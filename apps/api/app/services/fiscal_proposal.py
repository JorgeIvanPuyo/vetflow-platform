from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.errors import AppError
from app.core.roles import Role
from app.core.sale_limits import MONEY_QUANTUM
from app.core.tenant import TenantContext
from app.models.fiscal_configuration import FiscalPolicy, FiscalSeries
from app.models.fiscal_proposal import FiscalPaymentAllocation, FiscalProposal
from app.models.payment import PaymentMethod, SalePayment
from app.models.sale_fiscal import FiscalIssuer, SaleFiscalDocument
from app.models.user import User
from app.repositories.fiscal_proposal import FiscalProposalRepository
from app.repositories.sale import SaleRepository
from app.repositories.sale_fiscal_document import SaleFiscalDocumentRepository
from app.schemas.fiscal_proposal import (
    FiscalAllocationRead, FiscalBlocker, FiscalEligibility, FiscalPaymentReview,
    FiscalProposalApprove, FiscalProposalGenerate, FiscalProposalRead,
    FiscalProposalUpdate, FiscalReviewPermissions, FiscalReviewRead, FiscalReviewTotals,
)
from app.schemas.sale_fiscal import SaleFiscalDocumentRead
from app.services.fiscal_configuration import (
    ELECTRONIC_PAYMENT_TYPES, FISCAL_MANAGERS, FiscalConfigurationService,
    authorize_fiscal_context, series_pending_reasons,
)


def _canonical(value):
    if isinstance(value, Decimal):
        return format(value.quantize(MONEY_QUANTUM), ".2f")
    if isinstance(value, datetime):
        return value.replace(tzinfo=value.tzinfo or UTC).astimezone(UTC).isoformat()
    return str(value)


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=_canonical).encode()).hexdigest()


def _block(code, message):
    return FiscalBlocker(code=code, message=message)


class FiscalProposalService:
    """Local fiscal review only. No provider, stock, sale or payment mutations."""

    def __init__(self, db: Session):
        self.db = db
        self.repository = FiscalProposalRepository(db)
        self.sales = SaleRepository(db)
        self.configuration = FiscalConfigurationService(db)
        self.idempotency_replayed = False

    def _sale(self, tenant_id, sale_id, *, lock=False):
        sale = self.sales.get_by_id(tenant_id, sale_id, for_update=lock)
        if sale is None:
            raise AppError(404, "sale_not_found", "Venta no encontrada")
        if lock:
            # SQLAlchemy may already hold a sale loaded before a concurrent commit.
            self.db.refresh(sale, attribute_names=["status", "currency", "total_ars"])
        return sale

    def _series(self, tenant_id, series_id, *, lock=False):
        query = select(FiscalSeries).where(FiscalSeries.tenant_id == tenant_id, FiscalSeries.id == series_id)
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        series = self.db.scalar(query)
        if series is None:
            raise AppError(404, "fiscal_series_not_found", "Serie fiscal no encontrada")
        query = select(FiscalIssuer).where(FiscalIssuer.tenant_id == tenant_id, FiscalIssuer.id == series.fiscal_issuer_id)
        query = query.options(selectinload(FiscalIssuer.user.and_(User.tenant_id == tenant_id)))
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        issuer = self.db.scalar(query)
        if issuer is None:
            raise AppError(404, "fiscal_issuer_not_found", "Emisor fiscal no encontrado")
        return series, issuer

    def _proposal(self, tenant_id, sale_id, proposal_id, *, lock=False):
        proposal = self.repository.get(tenant_id, sale_id, proposal_id, lock=lock)
        if proposal is None:
            raise AppError(404, "fiscal_proposal_not_found", "Propuesta fiscal no encontrada")
        return proposal

    def _can_mutate(self, context, issuer_id=None):
        actor = authorize_fiscal_context(self.db, context)
        if actor.role in FISCAL_MANAGERS:
            return actor
        if actor.role == Role.MEDICO_VETERINARIO.value and issuer_id is not None:
            own = self.db.scalar(select(FiscalIssuer.id).where(FiscalIssuer.tenant_id == context.tenant_id, FiscalIssuer.id == issuer_id, FiscalIssuer.user_id == actor.id))
            if own is not None:
                return actor
        raise AppError(403, "fiscal_forbidden", "Sólo puedes revisar y aprobar propuestas de tu emisor vinculado")

    def _policy(self, tenant_id, *, lock=False):
        query = select(FiscalPolicy).where(FiscalPolicy.tenant_id == tenant_id)
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        return self.db.scalar(query)

    def _payments(self, tenant_id, sale_id, *, lock=False):
        query = select(SalePayment).where(SalePayment.tenant_id == tenant_id, SalePayment.sale_id == sale_id).order_by(SalePayment.id)
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        return list(self.db.scalars(query))

    def _methods(self, tenant_id, payments, *, lock=False):
        ids = {payment.payment_method_id for payment in payments}
        query = select(PaymentMethod).where(PaymentMethod.tenant_id == tenant_id, PaymentMethod.id.in_(ids)).order_by(PaymentMethod.id)
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        return {method.id: method for method in self.db.scalars(query)}

    def _sale_blockers(self, sale, policy):
        blockers = []
        if policy is None or not policy.enabled:
            blockers.append(_block("fiscal_module_disabled", "Activa y revisa la política fiscal en Ajustes antes de proponer cobros"))
        if sale.status != "confirmed":
            blockers.append(_block("fiscal_sale_not_confirmed", "Sólo las ventas confirmadas admiten propuestas fiscales"))
        if sale.currency != "ARS":
            blockers.append(_block("fiscal_currency_incompatible", "ARCA.1 sólo admite ventas ARS; no se convierten ni reinterpretan importes USD u otras monedas"))
        return blockers

    def _unknown_manual(self, tenant_id, sale_id):
        documents = list(self.db.scalars(select(SaleFiscalDocument).where(SaleFiscalDocument.tenant_id == tenant_id, SaleFiscalDocument.sale_id == sale_id, SaleFiscalDocument.is_active.is_(True), SaleFiscalDocument.source == "manual")))
        allocations = self.repository.allocations(tenant_id, sale_id, active_only=True)
        for document in documents:
            allocated = sum((row.amount_ars for row in allocations if row.fiscal_document_id == document.id), Decimal("0.00"))
            if allocated != document.total_ars_snapshot:
                return True
        return False

    def _snapshot(self, context, sale, payment_ids, series_id, *, lock=False):
        policy = self._policy(context.tenant_id, lock=lock)
        series, issuer = self._series(context.tenant_id, series_id, lock=lock)
        payments = self._payments(context.tenant_id, sale.id, lock=lock)
        by_id = {payment.id: payment for payment in payments}
        if any(payment_id not in by_id for payment_id in payment_ids):
            raise AppError(404, "sale_payment_not_found", "Cobro no encontrado en esta venta")
        chosen = [by_id[payment_id] for payment_id in sorted(payment_ids)]
        methods = self._methods(context.tenant_id, chosen, lock=lock)
        blockers = self._sale_blockers(sale, policy)
        blockers.extend(_block("fiscal_configuration_pending", reason) for reason in series_pending_reasons(series, issuer, policy))
        responsible = self.db.scalar(select(User).where(User.tenant_id == context.tenant_id, User.id == issuer.user_id, User.is_active.is_(True), User.role == Role.MEDICO_VETERINARIO.value))
        if responsible is None:
            blockers.append(_block("fiscal_responsible_invalid", "El responsable del emisor debe ser un médico veterinario activo de esta clínica"))
        if self._unknown_manual(context.tenant_id, sale.id):
            blockers.append(_block("fiscal_manual_allocation_unknown", "Existe un comprobante manual activo sin imputación monetaria conocida. Regularízalo explícitamente antes de aprobar propuestas nuevas"))
        active_allocations = {row.payment_id: row for row in self.repository.allocations(context.tenant_id, sale.id, active_only=True)}
        total = sum((payment.amount_ars for payment in chosen), Decimal("0.00")).quantize(MONEY_QUANTUM)
        if total > sale.total_ars or sum((payment.amount_ars for payment in payments if payment.is_active), Decimal("0.00")) > sale.total_ars:
            blockers.append(_block("fiscal_payment_totals_incompatible", "Los cobros activos superan el total de la venta y requieren conciliación antes de proponer importes fiscales"))
        for payment in chosen:
            if not payment.is_active:
                blockers.append(_block("fiscal_payment_inactive", "Un cobro seleccionado fue anulado; revisa la selección"))
            if payment.id in active_allocations:
                blockers.append(_block("fiscal_payment_reserved", "Un cobro seleccionado ya tiene una imputación fiscal activa"))
            if payment.payment_method_id not in methods:
                blockers.append(_block("fiscal_payment_method_not_found", "El método del cobro no pertenece a la clínica"))
            if policy is not None and policy.payment_scope == "electronic_only" and payment.payment_method_type_snapshot not in ELECTRONIC_PAYMENT_TYPES:
                code = "fiscal_other_requires_review" if payment.payment_method_type_snapshot == "other" else "fiscal_payment_excluded"
                blockers.append(_block(code, "El cobro no está seleccionado por la política electronic_only. Efectivo se conserva separado; other requiere revisión explícita de la política"))
        lines = [line for line in sale.items if line.tenant_id == context.tenant_id]
        kinds = {line.fiscal_line_type for line in lines}
        if not lines or sum((line.line_total_ars for line in lines), Decimal("0.00")) != sale.total_ars:
            blockers.append(_block("fiscal_sale_composition_invalid", "Las líneas fiscales no cierran con el total de la venta"))
        expected_concept = 1 if kinds == {"product"} else 2 if kinds == {"service"} else 3
        if series.concept != expected_concept:
            blockers.append(_block("fiscal_concept_incompatible", "El concepto de la serie no coincide con la clasificación fiscal de las líneas"))
        if kinds == {"product", "service"} and total != sale.total_ars:
            blockers.append(_block("fiscal_attribution_requires_split", "Esta venta mezcla productos y servicios y la selección no cubre su composición completa. Requiere atribución explícita o división fiscal del cobro; ARCA.1 no prorratea"))
        if expected_concept in (2, 3) and (not issuer.can_issue_service_receipt_c or issuer.service_document_type != series.document_type):
            blockers.append(_block("fiscal_issuer_service_ineligible", "El emisor no está configurado para documentar estos servicios con este tipo"))
        if expected_concept in (1, 3) and (not issuer.can_issue_product_invoice_c or issuer.product_document_type != series.document_type):
            blockers.append(_block("fiscal_issuer_product_ineligible", "El emisor no está configurado para documentar estos productos con este tipo"))
        snapshot = {
            "sale": {"id": str(sale.id), "status": sale.status, "currency": sale.currency, "total_ars": _canonical(sale.total_ars), "lines": [{"id": str(line.id), "fiscal_line_type": line.fiscal_line_type, "description": line.description_snapshot, "total_ars": _canonical(line.line_total_ars)} for line in sorted(lines, key=lambda line: line.id)]},
            "policy": {"enabled": bool(policy and policy.enabled), "payment_scope": policy.payment_scope if policy else "electronic_only", "revision": policy.revision if policy else 0, "accounting_reviewed_at": _canonical(policy.accounting_reviewed_at) if policy and policy.accounting_reviewed_at else None},
            "issuer": {"id": str(issuer.id), "user_id": str(issuer.user_id), "is_active": issuer.is_active, "cuit": issuer.cuit, "legal_name": issuer.legal_name, "tax_condition": issuer.tax_condition, "can_issue_service_receipt_c": issuer.can_issue_service_receipt_c, "can_issue_product_invoice_c": issuer.can_issue_product_invoice_c, "service_document_type": issuer.service_document_type, "product_document_type": issuer.product_document_type},
            "series": {"id": str(series.id), "cuit_snapshot": series.cuit_snapshot, "environment": series.environment, "point_of_sale": series.point_of_sale, "document_type": series.document_type, "concept": series.concept, "authorization_mode": series.authorization_mode, "revision": series.revision, "is_active": series.is_active},
            "payments": [{"id": str(payment.id), "amount_ars": _canonical(payment.amount_ars), "is_active": payment.is_active, "type": payment.payment_method_type_snapshot, "method_id": str(payment.payment_method_id), "received_at": _canonical(payment.received_at), "reference": payment.reference, "method_updated_at": _canonical(methods[payment.payment_method_id].updated_at) if payment.payment_method_id in methods else None, "suggested_fiscal_issuer_id": str(methods[payment.payment_method_id].suggested_fiscal_issuer_id) if payment.payment_method_id in methods and methods[payment.payment_method_id].suggested_fiscal_issuer_id else None} for payment in chosen],
        }
        local_issuer_ids = set(self.db.scalars(select(FiscalIssuer.id).where(FiscalIssuer.tenant_id == context.tenant_id)))
        snapshot["issuer"].update(service_document_code=issuer.service_document_code, product_document_code=issuer.product_document_code)
        snapshot["series"].update(credential_reference=series.credential_reference, caea_reference=series.caea_reference)
        for payment in snapshot["payments"]:
            if payment["suggested_fiscal_issuer_id"] and uuid.UUID(payment["suggested_fiscal_issuer_id"]) not in local_issuer_ids:
                payment["suggested_fiscal_issuer_id"] = None
        return snapshot, total, blockers, series, issuer

    def _read(self, context, proposal, *, sale=None):
        result = FiscalProposalRead.model_validate(proposal)
        result.allocations = [FiscalAllocationRead.model_validate(row) for row in self.repository.allocations(context.tenant_id, proposal.sale_id) if row.proposal_id == proposal.id]
        if proposal.status == "draft":
            sale = sale or self._sale(context.tenant_id, proposal.sale_id)
            try:
                snapshot, _total, blockers, _series, _issuer = self._snapshot(context, sale, [uuid.UUID(value) for value in proposal.payment_ids], proposal.fiscal_series_id)
                result.blockers = blockers
                result.is_stale = _hash(snapshot) != proposal.source_snapshot_hash
                if len(snapshot["sale"]["lines"]) > 1 and proposal.total_ars != sale.total_ars and not any(event["action"] == "reviewed" for event in proposal.audit_log):
                    result.blockers.append(_block("fiscal_attribution_review_required", "La selección cubre sólo parte de una venta con varias líneas; revisa explícitamente su descripción fiscal antes de aprobar"))
            except AppError:
                result.is_stale = True
                result.blockers = [_block("fiscal_proposal_stale", "Las referencias de la propuesta cambiaron; revisa su configuración y selección")]
            if result.is_stale:
                result.blockers.append(_block("fiscal_proposal_stale", "La propuesta está obsoleta; guarda una revisión con los datos actuales antes de aprobar"))
        return result

    @staticmethod
    def _event(proposal, actor, action, reason=None):
        proposal.audit_log = [*proposal.audit_log, {"action": action, "actor_id": str(actor.id), "at": datetime.now(UTC).isoformat(), "reason": reason}]

    def _set_draft(self, proposal, snapshot, total, series, description, actor):
        proposal.fiscal_issuer_id = series.fiscal_issuer_id
        proposal.fiscal_series_id = series.id
        proposal.payment_ids = sorted(payment["id"] for payment in snapshot["payments"])
        proposal.snapshot = snapshot
        proposal.source_snapshot_hash = _hash(snapshot)
        proposal.fiscal_description = description
        proposal.total_ars = total
        proposal.currency = "ARS"
        proposal.concept = series.concept
        proposal.content_hash = _hash({"snapshot": snapshot, "fiscal_description": description, "payment_ids": proposal.payment_ids})
        proposal.updated_by_user_id = actor.id
        proposal.updated_at = datetime.now(UTC)

    def generate(self, context: TenantContext, sale_id: uuid.UUID, payload: FiscalProposalGenerate):
        authorize_fiscal_context(self.db, context)
        if context.role not in FISCAL_MANAGERS | {Role.MEDICO_VETERINARIO.value}:
            raise AppError(403, "fiscal_forbidden", "No tienes permiso para generar propuestas")
        try:
            sale = self._sale(context.tenant_id, sale_id, lock=True)
            policy = self._policy(context.tenant_id)
            base_blockers = self._sale_blockers(sale, policy)
            if base_blockers:
                raise AppError(409, base_blockers[0].code, base_blockers[0].message)
            payments = self._payments(context.tenant_id, sale_id)
            by_id = {payment.id: payment for payment in payments}
            selected = payload.payment_ids
            if selected is not None and any(value not in by_id for value in selected):
                raise AppError(404, "sale_payment_not_found", "Cobro no encontrado en esta venta")
            methods = self._methods(context.tenant_id, payments)
            commitments = {row.payment_id for row in self.repository.allocations(context.tenant_id, sale_id, active_only=True)}
            existing_drafts = self.repository.list(context.tenant_id, sale_id)
            groups = {}
            if payload.fiscal_series_id:
                series, issuer = self._series(context.tenant_id, payload.fiscal_series_id)
                self._can_mutate(context, issuer.id)
            else:
                series = None
            for payment in payments:
                if selected is not None and payment.id not in selected:
                    continue
                policy_selected = policy.payment_scope == "all_payments" or payment.payment_method_type_snapshot in ELECTRONIC_PAYMENT_TYPES
                if not payment.is_active or payment.id in commitments or not policy_selected:
                    if selected is not None:
                        raise AppError(409, "fiscal_payment_unavailable", "Un cobro seleccionado está anulado, reservado o excluido por política")
                    continue
                resolved = series
                if resolved is None:
                    method = methods.get(payment.payment_method_id)
                    if method is None or method.suggested_fiscal_issuer_id is None:
                        continue
                    issuer_id = method.suggested_fiscal_issuer_id
                    if context.role == Role.MEDICO_VETERINARIO.value:
                        own = self.db.scalar(select(FiscalIssuer.id).where(FiscalIssuer.tenant_id == context.tenant_id, FiscalIssuer.id == issuer_id, FiscalIssuer.user_id == context.user_id))
                        if own is None:
                            continue
                    candidates = list(self.db.scalars(select(FiscalSeries).where(FiscalSeries.tenant_id == context.tenant_id, FiscalSeries.fiscal_issuer_id == issuer_id, FiscalSeries.is_active.is_(True))))
                    # Ambiguous environments/POS/types are never resolved by taking the first row.
                    if len(candidates) != 1:
                        continue
                    resolved = candidates[0]
                    _resolved, related_issuer = self._series(context.tenant_id, resolved.id)
                    self._can_mutate(context, related_issuer.id)
                groups.setdefault(resolved.id, []).append(payment.id)
            result_ids = []
            for series_id, ids in groups.items():
                description = payload.fiscal_description or "Revisión de cobros por " + "; ".join(dict.fromkeys(line.description_snapshot for line in sale.items if line.tenant_id == context.tenant_id))[:900]
                snapshot, total, _blockers, resolved, issuer = self._snapshot(context, sale, ids, series_id)
                actor = self._can_mutate(context, issuer.id)
                # Re-generating the same draft is harmless; approved content is never rewritten.
                matching = next((row for row in existing_drafts if row.status == "draft" and row.fiscal_series_id == series_id and row.payment_ids == sorted(str(value) for value in ids) and row.fiscal_description == description and row.source_snapshot_hash == _hash(snapshot)), None)
                if matching is not None:
                    result_ids.append(matching.id)
                    continue
                proposal = FiscalProposal(tenant_id=context.tenant_id, sale_id=sale_id, status="draft", created_by_user_id=actor.id, audit_log=[])
                self._set_draft(proposal, snapshot, total, resolved, description, actor)
                self._event(proposal, actor, "created")
                self.repository.add(proposal)
                result_ids.append(proposal.id)
            self.db.commit()
            return [self._read(context, self._proposal(context.tenant_id, sale_id, value)) for value in result_ids]
        except Exception:
            self.db.rollback()
            raise

    def update(self, context, sale_id, proposal_id, payload: FiscalProposalUpdate):
        authorize_fiscal_context(self.db, context)
        try:
            sale = self._sale(context.tenant_id, sale_id, lock=True)
            proposal = self._proposal(context.tenant_id, sale_id, proposal_id, lock=True)
            actor = self._can_mutate(context, proposal.fiscal_issuer_id)
            if proposal.status != "draft":
                raise AppError(409, "fiscal_proposal_frozen", "Sólo se pueden revisar borradores; cancela y crea una intención nueva si ya fue aprobada")
            snapshot, total, blockers, series, issuer = self._snapshot(context, sale, payload.payment_ids, payload.fiscal_series_id)
            self._can_mutate(context, issuer.id)
            if sale.currency != "ARS":
                raise AppError(409, "fiscal_currency_incompatible", "La propuesta requiere una venta ARS")
            self._set_draft(proposal, snapshot, total, series, payload.fiscal_description, actor)
            self._event(proposal, actor, "reviewed")
            self.db.flush()
            self.db.commit()
            return self._read(context, self._proposal(context.tenant_id, sale_id, proposal_id))
        except Exception:
            self.db.rollback()
            raise

    def approve(self, context, sale_id, proposal_id, payload: FiscalProposalApprove, idempotency_key: str):
        authorize_fiscal_context(self.db, context)
        if not idempotency_key or len(idempotency_key) > 128 or not all(33 <= ord(character) <= 126 for character in idempotency_key):
            raise AppError(422, "fiscal_idempotency_key_required", "Envía una clave de idempotencia válida para esta intención de aprobación")
        request_hash = _hash({"sale_id": sale_id, "proposal_id": proposal_id, **payload.model_dump()})
        try:
            sale = self._sale(context.tenant_id, sale_id, lock=True)
            proposal = self._proposal(context.tenant_id, sale_id, proposal_id, lock=True)
            actor = self._can_mutate(context, proposal.fiscal_issuer_id)
            existing = self.repository.by_key(context.tenant_id, idempotency_key)
            if existing is not None:
                if existing.id != proposal.id or existing.approval_request_hash != request_hash:
                    raise AppError(409, "fiscal_approval_idempotency_conflict", "La clave de aprobación ya se utilizó con contenido diferente")
                self.idempotency_replayed = True
                self.db.commit()
                return self._read(context, existing)
            if proposal.status != "draft":
                raise AppError(409, "fiscal_proposal_not_draft", "La propuesta ya fue aprobada o cancelada. Crea una intención nueva")
            if payload.content_hash != proposal.content_hash:
                raise AppError(409, "fiscal_proposal_stale", "El contenido cambió desde tu revisión; vuelve a cargar la propuesta")
            snapshot, total, blockers, _series, _issuer = self._snapshot(context, sale, [uuid.UUID(value) for value in proposal.payment_ids], proposal.fiscal_series_id, lock=True)
            if _hash(snapshot) != proposal.source_snapshot_hash or total != proposal.total_ars:
                raise AppError(409, "fiscal_proposal_stale", "Cambió la venta, un cobro o su configuración. Guarda una revisión actualizada antes de aprobar")
            if blockers:
                raise AppError(409, blockers[0].code, blockers[0].message)
            if len(snapshot["sale"]["lines"]) > 1 and proposal.total_ars != sale.total_ars and not any(event["action"] == "reviewed" for event in proposal.audit_log):
                raise AppError(409, "fiscal_attribution_review_required", "Revisa explícitamente la descripción fiscal de la selección parcial antes de aprobar")
            now = datetime.now(UTC)
            for payment_id in proposal.payment_ids:
                payment_snapshot = next(row for row in snapshot["payments"] if row["id"] == payment_id)
                self.db.add(FiscalPaymentAllocation(tenant_id=context.tenant_id, sale_id=sale_id, proposal_id=proposal.id, payment_id=uuid.UUID(payment_id), amount_ars=Decimal(payment_snapshot["amount_ars"]), is_active=True, reserved_by_user_id=actor.id, reserved_at=now))
            proposal.status = "approved"
            proposal.approved_at = now
            proposal.approved_by_user_id = actor.id
            proposal.idempotency_key = idempotency_key
            proposal.approval_request_hash = request_hash
            proposal.updated_by_user_id = actor.id
            proposal.updated_at = now
            self._event(proposal, actor, "approved")
            self.db.flush()
            self.db.commit()
            return self._read(context, self._proposal(context.tenant_id, sale_id, proposal_id))
        except IntegrityError as exc:
            self.db.rollback()
            existing = self.repository.by_key(context.tenant_id, idempotency_key)
            if existing is not None and existing.id == proposal_id and existing.approval_request_hash == request_hash:
                self.idempotency_replayed = True
                return self._read(context, existing)
            code = "fiscal_approval_idempotency_conflict" if existing else "fiscal_payment_reserved"
            raise AppError(409, code, "Otra aprobación comprometió el cobro o la clave. Actualiza la revisión antes de continuar") from exc
        except Exception:
            self.db.rollback()
            raise

    def cancel(self, context, sale_id, proposal_id, *, reason):
        authorize_fiscal_context(self.db, context)
        if not isinstance(reason, str) or not reason.strip():
            raise AppError(422, "fiscal_cancellation_reason_required", "Indica un motivo para cancelar")
        try:
            self._sale(context.tenant_id, sale_id, lock=True)
            proposal = self._proposal(context.tenant_id, sale_id, proposal_id, lock=True)
            actor = self._can_mutate(context, proposal.fiscal_issuer_id)
            if proposal.status not in {"draft", "approved"}:
                raise AppError(409, "fiscal_proposal_not_cancellable", "Sólo se pueden cancelar propuestas aún no enviadas; los estados enviados o inciertos requieren conciliación fiscal")
            now = datetime.now(UTC)
            for allocation in self.repository.allocations(context.tenant_id, sale_id, active_only=True):
                if allocation.proposal_id == proposal.id:
                    allocation.is_active = False
                    allocation.released_at = now
                    allocation.released_by_user_id = actor.id
                    allocation.release_reason = reason.strip()
            proposal.status = "cancelled"
            proposal.cancelled_at = now
            proposal.cancelled_by_user_id = actor.id
            proposal.cancellation_reason = reason.strip()
            proposal.updated_by_user_id = actor.id
            proposal.updated_at = now
            self._event(proposal, actor, "cancelled", reason.strip())
            self.db.flush()
            self.db.commit()
            return self._read(context, self._proposal(context.tenant_id, sale_id, proposal_id))
        except Exception:
            self.db.rollback()
            raise

    def review(self, context, sale_id):
        authorize_fiscal_context(self.db, context)
        sale = self._sale(context.tenant_id, sale_id)
        policy = self._policy(context.tenant_id)
        proposals = self.repository.list(context.tenant_id, sale_id)
        if context.role == Role.MEDICO_VETERINARIO.value:
            owned = set(self.db.scalars(select(FiscalIssuer.id).where(FiscalIssuer.tenant_id == context.tenant_id, FiscalIssuer.user_id == context.user_id)))
            proposals = [row for row in proposals if row.fiscal_issuer_id in owned]
        reads = [self._read(context, row, sale=sale) for row in proposals]
        payments = self._payments(context.tenant_id, sale_id)
        methods = self._methods(context.tenant_id, payments)
        commitments = {row.payment_id: row for row in self.repository.allocations(context.tenant_id, sale_id, active_only=True)}
        draft_map = {}
        for proposal in reads:
            if proposal.status == "draft" and not proposal.is_stale:
                for payment_id in proposal.payment_ids:
                    draft_map.setdefault(uuid.UUID(payment_id), proposal)
        valid_issuer_ids = set(self.db.scalars(select(FiscalIssuer.id).where(FiscalIssuer.tenant_id == context.tenant_id)))
        totals = {name: Decimal("0.00") for name in ("active_payments_ars", "committed_ars", "proposed_ars", "excluded_ars", "pending_ars", "available_ars")}
        payment_reads = []
        blockers = self._sale_blockers(sale, policy)
        if self._unknown_manual(context.tenant_id, sale_id):
            blockers.append(_block("fiscal_manual_allocation_unknown", "Regulariza el comprobante manual activo antes de aprobar nuevas propuestas"))
        for payment in payments:
            if not payment.is_active:
                continue
            totals["active_payments_ars"] += payment.amount_ars
            method = methods.get(payment.payment_method_id)
            suggestion = method.suggested_fiscal_issuer_id if method and method.suggested_fiscal_issuer_id in valid_issuer_ids else None
            proposal = draft_map.get(payment.id)
            reason = None
            proposal_id = None
            if payment.id in commitments:
                state, proposal_id = "committed", commitments[payment.id].proposal_id
                reason = "Imputación fiscal activa; cancela la propuesta no enviada para liberar el cobro"
            elif policy and policy.enabled and policy.payment_scope == "electronic_only" and payment.payment_method_type_snapshot == "cash":
                state, reason = "excluded", "Efectivo excluido de propuestas por política; esto no declara exención ni resuelve la obligación de facturar"
            elif policy and policy.enabled and policy.payment_scope == "electronic_only" and payment.payment_method_type_snapshot == "other":
                state, reason = "pending", "other requiere revisión explícita; no se presume electrónico"
            elif blockers:
                state, reason = "pending", blockers[0].message
            elif proposal:
                state, proposal_id = "proposed", proposal.id
                reason = proposal.blockers[0].message if proposal.blockers else "Borrador sin reserva; confirma emisor e identidad fiscal al aprobar"
            elif suggestion is None:
                state, reason = "pending", "Selecciona y confirma un emisor y una serie; no se deduce del label ni de la cuenta receptora"
            else:
                choices = list(self.db.scalars(select(FiscalSeries.id).where(FiscalSeries.tenant_id == context.tenant_id, FiscalSeries.fiscal_issuer_id == suggestion, FiscalSeries.is_active.is_(True))))
                state = "available" if len(choices) == 1 else "pending"
                reason = "Revisa el emisor sugerido antes de generar" if state == "available" else "Selecciona explícitamente ambiente, punto de venta y tipo de comprobante; la configuración es ambigua o falta"
            totals[state + "_ars"] += payment.amount_ars
            payment_reads.append(FiscalPaymentReview(payment_id=payment.id, payment_method_id=payment.payment_method_id, label=payment.payment_method_label_snapshot, type=payment.payment_method_type_snapshot, amount_ars=payment.amount_ars, status=state, reason=reason, suggested_fiscal_issuer_id=suggestion, proposal_id=proposal_id))
        own_issuer = self.db.scalar(select(FiscalIssuer.id).where(FiscalIssuer.tenant_id == context.tenant_id, FiscalIssuer.user_id == context.user_id))
        manager = context.role in FISCAL_MANAGERS
        mutator = manager or context.role == Role.MEDICO_VETERINARIO.value and own_issuer is not None
        documents = SaleFiscalDocumentRepository(self.db).list_for_sale(context.tenant_id, sale_id)
        return FiscalReviewRead(policy=self.configuration.policy_read(context.tenant_id, policy), eligibility=FiscalEligibility(eligible=not blockers, blockers=blockers), payments=payment_reads, proposals=reads, documents=[SaleFiscalDocumentRead.model_validate(row) for row in documents], totals=FiscalReviewTotals(**{name: value.quantize(MONEY_QUANTUM) for name, value in totals.items()}), permissions=FiscalReviewPermissions(can_generate=mutator, can_approve=mutator, can_manage_configuration=manager, own_issuer_id=own_issuer if context.role == Role.MEDICO_VETERINARIO.value else None))

    def regularize_manual(self, context, sale_id, document_id, payload, idempotency_key):
        """Explicit historical attribution; policy exclusions do not erase obligations."""
        authorize_fiscal_context(self.db, context)
        if not idempotency_key or len(idempotency_key) > 128 or not all(33 <= ord(character) <= 126 for character in idempotency_key):
            raise AppError(422, "fiscal_idempotency_key_required", "La revisión requiere una clave de idempotencia")
        request_hash = _hash({"sale_id": sale_id, "document_id": document_id, "payment_ids": sorted(str(value) for value in payload.payment_ids), "confirmed": payload.confirm_fiscal_identity})
        try:
            sale = self._sale(context.tenant_id, sale_id, lock=True)
            document = self.db.scalar(select(SaleFiscalDocument).where(SaleFiscalDocument.tenant_id == context.tenant_id, SaleFiscalDocument.sale_id == sale_id, SaleFiscalDocument.id == document_id).with_for_update().execution_options(populate_existing=True))
            if document is None:
                raise AppError(404, "sale_fiscal_document_not_found", "Comprobante fiscal no encontrado")
            actor = self._can_mutate(context, document.fiscal_issuer_id)
            key_owner = self.db.scalar(select(SaleFiscalDocument).where(SaleFiscalDocument.tenant_id == context.tenant_id, SaleFiscalDocument.allocation_idempotency_key == idempotency_key))
            if key_owner is not None:
                if key_owner.id != document.id or key_owner.allocation_request_hash != request_hash:
                    raise AppError(409, "fiscal_allocation_idempotency_conflict", "La clave de revisión manual ya se utilizó con otra selección")
                self.db.commit()
                return self.review(context, sale_id)
            if document.source != "manual" or not document.is_active:
                raise AppError(409, "fiscal_manual_document_required", "Selecciona un comprobante manual activo")
            if document.allocation_reviewed_at is not None:
                raise AppError(409, "fiscal_document_allocated", "El comprobante ya fue regularizado; conserva su imputación y solicita revisión contable para corregirlo")
            if sale.status != "confirmed" or sale.currency != "ARS":
                raise AppError(409, "fiscal_manual_sale_incompatible", "La regularización de ARCA.1 requiere una venta confirmada ARS")
            # Validate the document's responsible identity without changing its historical snapshot.
            issuer = self.db.scalar(select(FiscalIssuer.id).where(FiscalIssuer.tenant_id == context.tenant_id, FiscalIssuer.id == document.fiscal_issuer_id))
            if issuer is None:
                raise AppError(404, "fiscal_issuer_not_found", "Emisor fiscal no encontrado")
            payments = {payment.id: payment for payment in self._payments(context.tenant_id, sale_id, lock=True)}
            if any(value not in payments for value in payload.payment_ids):
                raise AppError(404, "sale_payment_not_found", "Cobro no encontrado en esta venta")
            selected = [payments[value] for value in payload.payment_ids]
            reserved = {row.payment_id for row in self.repository.allocations(context.tenant_id, sale_id, active_only=True)}
            if any(not row.is_active or row.id in reserved for row in selected):
                raise AppError(409, "fiscal_payment_unavailable", "Un cobro está anulado o ya imputado fiscalmente")
            total = sum((row.amount_ars for row in selected), Decimal("0.00")).quantize(MONEY_QUANTUM)
            if total != document.total_ars_snapshot or total > sale.total_ars:
                raise AppError(409, "fiscal_manual_total_mismatch", "La suma de cobros íntegros debe coincidir exactamente con el total histórico del comprobante")
            now = datetime.now(UTC)
            for payment in selected:
                self.db.add(FiscalPaymentAllocation(tenant_id=context.tenant_id, sale_id=sale_id, fiscal_document_id=document.id, payment_id=payment.id, amount_ars=payment.amount_ars, is_active=True, reserved_by_user_id=actor.id, reserved_at=now))
            document.allocation_idempotency_key = idempotency_key
            document.allocation_request_hash = request_hash
            document.allocation_reviewed_at = now
            document.allocation_reviewed_by_user_id = actor.id
            self.db.flush()
            self.db.commit()
            return self.review(context, sale_id)
        except IntegrityError as exc:
            self.db.rollback()
            raise AppError(409, "fiscal_payment_reserved", "Otra revisión comprometió un cobro o la clave de regularización; actualiza la pantalla") from exc
        except Exception:
            self.db.rollback()
            raise

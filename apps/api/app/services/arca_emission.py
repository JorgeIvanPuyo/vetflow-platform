"""Recoverable CAE orchestration; every outbound emission has durable identity.

Transactions end before authentication and HTTP. A claim expiration permits
reconciliation, never another number. Fences prevent an obsolete process from
persisting its outcome; a permitted resend always uses the same frozen request.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy.exc import IntegrityError

from app.core.errors import AppError
from app.core.roles import Role
from app.models.arca_emission import ArcaDocumentFile, ArcaEmissionAttempt, ArcaEmissionIntent, ArcaParameterCache
from app.models.sale_fiscal import SaleFiscalDocument
from app.repositories.arca_emission import ArcaEmissionRepository
from app.repositories.fiscal_issuer import FiscalIssuerRepository
from app.schemas.arca_emission import FiscalBusinessPayload
from app.schemas.fiscal_emission import FiscalEmissionActions, FiscalEmissionAttemptRead, FiscalEmissionFileRead, FiscalEmissionRead
from app.services.arca_credentials import require_homologation
from app.services.arca_pdf import render_authorized_pdf
from app.services.arca_runtime import ArcaRuntime
from app.services.arca_wsfe import PARAMETER_METHODS, business_fingerprint
from app.services.fiscal_configuration import FISCAL_MANAGERS, authorize_fiscal_context, authorize_fiscal_issuer_action, series_pending_reasons
from app.services.storage import get_purchase_attachment_storage_service


def utcnow():
    return datetime.now(UTC)


def aware(value):
    return value.replace(tzinfo=UTC) if value is not None and value.tzinfo is None else value


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


class ArcaEmissionService:
    def __init__(self, db, runtime=None, storage=None, *, clock=utcnow, owner_id=None, lease_seconds=120):
        self.db = db
        self.repository = ArcaEmissionRepository(db)
        self.clock = clock
        self.owner_id = owner_id or uuid.uuid4().hex
        self.lease_seconds = lease_seconds
        self.runtime = runtime if runtime is not None else ArcaRuntime(db, clock=clock)
        self.storage = storage if storage is not None else get_purchase_attachment_storage_service()
        self.idempotency_replayed = False

    def close(self):
        self.runtime.close()

    def _sale(self, context, sale_id, *, lock=False):
        sale = self.repository.sale(context.tenant_id, sale_id, lock=lock)
        if sale is None:
            raise AppError(404, "sale_not_found", "Venta no encontrada")
        return sale

    def _intent(self, context, sale_id, intent_id, *, lock=False):
        row = self.repository.intent(context.tenant_id, sale_id, intent_id, lock=lock)
        if row is None:
            raise AppError(404, "arca_emission_not_found", "Operación fiscal no encontrada")
        return row

    def _authorize(self, context, row, *, mutate=True):
        actor = authorize_fiscal_context(self.db, context)
        if mutate:
            return authorize_fiscal_issuer_action(self.db, context, row.fiscal_issuer_id)
        if context.role == Role.MEDICO_VETERINARIO.value:
            issuer = self.repository.issuer(context.tenant_id, row.fiscal_issuer_id)
            if issuer is None or issuer.user_id != actor.id:
                raise AppError(404, "arca_emission_not_found", "Operación fiscal no encontrada")
        return actor

    def _event(self, row, context, action, outcome, fence=None):
        self.repository.add(ArcaEmissionAttempt(tenant_id=context.tenant_id, emission_id=row.id, action=action, outcome=outcome, actor_id=context.user_id, fence=row.claim_fence if fence is None else fence))

    def _read(self, context, row):
        self._authorize(context, row, mutate=False)
        proposal = self.repository.proposal(context.tenant_id, row.sale_id, row.proposal_id)
        mutator = context.role in FISCAL_MANAGERS or context.role == Role.MEDICO_VETERINARIO.value
        live_claim = row.claim_owner is not None and row.claim_until is not None and aware(row.claim_until) > self.clock()
        external = bool(self.runtime.external_enabled)
        statuses = {"prepared", "processing", "unknown", "conflict", "rejected", "authorized"}
        assert row.state in statuses
        return FiscalEmissionRead(
            id=row.id, proposal_id=row.proposal_id, sale_id=row.sale_id, status=row.state,
            environment=row.environment, request_hash=row.request_hash or row.intent_fingerprint,
            business_snapshot=row.request_payload or row.business_snapshot, number=row.number,
            cae=row.cae, cae_expiry=row.cae_expiry, document_id=row.document_id,
            file_status=row.file_status, diagnostics=row.diagnostics,
            next_action_at=row.next_action_at, created_at=row.created_at, updated_at=row.updated_at,
            attempts=[FiscalEmissionAttemptRead.model_validate(attempt) for attempt in self.repository.attempts(context.tenant_id, row.id)],
            file_versions=[FiscalEmissionFileRead.model_validate(version) for version in self.repository.files(context.tenant_id, row.id)],
            allowed_actions=FiscalEmissionActions(
                issue=mutator and external and row.state == "prepared" and proposal is not None and proposal.status == "approved",
                reconcile=mutator and external and row.state in {"processing", "unknown", "conflict"} and not live_claim,
                retry_same_request=mutator and external and row.state == "unknown" and row.last_diagnostic == "arca_remote_not_found" and not live_claim,
                regenerate=mutator and row.state == "authorized",
                download=row.state == "authorized" and row.file_status == "ready",
            ),
        )

    def list(self, context, sale_id=None, *, pending_only=False):
        actor = authorize_fiscal_context(self.db, context)
        if sale_id is not None:
            self._sale(context, sale_id)
        rows = self.repository.intents(context.tenant_id, sale_id, pending_only=pending_only)
        own = None
        if actor.role == Role.MEDICO_VETERINARIO.value:
            own_ids = {issuer.id for issuer in FiscalIssuerRepository(self.db).list(context.tenant_id, active_only=False) if issuer.user_id == actor.id}
            own = next(iter(own_ids), None)
            rows = [row for row in rows if row.fiscal_issuer_id in own_ids]
        mutable = actor.role in FISCAL_MANAGERS or actor.role == Role.MEDICO_VETERINARIO.value and own is not None
        return {"operations": [self._read(context, row).model_dump(mode="json") for row in rows], "permissions": {"can_prepare": mutable, "can_issue": mutable, "can_reconcile": mutable, "can_regenerate": mutable, "own_issuer_id": str(own) if own else None}, "external_validation": "pending", "production_blocked": True}

    def _proposal_ready(self, context, sale, proposal, *, initial=True):
        if proposal is None:
            raise AppError(404, "fiscal_proposal_not_found", "Propuesta fiscal no encontrada")
        authorize_fiscal_issuer_action(self.db, context, proposal.fiscal_issuer_id)
        allowed = {"approved"} if initial else {"approved", "sent", "unknown", "authorized", "rejected"}
        if proposal.status not in allowed or sale.status != "confirmed" or sale.currency != "ARS":
            raise AppError(409, "arca_approval_required", "La emisión requiere una propuesta aprobada vigente sobre una venta confirmada ARS")
        allocations = self.repository.allocations(context.tenant_id, sale.id, proposal.id, lock=True)
        ids = {allocation.payment_id for allocation in allocations}
        expected_ids = {uuid.UUID(value) for value in proposal.payment_ids}
        payments = self.repository.payments(context.tenant_id, sale.id, ids, lock=True)
        if ids != expected_ids or len(payments) != len(ids) or any(not payment.is_active for payment in payments) or sum((allocation.amount_ars for allocation in allocations), Decimal("0.00")) != proposal.total_ars:
            raise AppError(409, "arca_reservations_inconsistent", "Las reservas de cobros no coinciden con la aprobación fiscal; requiere revisión")
        amounts = {payment.id: payment.amount_ars for payment in payments}
        if any(allocation.amount_ars != amounts[allocation.payment_id] for allocation in allocations):
            raise AppError(409, "arca_reservations_inconsistent", "Cada reserva debe conservar íntegro el importe de su cobro")
        return allocations

    def _configuration_ready(self, context, proposal, data, *, credential_reference=None):
        policy = self.repository.policy(context.tenant_id, lock=True)
        if policy is None or not policy.enabled:
            raise AppError(409, "fiscal_module_disabled", "El módulo fiscal está desactivado")
        issuer = self.repository.issuer(context.tenant_id, proposal.fiscal_issuer_id, lock=True)
        if issuer is None or not issuer.is_active or (issuer.cuit, issuer.legal_name, issuer.tax_condition) != (data.issuer.cuit, data.issuer.legal_name, data.issuer.tax_condition):
            raise AppError(409, "arca_issuer_changed", "El emisor vigente difiere de la intención confirmada; requiere revisión")
        series = self.repository.series(context.tenant_id, proposal.fiscal_series_id, lock=True)
        document_type = "invoice_c" if data.document_type == 11 else "receipt_c"
        if series is None or not series.is_active or (series.environment, series.point_of_sale, series.document_type, series.concept, series.authorization_mode, series.fiscal_issuer_id, series.cuit_snapshot) != (data.environment, data.point_of_sale, document_type, data.concept, "CAE", proposal.fiscal_issuer_id, data.issuer.cuit):
            raise AppError(409, "arca_series_changed", "La serie vigente difiere de la intención confirmada; requiere revisión explícita")
        if not series.credential_reference or credential_reference is not None and series.credential_reference != credential_reference:
            raise AppError(409, "arca_credentials_changed", "La referencia fiscal falta o cambió desde la confirmación; requiere revisión")
        if series_pending_reasons(series, issuer, policy):
            raise AppError(409, "arca_configuration_pending", "Revisa las capacidades y el responsable activo del emisor antes del primer envío")
        return series

    def prepare(self, context, sale_id, payload, idempotency_key):
        authorize_fiscal_context(self.db, context)
        require_homologation(payload.fiscal_data.environment)
        if not idempotency_key or len(idempotency_key) > 128 or any(not 33 <= ord(char) <= 126 for char in idempotency_key):
            raise AppError(422, "arca_idempotency_key_required", "La intención requiere una clave de idempotencia válida")
        if payload.fiscal_data.number is not None:
            raise AppError(422, "arca_number_server_owned", "El número lo asigna el servidor después de consultar la serie remota")
        canonical = payload.model_dump(mode="json")
        intent_hash = fingerprint(canonical)
        try:
            sale = self._sale(context, sale_id, lock=True)
            proposal = self.repository.proposal(context.tenant_id, sale_id, payload.proposal_id, lock=True)
            if proposal is None:
                raise AppError(404, "fiscal_proposal_not_found", "Propuesta fiscal no encontrada")
            authorize_fiscal_issuer_action(self.db, context, proposal.fiscal_issuer_id)
            previous_key = self.repository.by_key(context.tenant_id, idempotency_key)
            if previous_key is not None:
                if previous_key.intent_fingerprint != intent_hash or previous_key.sale_id != sale_id:
                    raise AppError(409, "arca_intent_idempotency_conflict", "La clave de emisión ya identifica otro contenido")
                self.idempotency_replayed = True
                self.db.commit()
                return self._read(context, previous_key)
            current = self.repository.current_for_proposal(context.tenant_id, proposal.id, lock=True)
            correction = current is not None and current.state == "rejected" and payload.supersedes_id == current.id
            if current is not None and not correction:
                raise AppError(409, "arca_proposal_already_committed", "La propuesta ya tiene una intención fiscal; recupera esa operación en lugar de crear otra")
            if payload.supersedes_id is not None and not correction:
                raise AppError(409, "arca_correction_not_allowed", "Sólo un rechazo definitivo puede corregirse mediante una intención nueva explícita")
            self._proposal_ready(context, sale, proposal, initial=not correction)
            data = payload.fiscal_data
            frozen_issuer = proposal.snapshot["issuer"]
            frozen_series = proposal.snapshot["series"]
            expected_type = {"invoice_c": 11, "receipt_c": 15}[frozen_series["document_type"]]
            if data.issuer.cuit != frozen_issuer.get("cuit") or data.issuer.legal_name != frozen_issuer.get("legal_name") or data.issuer.tax_condition != frozen_issuer.get("tax_condition"):
                raise AppError(409, "arca_issuer_identity_mismatch", "La identidad del emisor debe coincidir con la aprobación congelada")
            if data.environment != frozen_series["environment"] or data.point_of_sale != frozen_series["point_of_sale"] or data.document_type != expected_type or data.concept != proposal.concept or data.total != proposal.total_ars:
                raise AppError(409, "arca_approved_content_mismatch", "Ambiente, serie, concepto e importe deben coincidir con la aprobación")
            if frozen_series["authorization_mode"] != "CAE":
                raise AppError(409, "arca_caea_pending", "El circuito completo CAEA está pendiente; no se sustituye CAE automáticamente")
            series = self._configuration_ready(context, proposal, data)
            series_key = fingerprint([data.environment, data.issuer.cuit, data.point_of_sale, data.document_type])
            owner = self.repository.claim_series_ownership(context.tenant_id, series_key, data)
            if correction:
                current.is_current = False
                self.db.flush()
            row = ArcaEmissionIntent(tenant_id=context.tenant_id, sale_id=sale_id, proposal_id=proposal.id, fiscal_issuer_id=proposal.fiscal_issuer_id, fiscal_series_id=proposal.fiscal_series_id, series_owner_id=owner.id, environment=data.environment, state="prepared", is_current=True, supersedes_id=current.id if correction else None, idempotency_key=idempotency_key, intent_fingerprint=intent_hash, approval_content_hash=proposal.content_hash, business_snapshot=data.model_dump(mode="json"), credential_reference=series.credential_reference, created_by_user_id=context.user_id, diagnostics=[], file_status="pending", claim_fence=0)
            self.repository.add(row)
            self._event(row, context, "prepare", "corrected_rejection" if correction else "prepared")
            self.db.commit()
            return self._read(context, row)
        except IntegrityError as exc:
            self.db.rollback()
            existing = self.repository.by_key(context.tenant_id, idempotency_key)
            if existing is not None and existing.intent_fingerprint == intent_hash and existing.sale_id == sale_id:
                self.idempotency_replayed = True
                return self._read(context, existing)
            raise AppError(409, "arca_intent_conflict", "Otra operación ya comprometió la propuesta o su clave") from exc
        except Exception:
            self.db.rollback()
            raise

    def _claim(self, context, sale_id, intent_id, *, reconciliation=False):
        sale = self._sale(context, sale_id, lock=True)
        row = self._intent(context, sale_id, intent_id, lock=True)
        self._authorize(context, row)
        require_homologation(row.environment)
        if row.state == "authorized":
            return row, None
        if row.state == "rejected" or not row.is_current:
            raise AppError(409, "arca_rejected_requires_new_intent", "Un rechazo definitivo requiere una intención nueva auditada")
        if row.state == "conflict":
            reconciliation = True
        proposal = self.repository.proposal(context.tenant_id, sale_id, row.proposal_id, lock=True)
        self._proposal_ready(context, sale, proposal, initial=False)
        if proposal.content_hash != row.approval_content_hash:
            raise AppError(409, "arca_approval_changed", "La aprobación no coincide con la intención congelada")
        if row.number is None:
            # Before any possible business send the current configuration must
            # still permit it. Once numbered, reconciliation uses the frozen
            # identity even if the operator later disables that configuration.
            self._configuration_ready(context, proposal, FiscalBusinessPayload.model_validate(row.business_snapshot), credential_reference=row.credential_reference)
        if not reconciliation and row.state != "prepared":
            raise AppError(409, "arca_reconcile_required", "La operación ya fue iniciada; consulta su resultado exacto antes de considerar un reenvío")
        owner = self.repository.owner(context.tenant_id, row.series_owner_id, lock=True)
        if owner is None:
            raise AppError(409, "arca_series_unavailable", "No se encuentra la propiedad de esta serie")
        now = self.clock()
        if owner.active_intent_id is not None and owner.active_intent_id != row.id:
            raise AppError(409, "arca_series_busy", "Otra operación de esta serie tiene un resultado pendiente; reconcilia esa operación antes de avanzar")
        if row.claim_owner and row.claim_until and aware(row.claim_until) > now:
            raise AppError(409, "arca_emission_in_progress", "La operación conserva un claim vigente; espera su resultado o su vencimiento para reconciliar")
        owner.fence += 1
        owner.active_intent_id = row.id
        owner.lease_owner = self.owner_id
        owner.lease_until = now + timedelta(seconds=self.lease_seconds)
        row.claim_owner = self.owner_id
        row.claim_until = owner.lease_until
        row.claim_fence = owner.fence
        row.state = "processing"
        row.updated_at = now
        proposal.status = "sent"
        self._event(row, context, "reconcile" if reconciliation else "issue", "claimed")
        fence = row.claim_fence
        return row, fence

    def _owned(self, context, sale_id, intent_id, fence):
        self._sale(context, sale_id, lock=True)
        row = self._intent(context, sale_id, intent_id, lock=True)
        owner = self.repository.owner(context.tenant_id, row.series_owner_id, lock=True)
        if row.state == "authorized" or owner is None or row.claim_owner != self.owner_id or row.claim_fence != fence or owner.fence != fence or owner.lease_owner != self.owner_id or owner.active_intent_id != row.id:
            return row, owner, False
        return row, owner, True

    def _parameters(self, context, environment, cuit, ticket):
        from sqlalchemy import select
        result = {}
        for method in sorted(PARAMETER_METHODS):
            scope = fingerprint([environment, cuit, ticket.certificate_fingerprint, ticket.auth_scope, method])
            cache = self.db.scalar(select(ArcaParameterCache).where(ArcaParameterCache.tenant_id == context.tenant_id, ArcaParameterCache.scope_key == scope))
            if cache is not None and aware(cache.expires_at) > self.clock():
                result[method] = cache.payload
                self.db.commit()
                continue
            self.db.commit()
            values = self.runtime.wsfe.parameters(method, ticket, cuit)
            result[method] = values
            cache = self.db.scalar(select(ArcaParameterCache).where(ArcaParameterCache.tenant_id == context.tenant_id, ArcaParameterCache.scope_key == scope))
            if cache is None:
                cache = ArcaParameterCache(tenant_id=context.tenant_id, scope_key=scope, environment=environment, cuit=cuit, method=method)
                self.db.add(cache)
            cache.payload = values
            cache.expires_at = self.clock() + timedelta(minutes=15)
            try:
                self.db.commit()
            except IntegrityError:
                self.db.rollback()  # A concurrent parameter read populated the same scope.
        return result

    @staticmethod
    def _validate_parameters(payload, parameters):
        requirements = {"FEParamGetTiposCbte": payload.document_type, "FEParamGetTiposDoc": payload.receiver.document_type, "FEParamGetTiposConcepto": payload.concept, "FEParamGetTiposMonedas": payload.currency, "FEParamGetCondicionIvaReceptor": payload.receiver.iva_condition_id}
        for method, expected in requirements.items():
            if not any(str(value.get("Id")) == str(expected) for value in parameters[method]):
                raise AppError(409, "arca_remote_parameter_incompatible", "Un dato fiscal no aparece entre los parámetros remotos aplicables; requiere revisión")
        points = [value for value in parameters["FEParamGetPtosVenta"] if str(value.get("Nro")) == str(payload.point_of_sale)]
        if len(points) != 1 or str(points[0].get("Bloqueado", "N")).upper() != "N" or points[0].get("FchBaja") not in (None, "", "NULL", "00000000"):
            raise AppError(409, "arca_point_of_sale_not_enabled", "El punto de venta no está disponible para este emisor en la consulta remota")
        # A global catalogue is not proof of taxpayer habilitation. The actual
        # authorization still decides; no inferred permissions are persisted.

    def _after_number_persisted(self):
        """Fault-injection checkpoint in tests; never selected through the API."""

    def _before_result_commit(self):
        """Fault-injection checkpoint for a DB failure after a remote answer."""

    def issue(self, context, sale_id, intent_id):
        authorize_fiscal_context(self.db, context)
        row = self._intent(context, sale_id, intent_id)
        self._authorize(context, row)
        require_homologation(row.environment)
        if row.state == "authorized":
            return self._read(context, row)
        self.runtime.ensure_available(context.tenant_id, row.credential_reference, row.environment, row.business_snapshot["issuer"]["cuit"])
        claimed = False
        try:
            row, fence = self._claim(context, sale_id, intent_id)
            if fence is None:
                self.db.commit()
                return self._read(context, row)
            reference, environment = row.credential_reference, row.environment
            payload = FiscalBusinessPayload.model_validate(row.business_snapshot)
            self.db.commit()
            claimed = True
            ticket = self.runtime.get_ticket(context.tenant_id, reference, environment, payload.issuer.cuit)
            self.db.commit()
            parameters = self._parameters(context, payload.environment, payload.issuer.cuit, ticket)
            self._validate_parameters(payload, parameters)
            self.db.commit()
            last = self.runtime.wsfe.last_authorized(ticket, payload.issuer.cuit, payload.point_of_sale, payload.document_type)
            row, owner, owned = self._owned(context, sale_id, intent_id, fence)
            if not owned:
                self.db.commit()
                return self._read(context, row)
            if row.number is not None:
                raise AppError(409, "arca_reconcile_required", "Ya existe un número persistido; no se elegirá otro")
            numbered = FiscalBusinessPayload.model_validate({**payload.model_dump(mode="json"), "number": last + 1})
            row.number = numbered.number
            row.request_payload = numbered.model_dump(mode="json")
            row.request_hash = business_fingerprint(numbered)
            self._event(row, context, "persist", "request_number_frozen")
            self.db.commit()
            self._after_number_persisted()
            response = self.runtime.wsfe.request_authorization(numbered, ticket, numbered.issuer.cuit)
            return self._finalize(context, sale_id, intent_id, fence, response, numbered)
        except Exception as error:
            self.db.rollback()
            if claimed:
                return self._uncertain(context, sale_id, intent_id, fence, "arca_emission_uncertain" if not isinstance(error, AppError) else error.code)
            raise

    def _uncertain(self, context, sale_id, intent_id, fence, code):
        try:
            row, owner, owned = self._owned(context, sale_id, intent_id, fence)
            if not owned:
                self.db.commit()
                return self._read(context, row)
            row.state = "unknown"
            row.last_diagnostic = code
            row.diagnostics = [{"code": code, "message": "Resultado pendiente de conciliación. Se conservan número, solicitud y reservas; no se emitirá otro número"}]
            row.next_action_at = self.clock() + timedelta(seconds=5)
            row.claim_owner = None
            row.claim_until = None
            owner.lease_owner = None
            owner.lease_until = None
            proposal = self.repository.proposal(context.tenant_id, sale_id, row.proposal_id, lock=True)
            if proposal.status != "authorized":
                proposal.status = "unknown"
            self._event(row, context, "recover", code)
            self.db.commit()
            return self._read(context, row)
        except Exception:
            self.db.rollback()
            raise AppError(503, "arca_outcome_persistence_pending", "La solicitud fiscal tiene un estado durable pendiente; recupérala por su identificador antes de continuar") from None

    def _finalize(self, context, sale_id, intent_id, fence, response, payload):
        row, owner, owned = self._owned(context, sale_id, intent_id, fence)
        if not owned:
            self.db.commit()
            return self._read(context, row)
        comparison = response.comparison(payload)
        if response.status == "authorized" and comparison == "match":
            if row.document_id is None:
                proposal = self.repository.proposal(context.tenant_id, sale_id, row.proposal_id, lock=True)
                document = SaleFiscalDocument(tenant_id=context.tenant_id, sale_id=sale_id, fiscal_issuer_id=row.fiscal_issuer_id, issuer_user_id_snapshot=uuid.UUID(proposal.snapshot["issuer"]["user_id"]), issuer_name_snapshot=payload.issuer.legal_name, issuer_tax_id_snapshot=payload.issuer.cuit, source="arca", authorization_status="authorized", environment=row.environment, document_type="invoice_c" if payload.document_type == 11 else "receipt_c", document_code=f"{payload.document_type:03d}", document_number=f"{payload.point_of_sale:05d}-{payload.number:08d}", issue_date=payload.voucher_date, total_ars_snapshot=payload.total, is_active=True, cae=response.cae, cae_expiry=response.cae_expiry, authorization_snapshot=payload.model_dump(mode="json"), emission_intent_id=row.id)
                self.repository.add(document)
                row.document_id = document.id
            row.cae = response.cae
            row.cae_expiry = response.cae_expiry
            row.state = "authorized"
            row.last_diagnostic = None
            row.next_action_at = None
            row.diagnostics = [{"code": str(message.code), "message": message.message} for message in (*response.observations, *response.events)]
            self.repository.proposal(context.tenant_id, sale_id, row.proposal_id, lock=True).status = "authorized"
            owner.active_intent_id = None
            self._event(row, context, "authorization", "authorized")
        elif response.status == "rejected":
            row.state = "rejected"
            row.last_diagnostic = "arca_definitive_rejection"
            row.diagnostics = [{"code": str(message.code), "message": message.message} for message in (*response.errors, *response.observations, *response.events)] or [{"code": "arca_definitive_rejection", "message": "Solicitud rechazada definitivamente; prepara una corrección explícita nueva"}]
            self.repository.proposal(context.tenant_id, sale_id, row.proposal_id, lock=True).status = "rejected"
            owner.active_intent_id = None
            self._event(row, context, "authorization", "rejected")
        else:
            row.state = "conflict" if comparison == "conflict" else "unknown"
            row.last_diagnostic = "arca_remote_conflict" if comparison == "conflict" else "arca_remote_not_found" if response.remote.get("not_found") else "arca_emission_uncertain"
            row.diagnostics = [{"code": row.last_diagnostic, "message": "La consulta no coincide con la identidad o importes congelados" if row.state == "conflict" else "Resultado remoto incierto; conserva la operación y consulta el número exacto"}]
            row.next_action_at = self.clock() + timedelta(seconds=5)
            self.repository.proposal(context.tenant_id, sale_id, row.proposal_id, lock=True).status = "unknown"
            self._event(row, context, "reconcile", row.last_diagnostic)
        row.claim_owner = None
        row.claim_until = None
        owner.lease_owner = None
        owner.lease_until = None
        row.updated_at = self.clock()
        self._before_result_commit()
        self.db.commit()
        if row.state == "authorized":
            return self.regenerate(context, sale_id, intent_id)
        return self._read(context, row)

    def reconcile(self, context, sale_id, intent_id, *, retry_same_request=False):
        authorize_fiscal_context(self.db, context)
        row = self._intent(context, sale_id, intent_id)
        self._authorize(context, row)
        require_homologation(row.environment)
        if row.state == "authorized":
            return self._read(context, row)
        self.runtime.ensure_available(context.tenant_id, row.credential_reference, row.environment, row.business_snapshot["issuer"]["cuit"])
        claimed = False
        try:
            row, fence = self._claim(context, sale_id, intent_id, reconciliation=True)
            payload = FiscalBusinessPayload.model_validate(row.request_payload or row.business_snapshot)
            reference, environment = row.credential_reference, row.environment
            self.db.commit()
            claimed = True
            ticket = self.runtime.get_ticket(context.tenant_id, reference, environment, payload.issuer.cuit)
            self.db.commit()
            if payload.number is None:
                # No business send can precede durable numbering in this design.
                parameters = self._parameters(context, payload.environment, payload.issuer.cuit, ticket)
                self._validate_parameters(payload, parameters)
                self.db.commit()
                last = self.runtime.wsfe.last_authorized(ticket, payload.issuer.cuit, payload.point_of_sale, payload.document_type)
                row, owner, owned = self._owned(context, sale_id, intent_id, fence)
                if not owned:
                    self.db.commit()
                    return self._read(context, row)
                numbered = FiscalBusinessPayload.model_validate({**payload.model_dump(mode="json"), "number": last + 1})
                row.number = numbered.number
                row.request_payload = numbered.model_dump(mode="json")
                row.request_hash = business_fingerprint(numbered)
                self._event(row, context, "persist", "recovered_request_number_frozen")
                self.db.commit()
                payload = numbered
            response = self.runtime.wsfe.consult(ticket, payload.issuer.cuit, payload.point_of_sale, payload.document_type, payload.number)
            if retry_same_request and response.status == "unknown" and response.remote.get("not_found"):
                row, owner, owned = self._owned(context, sale_id, intent_id, fence)
                if not owned:
                    self.db.commit()
                    return self._read(context, row)
                # Fresh fence check, same number, exact immutable business body.
                if row.request_hash != business_fingerprint(payload):
                    raise AppError(409, "arca_request_hash_conflict", "La solicitud persistida no coincide con su huella")
                self._event(row, context, "retry", "explicit_same_number_request")
                self.db.commit()
                response = self.runtime.wsfe.request_authorization(payload, ticket, payload.issuer.cuit)
            return self._finalize(context, sale_id, intent_id, fence, response, payload)
        except Exception as error:
            self.db.rollback()
            if claimed:
                return self._uncertain(context, sale_id, intent_id, fence, error.code if isinstance(error, AppError) else "arca_reconciliation_uncertain")
            raise

    def regenerate(self, context, sale_id, intent_id):
        authorize_fiscal_context(self.db, context)
        row = self._intent(context, sale_id, intent_id)
        self._authorize(context, row)
        if row.state != "authorized" or row.document_id is None:
            raise AppError(409, "arca_authorization_required", "Sólo se genera el archivo de una autorización persistida")
        require_homologation(row.environment)
        snapshot = dict(row.request_payload)
        authorization = {"cae": row.cae, "cae_expiry": row.cae_expiry.isoformat(), "number": row.number}
        environment, document_id, issuer_id = row.environment, row.document_id, row.fiscal_issuer_id
        self.db.commit()
        uploaded_key = None
        try:
            artifact = render_authorized_pdf(snapshot, authorization, environment)
            if not self.storage.bucket_name:
                raise ValueError("Storage missing")
            version_id = uuid.uuid4()
            key = f"tenants/{context.tenant_id}/fiscal/{environment}/{issuer_id}/{document_id}/{version_id}.pdf"
            self.storage.upload_clinical_file(object_path=key, content=artifact.pdf_bytes, content_type="application/pdf")
            uploaded_key = key
            self._sale(context, sale_id, lock=True)
            row = self._intent(context, sale_id, intent_id, lock=True)
            if row.state != "authorized" or row.document_id != document_id or row.request_payload != snapshot:
                raise ValueError("Authorized snapshot changed")
            descriptor = ArcaDocumentFile(id=version_id, tenant_id=context.tenant_id, emission_id=row.id, document_id=document_id, environment=environment, bucket_name=self.storage.bucket_name, storage_key=key, original_filename=f"homologacion-{snapshot['point_of_sale']:05d}-{snapshot['number']:08d}.pdf", sha256=artifact.sha256, size_bytes=len(artifact.pdf_bytes), created_by_user_id=context.user_id)
            self.repository.add(descriptor)
            document = self.repository.document(context.tenant_id, sale_id, document_id, lock=True)
            document.original_filename = descriptor.original_filename
            document.bucket_name = descriptor.bucket_name
            document.storage_key = key
            document.content_type = "application/pdf"
            document.size_bytes = descriptor.size_bytes
            document.sha256 = descriptor.sha256
            document.uploaded_at = self.clock()
            document.uploaded_by_user_id = context.user_id
            row.file_status = "ready"
            self._event(row, context, "file", "ready")
            self.db.commit()
        except Exception:
            self.db.rollback()
            if uploaded_key:
                try:
                    self.storage.delete_clinical_file(bucket_name=self.storage.bucket_name, object_path=uploaded_key)
                except Exception:
                    pass  # Orphan cleanup is safe to retry by its tenant-scoped key.
            row = self._intent(context, sale_id, intent_id, lock=True)
            # A failed regeneration does not invalidate an earlier immutable
            # version. Keep its download available and record the failed new
            # attempt separately from the authorization and available file.
            previous_versions = self.repository.files(context.tenant_id, row.id)
            row.file_status = "ready" if previous_versions else "failed"
            self._event(row, context, "file", "regeneration_failed_previous_version_retained"
                        if previous_versions else "authorized_file_pending")
            self.db.commit()
        return self._read(context, row)

    def download(self, context, sale_id, intent_id, *, version_id=None):
        authorize_fiscal_context(self.db, context)
        row = self._intent(context, sale_id, intent_id)
        self._authorize(context, row, mutate=False)
        if row.state != "authorized":
            raise AppError(404, "arca_file_not_found", "Archivo fiscal no encontrado")
        versions = self.repository.files(context.tenant_id, intent_id)
        descriptor = self.repository.file(context.tenant_id, intent_id, version_id) if version_id else versions[0] if versions else None
        if descriptor is None or descriptor.environment != row.environment or descriptor.document_id != row.document_id:
            raise AppError(404, "arca_file_not_found", "Archivo fiscal no encontrado")
        prefix = f"tenants/{context.tenant_id}/fiscal/{row.environment}/{row.fiscal_issuer_id}/{row.document_id}/"
        if not descriptor.storage_key.startswith(prefix):
            raise AppError(404, "arca_file_not_found", "Archivo fiscal no encontrado")
        content = self.storage.download_object_bytes(bucket_name=descriptor.bucket_name, object_path=descriptor.storage_key)
        if len(content) != descriptor.size_bytes or hashlib.sha256(content).hexdigest() != descriptor.sha256:
            raise AppError(409, "arca_file_integrity_error", "La integridad del archivo fiscal no coincide con su versión registrada")
        return descriptor, content

    def readiness(self, context, series_id, *, validate=False):
        actor = authorize_fiscal_context(self.db, context)
        series = self.repository.series(context.tenant_id, series_id)
        if series is None:
            raise AppError(404, "fiscal_series_not_found", "Serie fiscal no encontrada")
        issuer = self.repository.issuer(context.tenant_id, series.fiscal_issuer_id)
        if issuer is None:
            raise AppError(404, "fiscal_issuer_not_found", "Emisor fiscal no encontrado")
        if validate:
            authorize_fiscal_issuer_action(self.db, context, issuer.id)
            require_homologation(series.environment)
        status = self.runtime.credential_status(context.tenant_id, series.credential_reference or "", series.environment, issuer.cuit or "")
        policy = self.repository.policy(context.tenant_id)
        can_mutate = actor.role in FISCAL_MANAGERS or actor.role == Role.MEDICO_VETERINARIO.value and issuer.user_id == actor.id
        configured = not series_pending_reasons(series, issuer, policy)
        result = {"credential": status, "remote_validation": "pending", "parameters": None, "blockers": [], "production_blocked": True, "allowed_actions": {"validate": can_mutate and configured and series.environment == "homologation" and bool(self.runtime.external_enabled)}}
        if series.environment != "homologation":
            result["blockers"].append({"code": "arca_production_disabled", "message": "Producción permanece bloqueada antes de resolver credenciales o iniciar transporte"})
            return result
        if not configured:
            result["blockers"].append({"code": "arca_configuration_pending", "message": "Completa identidad, referencia y serie antes de validar"})
            return result
        if not self.runtime.external_enabled:
            result["blockers"].append({"code": "arca_homologation_disabled", "message": "Homologación externa pendiente de accesos y validación; no se usarán dobles en la aplicación"})
            if validate:
                raise AppError(503, "arca_homologation_disabled", result["blockers"][0]["message"])
        if validate:
            self.runtime.ensure_available(context.tenant_id, series.credential_reference, series.environment, issuer.cuit)
            reference, environment, cuit = series.credential_reference, series.environment, issuer.cuit
            self.db.commit()
            ticket = self.runtime.get_ticket(context.tenant_id, reference, environment, cuit)
            self.db.commit()
            parameters = self._parameters(context, environment, cuit, ticket)
            result["parameters"] = parameters
            result["remote_validation"] = "validated"
            result["credential"] = {**status, "fingerprint": ticket.certificate_fingerprint, "expires_at": ticket.expires_at.isoformat(), "diagnostic": "Autenticación y parámetros consultados; la habilitación del tipo y su autorización efectiva no se deducen del catálogo"}
        return result

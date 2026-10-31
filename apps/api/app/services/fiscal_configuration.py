from __future__ import annotations

import uuid
from datetime import UTC, datetime

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.roles import Role
from app.core.tenant import TenantContext
from app.models.fiscal_configuration import FiscalPolicy, FiscalPolicyReview, FiscalSeries
from app.models.sale_fiscal import FiscalIssuer
from app.models.tenant import Tenant
from app.models.user import User
from app.repositories.fiscal_configuration import FiscalConfigurationRepository
from app.repositories.fiscal_issuer import FiscalIssuerRepository
from app.repositories.user import UserRepository
from app.schemas.fiscal_configuration import (
    FiscalConfigurationRead, FiscalPermissions, FiscalPolicyRead,
    FiscalPolicyReviewRead, FiscalPolicyUpdate, FiscalSeriesCreate,
    FiscalSeriesRead, FiscalSeriesUpdate,
)
from app.schemas.fiscal_issuer import FiscalIssuerRead, normalize_cuit
from app.schemas.payment import PaymentMethodRead


FISCAL_MANAGERS = {Role.CLINIC_ADMIN.value, Role.CONTADOR.value}
FISCAL_READERS = FISCAL_MANAGERS | {Role.MEDICO_VETERINARIO.value, Role.SECRETARIA.value}
ELECTRONIC_PAYMENT_TYPES = {"bank_transfer", "debit_card", "credit_card", "digital_wallet"}


def authorize_fiscal_context(db: Session, context: TenantContext, *, manage: bool = False) -> User:
    """Never grant fiscal access to an anonymous development tenant or role."""
    actor = UserRepository(db).get_by_id(context.tenant_id, context.user_id) if context.user_id else None
    allowed = FISCAL_MANAGERS if manage else FISCAL_READERS
    if actor is None or not actor.is_active or actor.role != context.role or context.role not in allowed:
        raise AppError(403, "fiscal_forbidden", "No tienes autorización fiscal para esta acción")
    return actor


def authorize_fiscal_issuer_action(db: Session, context: TenantContext, issuer_id: uuid.UUID, *, for_update: bool = False) -> User:
    """Managers or the current responsible veterinarian may mutate fiscal work."""
    actor = authorize_fiscal_context(db, context)
    if actor.role not in FISCAL_MANAGERS | {Role.MEDICO_VETERINARIO.value}:
        raise AppError(403, "fiscal_forbidden", "No tienes autorización para modificar comprobantes fiscales")
    query = select(FiscalIssuer).where(FiscalIssuer.tenant_id == context.tenant_id, FiscalIssuer.id == issuer_id)
    if for_update:
        query = query.with_for_update().execution_options(populate_existing=True)
    issuer = db.scalar(query)
    if issuer is None:
        raise AppError(404, "fiscal_issuer_not_found", "Emisor fiscal no encontrado")
    if actor.role not in FISCAL_MANAGERS and issuer.user_id != actor.id:
        raise AppError(403, "fiscal_forbidden", "Sólo puedes modificar comprobantes de tu emisor vinculado")
    return actor


def fiscal_permissions(context: TenantContext) -> FiscalPermissions:
    manager = context.role in FISCAL_MANAGERS
    veterinarian = context.role == Role.MEDICO_VETERINARIO.value
    return FiscalPermissions(can_manage_configuration=manager, can_review_proposals=manager or veterinarian, can_approve_proposals=manager or veterinarian, own_issuer_only=veterinarian)


def series_pending_reasons(series: FiscalSeries, issuer: FiscalIssuer | None, policy: FiscalPolicy | None) -> list[str]:
    reasons = []
    if policy is None or not policy.enabled:
        reasons.append("El módulo fiscal está desactivado")
    if not series.is_active:
        reasons.append("La serie está inactiva")
    if issuer is None or not issuer.is_active:
        reasons.append("El emisor fiscal no está activo")
    if issuer is not None:
        responsible = issuer.user
        if responsible is None or responsible.tenant_id != issuer.tenant_id or not responsible.is_active or responsible.role != Role.MEDICO_VETERINARIO.value:
            reasons.append("El usuario responsable del emisor debe ser un veterinario activo de la clínica")
        if series.concept in (2, 3) and (not issuer.can_issue_service_receipt_c or issuer.service_document_type != series.document_type):
            reasons.append("El emisor no tiene la capacidad de servicios requerida para este comprobante")
        if series.concept in (1, 3) and (not issuer.can_issue_product_invoice_c or issuer.product_document_type != series.document_type):
            reasons.append("El emisor no tiene la capacidad de productos requerida para este comprobante")
    if issuer is None or not issuer.cuit or not issuer.legal_name or not issuer.tax_condition:
        reasons.append("Completa CUIT, razón fiscal y condición fiscal del emisor")
    else:
        try:
            normalize_cuit(issuer.cuit)
        except ValueError:
            reasons.append("El CUIT del emisor no es válido")
        if series.cuit_snapshot != issuer.cuit:
            reasons.append("La identidad fiscal cambió; revisa y guarda la serie nuevamente")
    if not series.credential_reference:
        reasons.append("Falta una referencia opaca a las credenciales; no cargues secretos")
    if series.authorization_mode == "CAEA" and not series.caea_reference:
        reasons.append("Falta la referencia opaca de configuración CAEA")
    if series.environment == "production":
        if policy is None or policy.accounting_reviewed_at is None:
            reasons.append("Falta la revisión contable de la política fiscal")
        reasons.append("La emisión externa en producción permanece bloqueada")
    return reasons


class FiscalConfigurationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = FiscalConfigurationRepository(db)
        self.issuers = FiscalIssuerRepository(db)

    def policy_read(self, tenant_id: uuid.UUID, policy: FiscalPolicy | None = None) -> FiscalPolicyRead:
        policy = policy or self.repository.policy(tenant_id)
        result = FiscalPolicyRead.model_validate(policy) if policy else FiscalPolicyRead()
        # ARCA.1 never claims that production or external issuance is enabled.
        result.production_blocked = True
        result.review_history = [FiscalPolicyReviewRead.model_validate(row) for row in self.db.scalars(select(FiscalPolicyReview).where(FiscalPolicyReview.tenant_id == tenant_id).order_by(FiscalPolicyReview.reviewed_at.desc(), FiscalPolicyReview.id))]
        return result

    def series_read(self, tenant_id: uuid.UUID, series: FiscalSeries, policy: FiscalPolicy | None = None) -> FiscalSeriesRead:
        issuer = self.issuers.get_by_id(tenant_id, series.fiscal_issuer_id)
        reasons = series_pending_reasons(series, issuer, policy or self.repository.policy(tenant_id))
        result = FiscalSeriesRead.model_validate(series)
        result.pending_reasons = reasons
        result.readiness = "pending" if reasons else "ready"
        return result

    def configuration(self, context: TenantContext) -> FiscalConfigurationRead:
        authorize_fiscal_context(self.db, context)
        tenant_id = context.tenant_id
        policy = self.repository.policy(tenant_id)
        issuer_list = self.issuers.list(tenant_id, active_only=False)
        issuer_ids = {issuer.id for issuer in issuer_list}
        methods = []
        for method in self.repository.payment_methods(tenant_id):
            read = PaymentMethodRead.model_validate(method)
            # Hide inconsistent old relationships as well as validating new links.
            if read.suggested_fiscal_issuer_id not in issuer_ids:
                read.suggested_fiscal_issuer_id = None
            methods.append(read)
        return FiscalConfigurationRead(
            policy=self.policy_read(tenant_id, policy),
            issuers=[FiscalIssuerRead.model_validate(issuer) for issuer in issuer_list],
            series=[self.series_read(tenant_id, row, policy) for row in self.repository.series(tenant_id) if row.fiscal_issuer_id in issuer_ids],
            payment_methods=methods,
            permissions=fiscal_permissions(context),
        )

    def update_policy(self, context: TenantContext, payload: FiscalPolicyUpdate) -> FiscalPolicyRead:
        actor = authorize_fiscal_context(self.db, context, manage=True)
        changes = payload.model_dump(exclude_unset=True)
        if any(value is None for value in changes.values()):
            raise AppError(422, "fiscal_policy_invalid", "Los campos de política enviados no pueden ser null")
        try:
            # Serializes first creation as well as updates for this tenant.
            self.db.scalar(select(Tenant).where(Tenant.id == context.tenant_id).with_for_update())
            policy = self.repository.policy(context.tenant_id, for_update=True)
            if policy is None:
                policy = FiscalPolicy(tenant_id=context.tenant_id, enabled=False, payment_scope="electronic_only", revision=1)
                self.db.add(policy)
                self.db.flush()
            operative_change = any(field in changes and changes[field] != getattr(policy, field) for field in ("enabled", "payment_scope"))
            if changes:
                policy.revision += 1
            for field in ("enabled", "payment_scope"):
                if field in changes:
                    setattr(policy, field, changes[field])
            if operative_change:
                policy.accounting_reviewed_at = None
                policy.accounting_reviewed_by_user_id = None
                policy.accounting_review_note = None
            if "accounting_review_note" in changes:
                now = datetime.now(UTC)
                policy.accounting_reviewed_at = now
                policy.accounting_reviewed_by_user_id = actor.id
                policy.accounting_review_note = changes["accounting_review_note"]
                self.db.add(FiscalPolicyReview(tenant_id=context.tenant_id, policy_id=policy.id, policy_revision=policy.revision, payment_scope=policy.payment_scope, enabled=policy.enabled, reviewed_at=now, reviewed_by_user_id=actor.id, note=changes["accounting_review_note"]))
            policy.updated_at = datetime.now(UTC)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self.policy_read(context.tenant_id)

    def create_series(self, context: TenantContext, payload: FiscalSeriesCreate) -> FiscalSeriesRead:
        actor = authorize_fiscal_context(self.db, context, manage=True)
        issuer = self._issuer(context.tenant_id, payload.fiscal_issuer_id)
        row = FiscalSeries(tenant_id=context.tenant_id, cuit_snapshot=issuer.cuit, revision=1, created_by_user_id=actor.id, updated_by_user_id=actor.id, **payload.model_dump())
        try:
            self.db.add(row)
            self.db.flush()
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise AppError(409, "fiscal_series_duplicate", "Ya existe una serie para ese CUIT, ambiente, punto de venta y tipo de comprobante") from exc
        except Exception:
            self.db.rollback()
            raise
        return self.series_read(context.tenant_id, row)

    def update_series(self, context: TenantContext, series_id: uuid.UUID, payload: FiscalSeriesUpdate) -> FiscalSeriesRead:
        actor = authorize_fiscal_context(self.db, context, manage=True)
        try:
            row = self.repository.get_series(context.tenant_id, series_id, for_update=True)
            if row is None:
                raise AppError(404, "fiscal_series_not_found", "Serie fiscal no encontrada")
            values = {name: getattr(row, name) for name in FiscalSeriesCreate.model_fields}
            values.update(payload.model_dump(exclude_unset=True))
            try:
                validated = FiscalSeriesCreate.model_validate(values)
            except ValidationError as exc:
                raise AppError(422, "fiscal_series_invalid", "La configuración de la serie no es válida") from exc
            issuer = self._issuer(context.tenant_id, validated.fiscal_issuer_id)
            for field, value in validated.model_dump().items():
                setattr(row, field, value)
            row.cuit_snapshot = issuer.cuit
            row.revision += 1
            row.updated_by_user_id = actor.id
            row.updated_at = datetime.now(UTC)
            self.db.flush()
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise AppError(409, "fiscal_series_duplicate", "Ya existe una serie para ese CUIT, ambiente, punto de venta y tipo de comprobante") from exc
        except Exception:
            self.db.rollback()
            raise
        return self.series_read(context.tenant_id, row)

    def _issuer(self, tenant_id: uuid.UUID, issuer_id: uuid.UUID) -> FiscalIssuer:
        issuer = self.issuers.get_by_id(tenant_id, issuer_id)
        if issuer is None:
            raise AppError(404, "fiscal_issuer_not_found", "Emisor fiscal no encontrado")
        return issuer

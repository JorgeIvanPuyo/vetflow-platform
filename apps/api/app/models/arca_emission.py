"""Durable fiscal work. Global series ownership is internal, never a browse API."""
from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, JSON, String, Text, UniqueConstraint, Uuid, event, inspect, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.errors import AppError
from app.models.base import BaseModel


class ArcaSeriesOwnership(BaseModel):
    """Exclusive remote numbering scope; only scoped ownership checks may use it."""
    __tablename__ = "arca_series_ownership"
    __table_args__ = (
        UniqueConstraint("series_key", name="uq_arca_series_remote_identity"),
        UniqueConstraint("environment", "cuit", "point_of_sale", "document_type", name="uq_arca_series_remote_coordinates"),
        UniqueConstraint("tenant_id", "id", name="uq_arca_series_owner_tenant"),
        ForeignKeyConstraint(["tenant_id", "active_intent_id"], ["arca_emission_intents.tenant_id", "arca_emission_intents.id"], name="fk_arca_series_active_intent", use_alter=True, ondelete="RESTRICT"),
        CheckConstraint("environment = 'homologation'", name="ck_arca_series_owner_environment"),
        CheckConstraint("fence >= 0", name="ck_arca_series_owner_fence"),
        CheckConstraint("point_of_sale BETWEEN 1 AND 99999 AND document_type IN (11,15) AND length(cuit) = 11 AND length(series_key) = 64", name="ck_arca_series_remote_coordinates"),
        CheckConstraint("(lease_owner IS NULL AND lease_until IS NULL) OR (lease_owner IS NOT NULL AND lease_until IS NOT NULL)", name="ck_arca_series_lease_pair"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    series_key: Mapped[str] = mapped_column(String(64), nullable=False)
    environment: Mapped[str] = mapped_column(String(20), nullable=False)
    cuit: Mapped[str] = mapped_column(String(11), nullable=False)
    point_of_sale: Mapped[int] = mapped_column(Integer, nullable=False)
    document_type: Mapped[int] = mapped_column(Integer, nullable=False)
    active_intent_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    lease_owner: Mapped[str | None] = mapped_column(String(64))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fence: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")


class ArcaEmissionIntent(BaseModel):
    __tablename__ = "arca_emission_intents"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_arca_emission_tenant_id"),
        UniqueConstraint("tenant_id", "sale_id", "id", name="uq_arca_emission_membership"),
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_arca_emission_intent_key"),
        Index("uq_arca_emission_remote_number", "series_owner_id", "number", unique=True, postgresql_where=text("state <> 'rejected'"), sqlite_where=text("state <> 'rejected'")),
        ForeignKeyConstraint(["tenant_id", "sale_id", "proposal_id"], ["fiscal_proposals.tenant_id", "fiscal_proposals.sale_id", "fiscal_proposals.id"], name="fk_arca_emission_proposal", ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "series_owner_id"], ["arca_series_ownership.tenant_id", "arca_series_ownership.id"], name="fk_arca_emission_series_owner", ondelete="RESTRICT"),
        CheckConstraint("state IN ('prepared','processing','unknown','conflict','rejected','authorized')", name="ck_arca_emission_state"),
        CheckConstraint("environment = 'homologation'", name="ck_arca_emission_environment"),
        CheckConstraint("file_status IN ('pending','ready','failed')", name="ck_arca_emission_file_state"),
        CheckConstraint("(number IS NULL AND request_payload IS NULL AND request_hash IS NULL) OR (number IS NOT NULL AND number > 0 AND request_payload IS NOT NULL AND request_hash IS NOT NULL AND length(request_hash) = 64)", name="ck_arca_emission_persisted_request"),
        CheckConstraint("state <> 'authorized' OR (cae IS NOT NULL AND length(cae) = 14 AND cae_expiry IS NOT NULL AND document_id IS NOT NULL AND number IS NOT NULL)", name="ck_arca_emission_authorization"),
        CheckConstraint("length(intent_fingerprint) = 64 AND length(approval_content_hash) = 64 AND length(idempotency_key) BETWEEN 1 AND 128 AND claim_fence >= 0", name="ck_arca_emission_identity"),
        CheckConstraint("(claim_owner IS NULL AND claim_until IS NULL) OR (claim_owner IS NOT NULL AND claim_until IS NOT NULL)", name="ck_arca_emission_claim_pair"),
        Index("uq_arca_emission_current_proposal", "tenant_id", "proposal_id", unique=True, postgresql_where=text("is_current"), sqlite_where=text("is_current = 1")),
        Index("ix_arca_emission_tenant_sale", "tenant_id", "sale_id"),
        Index("ix_arca_emission_pending", "tenant_id", "state", "next_action_at"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    sale_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    proposal_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    fiscal_issuer_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("fiscal_issuers.id", ondelete="RESTRICT"), nullable=False)
    fiscal_series_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("fiscal_series.id", ondelete="RESTRICT"), nullable=False)
    series_owner_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    environment: Mapped[str] = mapped_column(String(20), nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False, default="prepared", server_default="prepared", active_history=True)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("arca_emission_intents.id", ondelete="RESTRICT"))
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    intent_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    approval_content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    business_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    credential_reference: Mapped[str] = mapped_column(String(220), nullable=False)
    number: Mapped[int | None] = mapped_column(Integer, active_history=True)
    request_payload: Mapped[dict | None] = mapped_column(JSON(none_as_null=True), active_history=True)
    request_hash: Mapped[str | None] = mapped_column(String(64), active_history=True)
    claim_owner: Mapped[str | None] = mapped_column(String(64))
    claim_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    claim_fence: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    next_action_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_diagnostic: Mapped[str | None] = mapped_column(String(120))
    diagnostics: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    cae: Mapped[str | None] = mapped_column(String(14), active_history=True)
    cae_expiry: Mapped[date | None] = mapped_column(Date, active_history=True)
    document_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("sale_fiscal_documents.id", ondelete="RESTRICT"), active_history=True)
    file_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", server_default="pending")
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)


class ArcaEmissionAttempt(BaseModel):
    __tablename__ = "arca_emission_attempts"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "emission_id"], ["arca_emission_intents.tenant_id", "arca_emission_intents.id"], name="fk_arca_attempt_emission", ondelete="RESTRICT"),
        Index("ix_arca_attempt_tenant_emission", "tenant_id", "emission_id"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    emission_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    outcome: Mapped[str] = mapped_column(String(120), nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    fence: Mapped[int] = mapped_column(Integer, nullable=False)


class ArcaDocumentFile(BaseModel):
    __tablename__ = "arca_document_files"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "emission_id"], ["arca_emission_intents.tenant_id", "arca_emission_intents.id"], name="fk_arca_file_emission", ondelete="RESTRICT"),
        Index("ix_arca_file_tenant_emission", "tenant_id", "emission_id"),
        CheckConstraint("environment = 'homologation' AND length(sha256) = 64 AND size_bytes > 0", name="ck_arca_file_identity"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    emission_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("sale_fiscal_documents.id", ondelete="RESTRICT"), nullable=False)
    environment: Mapped[str] = mapped_column(String(20), nullable=False)
    bucket_name: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)


class ArcaParameterCache(BaseModel):
    __tablename__ = "arca_parameter_cache"
    __table_args__ = (UniqueConstraint("tenant_id", "scope_key", name="uq_arca_parameter_scope"),)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    scope_key: Mapped[str] = mapped_column(String(64), nullable=False)
    environment: Mapped[str] = mapped_column(String(20), nullable=False)
    cuit: Mapped[str] = mapped_column(String(11), nullable=False)
    method: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[list[dict]] = mapped_column(JSON, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


@event.listens_for(ArcaEmissionIntent, "before_update")
def freeze_emission_request(_mapper, _connection, intent):
    state = inspect(intent)
    immutable = ("tenant_id", "sale_id", "proposal_id", "fiscal_issuer_id", "fiscal_series_id", "series_owner_id", "environment", "business_snapshot", "credential_reference", "intent_fingerprint", "approval_content_hash", "idempotency_key", "supersedes_id")
    if any(state.attrs[key].history.has_changes() for key in immutable):
        raise AppError(409, "arca_intent_immutable", "La intención fiscal es inmutable; un rechazo requiere una corrección explícita nueva")
    for key in ("number", "request_payload", "request_hash", "cae", "cae_expiry", "document_id"):
        history = state.attrs[key].history
        if history.has_changes() and history.deleted and history.deleted[0] is not None:
            raise AppError(409, "arca_request_immutable", "El número, solicitud y autorización persistidos no pueden sustituirse")
    previous = state.attrs.state.history.deleted
    if previous and previous[0] == "authorized" and intent.state != "authorized":
        raise AppError(409, "arca_authorization_immutable", "La autorización fiscal no puede revertirse como estado local")


@event.listens_for(ArcaEmissionIntent, "before_delete")
def preserve_emission(_mapper, _connection, _intent):
    raise AppError(409, "arca_audit_required", "Las intenciones de emisión conservan su historial")


@event.listens_for(ArcaDocumentFile, "before_update")
@event.listens_for(ArcaEmissionAttempt, "before_update")
def preserve_arca_audit_content(_mapper, _connection, record):
    state = inspect(record)
    if any(state.attrs[column.key].history.has_changes() for column in state.mapper.column_attrs):
        raise AppError(409, "arca_audit_immutable", "El historial fiscal es inmutable; conserva la versión anterior y registra una entrada nueva")


@event.listens_for(ArcaDocumentFile, "before_delete")
@event.listens_for(ArcaEmissionAttempt, "before_delete")
def preserve_arca_audit_history(_mapper, _connection, _record):
    raise AppError(409, "arca_audit_required", "Las versiones y los intentos fiscales deben conservarse en el historial")

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, JSON, Numeric, String, Text, UniqueConstraint, Uuid, event, inspect, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.errors import AppError
from app.models.base import BaseModel


class FiscalProposal(BaseModel):
    __tablename__ = "fiscal_proposals"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_fiscal_proposals_tenant_id"),
        UniqueConstraint("tenant_id", "sale_id", "id", name="uq_fiscal_proposals_membership"),
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_fiscal_proposals_approval_key"),
        ForeignKeyConstraint(["tenant_id", "sale_id"], ["sales.tenant_id", "sales.id"], name="fk_fiscal_proposals_tenant_sale", ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "fiscal_series_id"], ["fiscal_series.tenant_id", "fiscal_series.id"], name="fk_fiscal_proposals_tenant_series", ondelete="RESTRICT"),
        CheckConstraint("status IN ('draft','approved','cancelled','sent','unknown','authorized','rejected','caea_pending')", name="ck_fiscal_proposals_status"),
        CheckConstraint("currency = 'ARS' AND total_ars > 0", name="ck_fiscal_proposals_money"),
        CheckConstraint("concept IN (1,2,3)", name="ck_fiscal_proposals_concept"),
        CheckConstraint("length(content_hash) = 64 AND length(source_snapshot_hash) = 64", name="ck_fiscal_proposals_hashes"),
        CheckConstraint("(status = 'draft' AND approved_at IS NULL) OR status = 'cancelled' OR (status NOT IN ('draft','cancelled') AND approved_at IS NOT NULL)", name="ck_fiscal_proposals_approval_state"),
        CheckConstraint("status <> 'cancelled' OR (cancelled_at IS NOT NULL AND cancelled_by_user_id IS NOT NULL AND cancellation_reason IS NOT NULL)", name="ck_fiscal_proposals_cancellation_audit"),
        CheckConstraint("(approved_at IS NULL AND approved_by_user_id IS NULL AND idempotency_key IS NULL AND approval_request_hash IS NULL) OR (approved_at IS NOT NULL AND approved_by_user_id IS NOT NULL AND idempotency_key IS NOT NULL AND length(approval_request_hash) = 64)", name="ck_fiscal_proposals_approval_identity"),
        Index("ix_fiscal_proposals_tenant_sale", "tenant_id", "sale_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    sale_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    fiscal_issuer_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("fiscal_issuers.id", ondelete="RESTRICT"), nullable=False)
    fiscal_series_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", server_default="draft", active_history=True)
    payment_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    fiscal_description: Mapped[str] = mapped_column(Text, nullable=False)
    total_ars: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="ARS")
    concept: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    source_snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    updated_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    approval_request_hash: Mapped[str | None] = mapped_column(String(64))
    cancelled_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancellation_reason: Mapped[str | None] = mapped_column(Text)
    audit_log: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)


class FiscalPaymentAllocation(BaseModel):
    __tablename__ = "fiscal_payment_allocations"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "sale_id", "proposal_id"], ["fiscal_proposals.tenant_id", "fiscal_proposals.sale_id", "fiscal_proposals.id"], name="fk_fiscal_allocations_proposal", ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "sale_id", "payment_id"], ["sale_payments.tenant_id", "sale_payments.sale_id", "sale_payments.id"], name="fk_fiscal_allocations_payment", ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "sale_id", "fiscal_document_id"], ["sale_fiscal_documents.tenant_id", "sale_fiscal_documents.sale_id", "sale_fiscal_documents.id"], name="fk_fiscal_allocations_document", ondelete="RESTRICT"),
        CheckConstraint("amount_ars > 0", name="ck_fiscal_allocations_positive"),
        CheckConstraint("(proposal_id IS NOT NULL AND fiscal_document_id IS NULL) OR (proposal_id IS NULL AND fiscal_document_id IS NOT NULL)", name="ck_fiscal_allocations_owner"),
        CheckConstraint("(is_active AND released_at IS NULL AND released_by_user_id IS NULL AND release_reason IS NULL) OR (NOT is_active AND released_at IS NOT NULL AND released_by_user_id IS NOT NULL AND release_reason IS NOT NULL)", name="ck_fiscal_allocations_release"),
        Index("uq_fiscal_allocations_active_payment", "tenant_id", "payment_id", unique=True, postgresql_where=text("is_active"), sqlite_where=text("is_active = 1")),
        Index("ix_fiscal_allocations_tenant_sale", "tenant_id", "sale_id"),
        Index("ix_fiscal_allocations_tenant_proposal", "tenant_id", "proposal_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    sale_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("sales.id", ondelete="RESTRICT"), nullable=False)
    proposal_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    fiscal_document_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("sale_fiscal_documents.id", ondelete="RESTRICT"))
    payment_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    amount_ars: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    reserved_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    reserved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    released_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"))
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    release_reason: Mapped[str | None] = mapped_column(Text)


@event.listens_for(FiscalProposal, "before_update")
def freeze_approved_content(_mapper, _connection, proposal):
    state = inspect(proposal)
    old_status = state.attrs.status.history.deleted
    previously_frozen = (old_status[0] if old_status else proposal.status) != "draft"
    if previously_frozen and proposal.status == "draft":
        raise AppError(409, "fiscal_proposal_frozen", "Una propuesta aprobada o cancelada no puede volver a borrador")
    frozen_fields = ("tenant_id", "sale_id", "fiscal_issuer_id", "fiscal_series_id", "payment_ids", "fiscal_description", "total_ars", "currency", "concept", "snapshot", "source_snapshot_hash", "content_hash", "idempotency_key", "approval_request_hash", "approved_at", "approved_by_user_id")
    if previously_frozen and any(state.attrs[field].history.has_changes() for field in frozen_fields):
        raise AppError(409, "fiscal_proposal_frozen", "El contenido aprobado es inmutable; cancela la reserva no enviada y crea una intención nueva")


@event.listens_for(FiscalProposal, "before_delete")
def preserve_proposal_audit(_mapper, _connection, _proposal):
    raise AppError(409, "fiscal_proposal_audit_required", "Las propuestas se cancelan explícitamente y conservan su trazabilidad")

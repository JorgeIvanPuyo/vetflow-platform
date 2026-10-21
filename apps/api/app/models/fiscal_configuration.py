from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class FiscalPolicy(BaseModel):
    __tablename__ = "fiscal_policies"
    __table_args__ = (
        UniqueConstraint("tenant_id", name="uq_fiscal_policies_tenant"),
        CheckConstraint("payment_scope IN ('electronic_only', 'all_payments')", name="ck_fiscal_policies_scope"),
        CheckConstraint("revision > 0", name="ck_fiscal_policies_revision"),
        CheckConstraint(
            "(accounting_reviewed_at IS NULL AND accounting_reviewed_by_user_id IS NULL AND accounting_review_note IS NULL) OR "
            "(accounting_reviewed_at IS NOT NULL AND accounting_reviewed_by_user_id IS NOT NULL AND accounting_review_note IS NOT NULL)",
            name="ck_fiscal_policies_accounting_review",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    payment_scope: Mapped[str] = mapped_column(String(30), nullable=False, default="electronic_only", server_default="electronic_only")
    accounting_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accounting_reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"))
    accounting_review_note: Mapped[str | None] = mapped_column(Text)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


class FiscalSeries(BaseModel):
    __tablename__ = "fiscal_series"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_fiscal_series_tenant_id"),
        UniqueConstraint("tenant_id", "cuit_snapshot", "environment", "point_of_sale", "document_type", name="uq_fiscal_series_identity"),
        UniqueConstraint("tenant_id", "fiscal_issuer_id", "environment", "point_of_sale", "document_type", name="uq_fiscal_series_issuer_identity"),
        CheckConstraint("environment IN ('homologation', 'production')", name="ck_fiscal_series_environment"),
        CheckConstraint("point_of_sale BETWEEN 1 AND 99999", name="ck_fiscal_series_point_of_sale"),
        CheckConstraint("document_type IN ('receipt_c', 'invoice_c')", name="ck_fiscal_series_document_type"),
        CheckConstraint("concept IN (1, 2, 3)", name="ck_fiscal_series_concept"),
        CheckConstraint("authorization_mode IN ('CAE', 'CAEA')", name="ck_fiscal_series_authorization_mode"),
        CheckConstraint("revision > 0", name="ck_fiscal_series_revision"),
        Index("ix_fiscal_series_tenant_issuer", "tenant_id", "fiscal_issuer_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    fiscal_issuer_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("fiscal_issuers.id", ondelete="RESTRICT"), nullable=False)
    # Null keeps historical/incomplete identities pending; never invent a CUIT.
    cuit_snapshot: Mapped[str | None] = mapped_column(String(11))
    environment: Mapped[str] = mapped_column(String(20), nullable=False, default="homologation", server_default="homologation")
    point_of_sale: Mapped[int] = mapped_column(Integer, nullable=False)
    document_type: Mapped[str] = mapped_column(String(30), nullable=False)
    concept: Mapped[int] = mapped_column(Integer, nullable=False)
    authorization_mode: Mapped[str] = mapped_column(String(4), nullable=False, default="CAE", server_default="CAE")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    credential_reference: Mapped[str | None] = mapped_column(String(220))
    caea_reference: Mapped[str | None] = mapped_column(String(220))
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    updated_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)


class FiscalPolicyReview(BaseModel):
    """Append-only evidence, retained when the operative policy changes."""

    __tablename__ = "fiscal_policy_reviews"
    __table_args__ = (Index("ix_fiscal_policy_reviews_tenant_policy", "tenant_id", "policy_id"),)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    policy_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("fiscal_policies.id", ondelete="RESTRICT"), nullable=False)
    policy_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    payment_scope: Mapped[str] = mapped_column(String(30), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reviewed_by_user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False)

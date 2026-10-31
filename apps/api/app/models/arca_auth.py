"""Internal authentication coordination, separate from tenant fiscal data.

ArcaAuthCache is deliberately global: WSAA authenticates a certificate/service,
not an individual represented CUIT. Only server-authorized auth scopes can use
this repository. Tenant grants are independently authenticated and encrypted.
Neither table has a public or cross-tenant API.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, LargeBinary, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class ArcaAuthCache(BaseModel):
    __tablename__ = "arca_auth_cache"
    __table_args__ = (
        UniqueConstraint("cache_key", name="uq_arca_auth_cache_scope"),
        UniqueConstraint("certificate_fingerprint", "environment", "service", name="uq_arca_auth_remote_identity"),
        CheckConstraint("environment IN ('homologation','production')", name="ck_arca_auth_environment"),
        CheckConstraint("service = 'wsfe'", name="ck_arca_auth_service"),
        CheckConstraint("state IN ('idle','renewing','ready','backoff','blocked')", name="ck_arca_auth_state"),
        CheckConstraint("fence >= 0", name="ck_arca_auth_fence"),
        Index("ix_arca_auth_retry", "state", "retry_not_before"),
    )
    cache_key: Mapped[str] = mapped_column(String(64), nullable=False)
    certificate_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    environment: Mapped[str] = mapped_column(String(20), nullable=False)
    service: Mapped[str] = mapped_column(String(20), nullable=False, default="wsfe")
    auth_scope: Mapped[str] = mapped_column(String(120), nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False, default="idle", server_default="idle")
    encrypted_ticket: Mapped[bytes | None] = mapped_column(LargeBinary)
    encryption_key_version: Mapped[str | None] = mapped_column(String(80))
    encryption_key_scope: Mapped[str | None] = mapped_column(String(120))
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_owner: Mapped[str | None] = mapped_column(String(64))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fence: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    last_request_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retry_not_before: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    diagnostic_code: Mapped[str | None] = mapped_column(String(100))


class ArcaTenantTicketGrant(BaseModel):
    __tablename__ = "arca_tenant_ticket_grants"
    __table_args__ = (
        UniqueConstraint("tenant_id", "reference", "environment", "represented_cuit", name="uq_arca_tenant_ticket_grant"),
        Index("ix_arca_ticket_grants_tenant_cache", "tenant_id", "cache_id"),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    reference: Mapped[str] = mapped_column(String(220), nullable=False)
    environment: Mapped[str] = mapped_column(String(20), nullable=False)
    represented_cuit: Mapped[str] = mapped_column(String(11), nullable=False)
    cache_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("arca_auth_cache.id", ondelete="RESTRICT"), nullable=False)
    encrypted_ticket: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    encryption_key_version: Mapped[str] = mapped_column(String(80), nullable=False)
    encryption_key_scope: Mapped[str] = mapped_column(String(120), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

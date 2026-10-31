from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    event,
    inspect,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class FiscalIssuer(BaseModel):
    __tablename__ = "fiscal_issuers"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "user_id", name="uq_fiscal_issuers_tenant_user"
        ),
        CheckConstraint(
            "service_document_type IS NULL OR "
            "service_document_type IN ('receipt_c', 'invoice_c')",
            name="ck_fiscal_issuers_service_document_type",
        ),
        CheckConstraint(
            "product_document_type IS NULL OR "
            "product_document_type IN ('receipt_c', 'invoice_c')",
            name="ck_fiscal_issuers_product_document_type",
        ),
        CheckConstraint(
            "(can_issue_service_receipt_c AND service_document_type IS NOT NULL "
            "AND service_document_code IS NOT NULL) OR "
            "(NOT can_issue_service_receipt_c AND service_document_type IS NULL "
            "AND service_document_code IS NULL)",
            name="ck_fiscal_issuers_service_configuration",
        ),
        CheckConstraint(
            "(can_issue_product_invoice_c AND product_document_type IS NOT NULL "
            "AND product_document_code IS NOT NULL) OR "
            "(NOT can_issue_product_invoice_c AND product_document_type IS NULL "
            "AND product_document_code IS NULL)",
            name="ck_fiscal_issuers_product_configuration",
        ),
        CheckConstraint(
            "can_issue_service_receipt_c OR can_issue_product_invoice_c",
            name="ck_fiscal_issuers_has_capability",
        ),
        Index("ix_fiscal_issuers_tenant_active", "tenant_id", "is_active"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    tax_id: Mapped[str] = mapped_column(String(80), nullable=False)
    # Argentine identity is optional for historical/manual issuers and is never
    # inferred from tax_id, whose existing international contract is retained.
    cuit: Mapped[str | None] = mapped_column(String(11))
    legal_name: Mapped[str | None] = mapped_column(String(255))
    tax_condition: Mapped[str | None] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    can_issue_service_receipt_c: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    can_issue_product_invoice_c: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    service_document_type: Mapped[str | None] = mapped_column(String(30))
    service_document_code: Mapped[str | None] = mapped_column(String(20))
    product_document_type: Mapped[str | None] = mapped_column(String(30))
    product_document_code: Mapped[str | None] = mapped_column(String(20))

    user: Mapped[User] = relationship("User", foreign_keys=[user_id])
    fiscal_documents: Mapped[list[SaleFiscalDocument]] = relationship(
        "SaleFiscalDocument", back_populates="fiscal_issuer"
    )

    @property
    def user_name(self) -> str | None:
        return self.user.full_name if self.user is not None and self.user.tenant_id == self.tenant_id else None

    @property
    def user_email(self) -> str | None:
        return self.user.email if self.user is not None and self.user.tenant_id == self.tenant_id else None


class SaleFiscalDocument(BaseModel):
    __tablename__ = "sale_fiscal_documents"
    __table_args__ = (
        UniqueConstraint("tenant_id", "sale_id", "id", name="uq_sale_fiscal_documents_membership"),
        UniqueConstraint("tenant_id", "allocation_idempotency_key", name="uq_sale_fiscal_documents_allocation_key"),
        CheckConstraint(
            "document_type IN ('receipt_c', 'invoice_c')",
            name="ck_sale_fiscal_documents_type",
        ),
        CheckConstraint(
            "total_ars_snapshot >= 0", name="ck_sale_fiscal_documents_total"
        ),
        CheckConstraint(
            "source IN ('manual', 'arca')", name="ck_sale_fiscal_documents_source"
        ),
        CheckConstraint(
            "authorization_status IN ('manual', 'pending', 'unknown', 'authorized', "
            "'rejected', 'caea_pending')",
            name="ck_sale_fiscal_documents_authorization_status",
        ),
        CheckConstraint(
            "(source = 'manual' AND authorization_status = 'manual') OR "
            "(source = 'arca' AND authorization_status <> 'manual')",
            name="ck_sale_fiscal_documents_source_authorization",
        ),
        CheckConstraint(
            "authorization_status <> 'authorized' OR is_active",
            name="ck_sale_fiscal_documents_authorized_active",
        ),
        CheckConstraint(
            "source <> 'manual' OR (original_filename IS NOT NULL AND bucket_name IS NOT NULL "
            "AND storage_key IS NOT NULL AND content_type IS NOT NULL AND size_bytes IS NOT NULL "
            "AND sha256 IS NOT NULL AND uploaded_at IS NOT NULL)",
            name="ck_sale_fiscal_documents_manual_attachment",
        ),
        CheckConstraint("size_bytes > 0", name="ck_sale_fiscal_documents_size"),
        CheckConstraint("length(sha256) = 64", name="ck_sale_fiscal_documents_sha256"),
        Index("uq_sale_fiscal_documents_manual_number", "tenant_id", "fiscal_issuer_id", "document_type", "document_number", unique=True, postgresql_where=text("source = 'manual'"), sqlite_where=text("source = 'manual'")),
        Index("uq_sale_fiscal_documents_arca_number", "tenant_id", "environment", "fiscal_issuer_id", "document_type", "document_number", unique=True, postgresql_where=text("source = 'arca'"), sqlite_where=text("source = 'arca'")),
        UniqueConstraint("emission_intent_id", name="uq_sale_fiscal_document_emission"),
        Index(
            "uq_sale_fiscal_documents_active_manual_sale",
            "tenant_id",
            "sale_id",
            unique=True,
            postgresql_where=text("is_active AND source = 'manual'"),
            sqlite_where=text("is_active = 1 AND source = 'manual'"),
        ),
        Index("ix_sale_fiscal_documents_tenant_sale", "tenant_id", "sale_id"),
        Index(
            "ix_sale_fiscal_documents_tenant_issuer",
            "tenant_id",
            "fiscal_issuer_id",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    allocation_idempotency_key: Mapped[str | None] = mapped_column(String(128))
    allocation_request_hash: Mapped[str | None] = mapped_column(String(64))
    allocation_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    allocation_reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"))
    environment: Mapped[str | None] = mapped_column(String(20))
    cae: Mapped[str | None] = mapped_column(String(14))
    cae_expiry: Mapped[date | None] = mapped_column(Date)
    authorization_snapshot: Mapped[dict | None] = mapped_column(JSON(none_as_null=True), active_history=True)
    emission_intent_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("arca_emission_intents.id", name="fk_sale_fiscal_document_emission", use_alter=True, ondelete="RESTRICT"))
    sale_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("sales.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    fiscal_issuer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("fiscal_issuers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    issuer_user_id_snapshot: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False
    )
    issuer_name_snapshot: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    issuer_tax_id_snapshot: Mapped[str] = mapped_column(String(80), nullable=False)
    source: Mapped[str] = mapped_column(
        String(20), nullable=False, default="manual", server_default="manual"
    )
    authorization_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="manual", server_default="manual", active_history=True
    )
    document_type: Mapped[str] = mapped_column(String(30), nullable=False)
    document_code: Mapped[str] = mapped_column(String(20), nullable=False)
    document_number: Mapped[str] = mapped_column(String(120), nullable=False)
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_ars_snapshot: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(255))
    bucket_name: Mapped[str | None] = mapped_column(String(255))
    storage_key: Mapped[str | None] = mapped_column(Text)
    content_type: Mapped[str | None] = mapped_column(String(100))
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    sha256: Mapped[str | None] = mapped_column(String(64))
    uploaded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    sale: Mapped[Sale] = relationship("Sale", back_populates="fiscal_documents")
    fiscal_issuer: Mapped[FiscalIssuer] = relationship(
        "FiscalIssuer", back_populates="fiscal_documents"
    )
    uploaded_by_user: Mapped[User | None] = relationship(
        "User", foreign_keys=[uploaded_by_user_id]
    )
    file_history: Mapped[list[SaleFiscalDocumentFileVersion]] = relationship(
        "SaleFiscalDocumentFileVersion",
        back_populates="fiscal_document",
        cascade="all, delete-orphan",
        order_by="desc(SaleFiscalDocumentFileVersion.replaced_at)",
    )

    @property
    def uploaded_by_user_name(self) -> str | None:
        if self.uploaded_by_user is None or self.uploaded_by_user.tenant_id != self.tenant_id:
            return None
        return self.uploaded_by_user.full_name

    @property
    def uploaded_by_user_email(self) -> str | None:
        if self.uploaded_by_user is None or self.uploaded_by_user.tenant_id != self.tenant_id:
            return None
        return self.uploaded_by_user.email


class SaleFiscalDocumentFileVersion(BaseModel):
    __tablename__ = "sale_fiscal_document_file_versions"
    __table_args__ = (
        CheckConstraint(
            "size_bytes > 0", name="ck_sale_fiscal_document_versions_size"
        ),
        CheckConstraint(
            "length(sha256) = 64", name="ck_sale_fiscal_document_versions_sha256"
        ),
        Index(
            "ix_sale_fiscal_document_versions_tenant_document",
            "tenant_id",
            "fiscal_document_id",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    fiscal_document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("sale_fiscal_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    bucket_name: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    uploaded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    replaced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    replaced_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    fiscal_document: Mapped[SaleFiscalDocument] = relationship(
        "SaleFiscalDocument", back_populates="file_history"
    )
    replaced_by_user: Mapped[User | None] = relationship(
        "User", foreign_keys=[replaced_by_user_id]
    )

    @property
    def replaced_by_user_name(self) -> str | None:
        if self.replaced_by_user is None or self.replaced_by_user.tenant_id != self.tenant_id:
            return None
        return self.replaced_by_user.full_name

    @property
    def replaced_by_user_email(self) -> str | None:
        if self.replaced_by_user is None or self.replaced_by_user.tenant_id != self.tenant_id:
            return None
        return self.replaced_by_user.email


_FISCAL_DOCUMENT_IDENTITY_FIELDS = (
    "tenant_id", "sale_id", "fiscal_issuer_id", "issuer_user_id_snapshot",
    "issuer_name_snapshot", "issuer_tax_id_snapshot", "source", "document_type",
    "document_code", "document_number", "issue_date", "total_ars_snapshot",
    "environment", "cae", "cae_expiry", "authorization_snapshot", "emission_intent_id",
)


@event.listens_for(SaleFiscalDocument, "before_update")
def _protect_authorized_document_identity(mapper, connection, document):
    """ARCA identities are permanent, including during future status transitions."""
    state = inspect(document)
    previous = state.attrs.authorization_status.history.deleted
    was_authorized = "authorized" in previous or (
        document.authorization_status == "authorized"
        and not state.attrs.authorization_status.history.has_changes()
    )
    if not was_authorized:
        return
    from app.core.errors import AppError

    if any(state.attrs[field].history.has_changes() for field in _FISCAL_DOCUMENT_IDENTITY_FIELDS):
        raise AppError(
            409, "fiscal_document_identity_immutable",
            "La identidad de un comprobante autorizado no puede modificarse",
        )
    if not document.is_active:
        raise AppError(
            409, "fiscal_document_authorized_cannot_deactivate",
            "Un comprobante autorizado requiere el circuito fiscal de reversión; no puede desactivarse",
        )
    if document.authorization_status != "authorized":
        raise AppError(
            409, "fiscal_document_authorization_immutable",
            "La autorización remota no puede eliminarse ni sustituirse",
        )


@event.listens_for(SaleFiscalDocument, "before_delete")
def _protect_authorized_document_delete(mapper, connection, document):
    previous = inspect(document).attrs.authorization_status.history.deleted
    if document.authorization_status == "authorized" or "authorized" in previous:
        from app.core.errors import AppError

        raise AppError(
            409, "fiscal_document_authorized_cannot_delete",
            "Un comprobante autorizado debe conservarse en el historial fiscal",
        )

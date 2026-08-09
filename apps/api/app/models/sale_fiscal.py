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
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
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
        return self.user.full_name if self.user.tenant_id == self.tenant_id else None

    @property
    def user_email(self) -> str | None:
        return self.user.email if self.user.tenant_id == self.tenant_id else None


class SaleFiscalDocument(BaseModel):
    __tablename__ = "sale_fiscal_documents"
    __table_args__ = (
        CheckConstraint(
            "document_type IN ('receipt_c', 'invoice_c')",
            name="ck_sale_fiscal_documents_type",
        ),
        CheckConstraint(
            "total_ars_snapshot >= 0", name="ck_sale_fiscal_documents_total"
        ),
        CheckConstraint("size_bytes > 0", name="ck_sale_fiscal_documents_size"),
        CheckConstraint("length(sha256) = 64", name="ck_sale_fiscal_documents_sha256"),
        UniqueConstraint(
            "tenant_id",
            "fiscal_issuer_id",
            "document_type",
            "document_number",
            name="uq_sale_fiscal_documents_number",
        ),
        Index(
            "uq_sale_fiscal_documents_active_sale",
            "sale_id",
            unique=True,
            postgresql_where=text("is_active"),
            sqlite_where=text("is_active = 1"),
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
    document_type: Mapped[str] = mapped_column(String(30), nullable=False)
    document_code: Mapped[str] = mapped_column(String(20), nullable=False)
    document_number: Mapped[str] = mapped_column(String(120), nullable=False)
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_ars_snapshot: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    bucket_name: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    uploaded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
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

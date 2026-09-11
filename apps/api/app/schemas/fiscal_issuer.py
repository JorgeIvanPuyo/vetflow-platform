import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


FiscalDocumentType = Literal["receipt_c", "invoice_c"]


class FiscalIssuerCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: uuid.UUID
    display_name: str = Field(min_length=1, max_length=255)
    tax_id: str = Field(min_length=1, max_length=80)
    is_active: bool = True
    can_issue_service_receipt_c: bool = False
    can_issue_product_invoice_c: bool = False
    service_document_type: FiscalDocumentType | None = None
    service_document_code: str | None = Field(default=None, max_length=20)
    product_document_type: FiscalDocumentType | None = None
    product_document_code: str | None = Field(default=None, max_length=20)

    @field_validator(
        "display_name",
        "tax_id",
        "service_document_code",
        "product_document_code",
        mode="before",
    )
    @classmethod
    def normalize_text(cls, value):
        if not isinstance(value, str):
            return value
        return value.strip() or None

    @model_validator(mode="after")
    def validate_capabilities(self):
        if not (
            self.can_issue_service_receipt_c
            or self.can_issue_product_invoice_c
        ):
            raise ValueError("Selecciona al menos una capacidad fiscal")
        pairs = (
            (
                self.can_issue_service_receipt_c,
                self.service_document_type,
                self.service_document_code,
                "servicios",
            ),
            (
                self.can_issue_product_invoice_c,
                self.product_document_type,
                self.product_document_code,
                "productos",
            ),
        )
        for enabled, document_type, code, label in pairs:
            if enabled and (document_type is None or code is None):
                raise ValueError(
                    f"La capacidad de {label} requiere tipo y código de comprobante"
                )
            if not enabled and (document_type is not None or code is not None):
                raise ValueError(
                    f"La configuración de {label} requiere habilitar su capacidad"
                )
        return self


class FiscalIssuerUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: uuid.UUID | None = None
    display_name: str | None = Field(default=None, max_length=255)
    tax_id: str | None = Field(default=None, max_length=80)
    is_active: bool | None = None
    can_issue_service_receipt_c: bool | None = None
    can_issue_product_invoice_c: bool | None = None
    service_document_type: FiscalDocumentType | None = None
    service_document_code: str | None = Field(default=None, max_length=20)
    product_document_type: FiscalDocumentType | None = None
    product_document_code: str | None = Field(default=None, max_length=20)

    @field_validator(
        "display_name",
        "tax_id",
        "service_document_code",
        "product_document_code",
        mode="before",
    )
    @classmethod
    def normalize_text(cls, value):
        if not isinstance(value, str):
            return value
        return value.strip() or None


class FiscalIssuerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    user_name: str | None = None
    user_email: str | None = None
    display_name: str
    tax_id: str
    is_active: bool
    can_issue_service_receipt_c: bool
    can_issue_product_invoice_c: bool
    service_document_type: FiscalDocumentType | None = None
    service_document_code: str | None = None
    product_document_type: FiscalDocumentType | None = None
    product_document_code: str | None = None
    created_at: datetime
    updated_at: datetime

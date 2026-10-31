import uuid
import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


FiscalDocumentType = Literal["receipt_c", "invoice_c"]


def normalize_cuit(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str) or not re.fullmatch(r"[0-9\s-]+", value):
        raise ValueError("El CUIT debe contener once dígitos")
    normalized = re.sub(r"[\s-]", "", value)
    if len(normalized) != 11:
        raise ValueError("El CUIT debe contener once dígitos")
    weighted = sum(int(digit) * weight for digit, weight in zip(normalized[:10], (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)))
    verifier = 11 - weighted % 11
    # A remainder of one yields ten, which is not a decimal check digit.
    # Do not silently substitute nine or invent/reassign an issuer's identity.
    verifier = 0 if verifier == 11 else verifier
    if verifier != int(normalized[-1]) or normalized == "00000000000":
        raise ValueError("El dígito verificador del CUIT no es válido")
    return normalized


class FiscalIssuerCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: uuid.UUID
    display_name: str = Field(min_length=1, max_length=255)
    tax_id: str = Field(min_length=1, max_length=80)
    cuit: str | None = None
    legal_name: str | None = Field(default=None, max_length=255)
    tax_condition: str | None = Field(default=None, max_length=120)
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
        "legal_name",
        "tax_condition",
        "service_document_code",
        "product_document_code",
        mode="before",
    )
    @classmethod
    def normalize_text(cls, value):
        if not isinstance(value, str):
            return value
        return value.strip() or None

    @field_validator("cuit", mode="before")
    @classmethod
    def validate_cuit(cls, value):
        return normalize_cuit(value)

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
    cuit: str | None = None
    legal_name: str | None = Field(default=None, max_length=255)
    tax_condition: str | None = Field(default=None, max_length=120)
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
        "legal_name",
        "tax_condition",
        "service_document_code",
        "product_document_code",
        mode="before",
    )
    @classmethod
    def normalize_text(cls, value):
        if not isinstance(value, str):
            return value
        return value.strip() or None

    @field_validator("cuit", mode="before")
    @classmethod
    def validate_cuit(cls, value):
        return normalize_cuit(value)


class FiscalIssuerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    user_name: str | None = None
    user_email: str | None = None
    display_name: str
    tax_id: str
    cuit: str | None = None
    legal_name: str | None = None
    tax_condition: str | None = None
    is_active: bool
    can_issue_service_receipt_c: bool
    can_issue_product_invoice_c: bool
    service_document_type: FiscalDocumentType | None = None
    service_document_code: str | None = None
    product_document_type: FiscalDocumentType | None = None
    product_document_code: str | None = None
    created_at: datetime
    updated_at: datetime

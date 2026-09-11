import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_serializer

from app.schemas.fiscal_issuer import FiscalDocumentType


FiscalStatus = Literal[
    "pending", "documented", "requires_attention"
]


class SaleFiscalDocumentFileVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    original_filename: str
    content_type: Literal["application/pdf", "image/jpeg", "image/png"]
    size_bytes: int
    sha256: str
    uploaded_by_user_id: uuid.UUID | None = None
    uploaded_at: datetime
    replaced_at: datetime
    replaced_by_user_id: uuid.UUID | None = None
    replaced_by_user_name: str | None = None
    replaced_by_user_email: str | None = None

    @field_serializer("replaced_by_user_id")
    def serialize_replaced_by(self, value: uuid.UUID | None) -> uuid.UUID | None:
        return value if self.replaced_by_user_name or self.replaced_by_user_email else None


class SaleFiscalDocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    fiscal_issuer_id: uuid.UUID
    issuer_user_id_snapshot: uuid.UUID
    issuer_name_snapshot: str
    issuer_tax_id_snapshot: str
    document_type: FiscalDocumentType
    document_code: str
    document_number: str
    issue_date: date
    total_ars_snapshot: Decimal
    original_filename: str
    content_type: Literal["application/pdf", "image/jpeg", "image/png"]
    size_bytes: int
    sha256: str
    uploaded_by_user_id: uuid.UUID | None = None
    uploaded_by_user_name: str | None = None
    uploaded_by_user_email: str | None = None
    uploaded_at: datetime
    is_active: bool
    file_history: list[SaleFiscalDocumentFileVersionRead]
    created_at: datetime
    updated_at: datetime

    @field_serializer("uploaded_by_user_id")
    def serialize_uploaded_by(self, value: uuid.UUID | None) -> uuid.UUID | None:
        return value if self.uploaded_by_user_name or self.uploaded_by_user_email else None

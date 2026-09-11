import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)


PurchaseReturnStatus = Literal["draft", "confirmed", "cancelled"]
PurchaseReturnDocumentType = Literal[
    "credit_note", "return_delivery_note", "other"
]
PurchaseReturnAttachmentStatus = Literal["pending", "attached"]
PurchaseReturnSortBy = Literal["return_date", "created_at", "total_ars", "supplier_name", "status"]
PurchaseReturnSortDirection = Literal["asc", "desc"]
PurchaseReturnAggregationStatus = Literal["none", "partial", "full"]


class PurchaseReturnItemInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    purchase_item_id: uuid.UUID
    quantity: Decimal = Field(gt=0, multiple_of=Decimal("1"))


class PurchaseReturnCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    return_date: date
    reason: str = Field(min_length=1, max_length=2000)
    document_type: PurchaseReturnDocumentType | None = None
    document_number: str | None = Field(default=None, max_length=120)
    items: list[PurchaseReturnItemInput] = Field(min_length=1, max_length=200)

    @field_validator("reason")
    @classmethod
    def strip_reason(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("String should have at least 1 character")
        return value

    @field_validator("document_number", mode="before")
    @classmethod
    def strip_document_number(cls, value):
        if value is None or not isinstance(value, str):
            return value
        return value.strip() or None


class PurchaseReturnUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    return_date: date | None = None
    reason: str | None = Field(default=None, min_length=1, max_length=2000)
    document_type: PurchaseReturnDocumentType | None = None
    document_number: str | None = Field(default=None, max_length=120)
    items: list[PurchaseReturnItemInput] | None = Field(
        default=None, min_length=1, max_length=200
    )

    @field_validator("reason")
    @classmethod
    def strip_optional_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("String should have at least 1 character")
        return value

    @field_validator("document_number", mode="before")
    @classmethod
    def strip_optional_document_number(cls, value):
        if value is None or not isinstance(value, str):
            return value
        return value.strip() or None

    @model_validator(mode="after")
    def reject_null_required_fields(self):
        for field_name in ("return_date", "reason", "items"):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null")
        return self


class PurchaseReturnCancel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("reason")
    @classmethod
    def strip_reason(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("String should have at least 1 character")
        return value


class PurchaseReturnConfirm(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirm: Literal[True]


class PurchaseReturnItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    purchase_item_id: uuid.UUID
    inventory_item_id: uuid.UUID
    line_number: int
    description_snapshot: str
    internal_code_snapshot: str
    unit: str
    quantity: Decimal
    unit_price_without_tax_ars: Decimal
    tax_rate_percentage: Decimal
    line_subtotal_ars: Decimal
    line_tax_ars: Decimal
    line_total_ars: Decimal
    created_at: datetime
    updated_at: datetime


class PurchaseReturnAttachmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    original_filename: str
    content_type: Literal["application/pdf", "image/jpeg", "image/png"]
    size_bytes: int
    sha256: str
    uploaded_by_user_id: uuid.UUID | None = None
    uploaded_by_user_name: str | None = None
    uploaded_by_user_email: str | None = None
    uploaded_at: datetime
    is_active: bool
    replaced_at: datetime | None = None
    replaced_by_user_id: uuid.UUID | None = None
    replaced_by_user_name: str | None = None
    replaced_by_user_email: str | None = None
    created_at: datetime
    updated_at: datetime

    @field_serializer("uploaded_by_user_id", "replaced_by_user_id")
    def serialize_user_id(self, value: uuid.UUID | None, info) -> uuid.UUID | None:
        prefix = info.field_name.removesuffix("_id")
        if getattr(self, f"{prefix}_name") or getattr(self, f"{prefix}_email"):
            return value
        return None


class PurchaseReturnSummaryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    purchase_id: uuid.UUID
    supplier_id: uuid.UUID
    supplier_name: str
    return_date: date
    status: PurchaseReturnStatus
    reason: str
    document_type: PurchaseReturnDocumentType | None = None
    document_number: str | None = None
    subtotal_ars: Decimal
    tax_total_ars: Decimal
    total_ars: Decimal
    item_count: int
    attachment_status: PurchaseReturnAttachmentStatus
    created_by_user_id: uuid.UUID | None = None
    created_by_user_name: str | None = None
    created_by_user_email: str | None = None
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_by_user_id")
    def serialize_created_by_user_id(self, value: uuid.UUID | None) -> uuid.UUID | None:
        if self.created_by_user_name or self.created_by_user_email:
            return value
        return None


class PurchaseReturnPurchaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    purchase_date: date
    supplier_id: uuid.UUID
    supplier_name: str
    document_type: str
    document_number: str | None = None
    total_ars: Decimal
    status: str


class PurchaseReturnDetailRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    purchase_id: uuid.UUID
    supplier_id: uuid.UUID
    supplier_name: str
    supplier_tax_id: str | None = None
    return_date: date
    status: PurchaseReturnStatus
    reason: str
    document_type: PurchaseReturnDocumentType | None = None
    document_number: str | None = None
    currency: Literal["USD", "ARS"]
    subtotal_ars: Decimal
    tax_total_ars: Decimal
    total_ars: Decimal
    inventory_operation_id: uuid.UUID | None = None
    created_by_user_id: uuid.UUID | None = None
    created_by_user_name: str | None = None
    created_by_user_email: str | None = None
    confirmed_at: datetime | None = None
    confirmed_by_user_id: uuid.UUID | None = None
    confirmed_by_user_name: str | None = None
    confirmed_by_user_email: str | None = None
    cancelled_at: datetime | None = None
    cancelled_by_user_id: uuid.UUID | None = None
    cancelled_by_user_name: str | None = None
    cancelled_by_user_email: str | None = None
    cancellation_reason: str | None = None
    attachment_status: PurchaseReturnAttachmentStatus
    attachment: PurchaseReturnAttachmentRead | None = None
    attachment_history: list[PurchaseReturnAttachmentRead] = Field(default_factory=list)
    purchase: PurchaseReturnPurchaseRead
    items: list[PurchaseReturnItemRead]
    created_at: datetime
    updated_at: datetime

    @field_serializer(
        "created_by_user_id", "confirmed_by_user_id", "cancelled_by_user_id"
    )
    def serialize_user_id(self, value: uuid.UUID | None, info) -> uuid.UUID | None:
        prefix = info.field_name.removesuffix("_id")
        if getattr(self, f"{prefix}_name") or getattr(self, f"{prefix}_email"):
            return value
        return None

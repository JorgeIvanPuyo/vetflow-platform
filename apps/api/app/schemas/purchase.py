import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator, model_validator

from app.schemas.supplier import SupplierSummaryRead


PurchaseStatus = Literal[
    "draft", "cancelled", "received", "partially_received", "returned", "reversed"
]
PurchaseFunctionalStatus = Literal["draft", "cancelled", "received", "reversed"]
PurchaseDocumentType = Literal["invoice", "receipt", "ticket", "delivery_note", "other"]
PurchaseSortBy = Literal["purchase_date", "created_at", "total_ars", "supplier_name"]
SortDirection = Literal["asc", "desc"]
PurchaseAttachmentStatus = Literal["pending", "attached"]


class PurchaseItemInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inventory_item_id: uuid.UUID
    quantity: Decimal = Field(gt=0, multiple_of=Decimal("1"))
    unit_price_without_tax_ars: Decimal = Field(ge=0)
    tax_rate_percentage: Decimal = Field(default=Decimal("21"), ge=0, le=100)


class PurchaseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    supplier_id: uuid.UUID
    purchase_date: date
    document_type: PurchaseDocumentType
    document_number: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=4000)
    items: list[PurchaseItemInput] = Field(min_length=1, max_length=200)

    @field_validator("document_number", "notes", mode="before")
    @classmethod
    def strip_optional_strings(cls, value):
        if value is None or not isinstance(value, str):
            return value
        value = value.strip()
        return value or None


class PurchaseUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    supplier_id: uuid.UUID | None = None
    purchase_date: date | None = None
    document_type: PurchaseDocumentType | None = None
    document_number: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=4000)
    items: list[PurchaseItemInput] | None = Field(default=None, min_length=1, max_length=200)

    @field_validator("document_number", "notes", mode="before")
    @classmethod
    def strip_update_optional_strings(cls, value):
        if value is None or not isinstance(value, str):
            return value
        value = value.strip()
        return value or None

    @model_validator(mode="after")
    def reject_null_required_fields(self):
        for field_name in ("supplier_id", "purchase_date", "document_type", "items"):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null")
        return self


class PurchaseCancel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("reason")
    @classmethod
    def strip_reason(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("String should have at least 1 character")
        return value


class PurchaseReceive(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirm: Literal[True]


class PurchaseReverseReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("reason")
    @classmethod
    def strip_reason(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("String should have at least 1 character")
        return value


class PurchaseItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    inventory_item_id: uuid.UUID
    line_number: int
    description_snapshot: str
    internal_code_snapshot: str
    unit: str
    quantity: Decimal
    unit_price_without_tax_ars: Decimal
    tax_rate_percentage: Decimal
    unit_price_with_tax_ars: Decimal
    line_subtotal_ars: Decimal
    line_tax_ars: Decimal
    line_total_ars: Decimal
    previous_purchase_price_ars: Decimal | None = None
    previous_purchase_tax_rate_percentage: Decimal | None = None
    created_at: datetime
    updated_at: datetime


class PurchaseAttachmentRead(BaseModel):
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

    @field_serializer("uploaded_by_user_id")
    def serialize_uploaded_by_user_id(self, value: uuid.UUID | None) -> uuid.UUID | None:
        if self.uploaded_by_user_name or self.uploaded_by_user_email:
            return value
        return None

    @field_serializer("replaced_by_user_id")
    def serialize_replaced_by_user_id(self, value: uuid.UUID | None) -> uuid.UUID | None:
        if self.replaced_by_user_name or self.replaced_by_user_email:
            return value
        return None


class PurchaseSummaryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    supplier_id: uuid.UUID
    supplier_name: str
    supplier_tax_id: str | None = None
    purchase_date: date
    document_type: PurchaseDocumentType
    document_number: str | None = None
    currency: Literal["ARS"]
    subtotal_ars: Decimal
    tax_total_ars: Decimal
    total_ars: Decimal
    status: PurchaseStatus
    item_count: int
    attachment_status: PurchaseAttachmentStatus
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


class PurchaseDetailRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    supplier_id: uuid.UUID
    supplier_name: str
    supplier_tax_id: str | None = None
    supplier: SupplierSummaryRead | None = None
    purchase_date: date
    document_type: PurchaseDocumentType
    document_number: str | None = None
    currency: Literal["ARS"]
    subtotal_ars: Decimal
    tax_total_ars: Decimal
    total_ars: Decimal
    notes: str | None = None
    status: PurchaseStatus
    created_by_user_id: uuid.UUID | None = None
    created_by_user_name: str | None = None
    created_by_user_email: str | None = None
    created_at: datetime
    updated_at: datetime
    cancelled_at: datetime | None = None
    cancelled_by_user_id: uuid.UUID | None = None
    cancelled_by_user_name: str | None = None
    cancelled_by_user_email: str | None = None
    cancellation_reason: str | None = None
    received_at: datetime | None = None
    received_by_user_id: uuid.UUID | None = None
    received_by_user_name: str | None = None
    received_by_user_email: str | None = None
    inventory_operation_id: uuid.UUID | None = None
    reversed_at: datetime | None = None
    reversed_by_user_id: uuid.UUID | None = None
    reversed_by_user_name: str | None = None
    reversed_by_user_email: str | None = None
    reversal_reason: str | None = None
    reversal_operation_id: uuid.UUID | None = None
    reversal_warnings: list[str] = Field(default_factory=list)
    attachment_status: PurchaseAttachmentStatus
    attachment: PurchaseAttachmentRead | None = None
    attachment_history: list[PurchaseAttachmentRead] = Field(default_factory=list)
    items: list[PurchaseItemRead]

    @field_serializer("created_by_user_id")
    def serialize_created_by_user_id(self, value: uuid.UUID | None) -> uuid.UUID | None:
        if self.created_by_user_name or self.created_by_user_email:
            return value
        return None

    @field_serializer("cancelled_by_user_id")
    def serialize_cancelled_by_user_id(self, value: uuid.UUID | None) -> uuid.UUID | None:
        if self.cancelled_by_user_name or self.cancelled_by_user_email:
            return value
        return None

    @field_serializer("received_by_user_id")
    def serialize_received_by_user_id(self, value: uuid.UUID | None) -> uuid.UUID | None:
        if self.received_by_user_name or self.received_by_user_email:
            return value
        return None

    @field_serializer("reversed_by_user_id")
    def serialize_reversed_by_user_id(self, value: uuid.UUID | None) -> uuid.UUID | None:
        if self.reversed_by_user_name or self.reversed_by_user_email:
            return value
        return None

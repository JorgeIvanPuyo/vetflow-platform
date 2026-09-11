from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.schemas.purchase import (
    PurchaseAttachmentStatus,
    PurchaseDocumentType,
    PurchaseStatus,
)


PurchaseAttentionType = Literal[
    "old_draft",
    "attachment_pending",
    "reversed_receipt",
    "document_number_missing",
]
PurchaseAttentionPriority = Literal["high", "medium", "info"]


class PurchaseDashboardPeriodRead(BaseModel):
    date_from: date
    date_to: date


class PurchaseDashboardFiltersRead(BaseModel):
    supplier_id: uuid.UUID | None = None
    created_by_user_id: uuid.UUID | None = None
    document_type: PurchaseDocumentType | None = None


class PurchaseDashboardSummaryRead(BaseModel):
    registered_total_ars: Decimal
    received_total_ars: Decimal
    registered_tax_total_ars: Decimal
    received_tax_total_ars: Decimal
    returned_total_ars: Decimal
    net_received_total_ars: Decimal
    confirmed_return_count: int
    purchase_count: int
    draft_count: int
    received_count: int
    reversed_count: int
    cancelled_count: int
    attachment_pending_count: int
    attachment_attached_count: int


class PurchaseDashboardAttentionRead(BaseModel):
    id: uuid.UUID
    purchase_date: date
    supplier_name: str
    document_number: str | None = None
    total_ars: Decimal
    status: PurchaseStatus
    attachment_status: PurchaseAttachmentStatus
    alerts: list[PurchaseAttentionType]
    priority: PurchaseAttentionPriority


class PurchaseDashboardTopSupplierRead(BaseModel):
    supplier_id: uuid.UUID
    supplier_name: str
    purchase_count: int
    registered_total_ars: Decimal
    received_total_ars: Decimal


class PurchaseDashboardRecentPurchaseRead(BaseModel):
    id: uuid.UUID
    purchase_date: date
    supplier_name: str
    document_type: PurchaseDocumentType
    document_number: str | None = None
    total_ars: Decimal
    status: PurchaseStatus
    attachment_status: PurchaseAttachmentStatus
    created_by_user_id: uuid.UUID | None = None
    created_by_user_name: str | None = None
    created_by_user_email: str | None = None
    created_at: datetime


class PurchaseDashboardRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    generated_at: datetime
    period: PurchaseDashboardPeriodRead
    filters: PurchaseDashboardFiltersRead
    summary: PurchaseDashboardSummaryRead
    attention: list[PurchaseDashboardAttentionRead]
    top_suppliers: list[PurchaseDashboardTopSupplierRead]
    recent_purchases: list[PurchaseDashboardRecentPurchaseRead]

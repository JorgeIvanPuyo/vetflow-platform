import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.fiscal_configuration import FiscalPolicyRead
from app.schemas.sale_fiscal import SaleFiscalDocumentRead


class FiscalBlocker(BaseModel):
    code: str
    message: str


class FiscalProposalGenerate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    payment_ids: list[uuid.UUID] | None = Field(default=None, min_length=1, max_length=200)
    fiscal_series_id: uuid.UUID | None = None
    fiscal_description: str | None = Field(default=None, min_length=1, max_length=1000)

    @field_validator("payment_ids")
    @classmethod
    def unique_payments(cls, value):
        if value is not None and len(set(value)) != len(value):
            raise ValueError("Selecciona cada cobro una sola vez")
        return value

    @field_validator("fiscal_description")
    @classmethod
    def trim_description(cls, value):
        if value is not None and not value.strip():
            raise ValueError("La descripción fiscal es obligatoria")
        return value.strip() if value else value


class FiscalProposalUpdate(FiscalProposalGenerate):
    payment_ids: list[uuid.UUID] = Field(min_length=1, max_length=200)
    fiscal_series_id: uuid.UUID
    fiscal_description: str = Field(min_length=1, max_length=1000)


class FiscalProposalApprove(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    confirm_fiscal_identity: Literal[True]


class FiscalManualAllocation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    payment_ids: list[uuid.UUID] = Field(min_length=1, max_length=200)
    confirm_fiscal_identity: Literal[True]

    @field_validator("payment_ids")
    @classmethod
    def unique_payments(cls, value):
        if len(set(value)) != len(value):
            raise ValueError("Selecciona cada cobro una sola vez")
        return value


class FiscalProposalCancel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("reason")
    @classmethod
    def trim_reason(cls, value):
        if not value.strip():
            raise ValueError("Indica el motivo de cancelación")
        return value.strip()


class FiscalAllocationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    payment_id: uuid.UUID
    amount_ars: Decimal
    is_active: bool
    reserved_at: datetime
    released_at: datetime | None = None


class FiscalProposalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    sale_id: uuid.UUID
    fiscal_issuer_id: uuid.UUID
    fiscal_series_id: uuid.UUID
    status: Literal["draft", "approved", "cancelled", "sent", "unknown", "authorized", "rejected", "caea_pending"]
    payment_ids: list[str]
    fiscal_description: str
    total_ars: Decimal
    currency: str
    concept: int
    content_hash: str
    source_snapshot_hash: str
    snapshot: dict
    blockers: list[FiscalBlocker] = Field(default_factory=list)
    is_stale: bool = False
    created_at: datetime
    approved_at: datetime | None = None
    approved_by_user_id: uuid.UUID | None = None
    cancelled_at: datetime | None = None
    cancellation_reason: str | None = None
    allocations: list[FiscalAllocationRead] = Field(default_factory=list)


class FiscalPaymentReview(BaseModel):
    payment_id: uuid.UUID
    payment_method_id: uuid.UUID
    label: str
    type: str
    amount_ars: Decimal
    status: Literal["proposed", "committed", "excluded", "pending", "available"]
    reason: str | None = None
    suggested_fiscal_issuer_id: uuid.UUID | None = None
    proposal_id: uuid.UUID | None = None


class FiscalEligibility(BaseModel):
    eligible: bool
    blockers: list[FiscalBlocker]


class FiscalReviewPermissions(BaseModel):
    can_generate: bool
    can_manage_configuration: bool
    can_approve: bool
    own_issuer_id: uuid.UUID | None = None


class FiscalReviewTotals(BaseModel):
    active_payments_ars: Decimal
    committed_ars: Decimal
    proposed_ars: Decimal
    excluded_ars: Decimal
    pending_ars: Decimal
    available_ars: Decimal


class FiscalReviewRead(BaseModel):
    policy: FiscalPolicyRead
    eligibility: FiscalEligibility
    payments: list[FiscalPaymentReview]
    proposals: list[FiscalProposalRead]
    documents: list[SaleFiscalDocumentRead]
    totals: FiscalReviewTotals
    permissions: FiscalReviewPermissions
    external_emission_available: bool = False

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.fiscal_issuer import FiscalDocumentType, FiscalIssuerRead
from app.schemas.payment import PaymentMethodRead


class FiscalPolicyUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool | None = None
    payment_scope: Literal["electronic_only", "all_payments"] | None = None
    accounting_review_note: str | None = Field(default=None, min_length=1, max_length=1000)

    @field_validator("accounting_review_note", mode="before")
    @classmethod
    def trim_note(cls, value):
        return value.strip() if isinstance(value, str) else value


class FiscalPolicyReviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    policy_revision: int
    payment_scope: Literal["electronic_only", "all_payments"]
    enabled: bool
    reviewed_at: datetime
    reviewed_by_user_id: uuid.UUID
    note: str


class FiscalPolicyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    enabled: bool = False
    payment_scope: Literal["electronic_only", "all_payments"] = "electronic_only"
    accounting_reviewed_at: datetime | None = None
    accounting_reviewed_by_user_id: uuid.UUID | None = None
    accounting_review_note: str | None = None
    revision: int = 1
    production_blocked: bool = True
    external_emission_available: bool = False
    review_history: list[FiscalPolicyReviewRead] = Field(default_factory=list)


class FiscalSeriesCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fiscal_issuer_id: uuid.UUID
    environment: Literal["homologation", "production"] = "homologation"
    point_of_sale: int = Field(ge=1, le=99999)
    document_type: FiscalDocumentType
    concept: Literal[1, 2, 3]
    authorization_mode: Literal["CAE", "CAEA"] = "CAE"
    is_active: bool = True
    credential_reference: str | None = Field(default=None, max_length=220, pattern=r"^opaque://[A-Za-z0-9][A-Za-z0-9._/-]{0,199}$")
    caea_reference: str | None = Field(default=None, max_length=220, pattern=r"^opaque://[A-Za-z0-9][A-Za-z0-9._/-]{0,199}$")


class FiscalSeriesUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fiscal_issuer_id: uuid.UUID | None = None
    environment: Literal["homologation", "production"] | None = None
    point_of_sale: int | None = Field(default=None, ge=1, le=99999)
    document_type: FiscalDocumentType | None = None
    concept: Literal[1, 2, 3] | None = None
    authorization_mode: Literal["CAE", "CAEA"] | None = None
    is_active: bool | None = None
    credential_reference: str | None = Field(default=None, max_length=220, pattern=r"^opaque://[A-Za-z0-9][A-Za-z0-9._/-]{0,199}$")
    caea_reference: str | None = Field(default=None, max_length=220, pattern=r"^opaque://[A-Za-z0-9][A-Za-z0-9._/-]{0,199}$")


class FiscalSeriesRead(FiscalSeriesCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    cuit_snapshot: str | None = None
    revision: int
    readiness: Literal["pending", "ready"] = "pending"
    pending_reasons: list[str] = Field(default_factory=list)
    external_emission_available: bool = False
    created_at: datetime
    updated_at: datetime


class FiscalPermissions(BaseModel):
    can_manage_configuration: bool
    can_review_proposals: bool
    can_approve_proposals: bool
    own_issuer_only: bool


class FiscalConfigurationRead(BaseModel):
    policy: FiscalPolicyRead
    issuers: list[FiscalIssuerRead]
    series: list[FiscalSeriesRead]
    payment_methods: list[PaymentMethodRead]
    permissions: FiscalPermissions

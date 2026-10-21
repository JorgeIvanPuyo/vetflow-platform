import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.arca_emission import FiscalBusinessPayload


class FiscalEmissionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    proposal_id: uuid.UUID
    fiscal_data: FiscalBusinessPayload
    confirm_fiscal_identity: Literal[True]
    supersedes_id: uuid.UUID | None = None


class FiscalEmissionIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirm: Literal[True]


class FiscalEmissionActions(BaseModel):
    issue: bool = False
    reconcile: bool = False
    regenerate: bool = False
    download: bool = False
    retry_same_request: bool = False


class FiscalEmissionReconcile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    retry_same_request: bool = False
    confirm: bool = False


class FiscalEmissionAttemptRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    action: str
    outcome: str
    created_at: datetime


class FiscalEmissionFileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    sha256: str
    created_at: datetime


class FiscalEmissionRead(BaseModel):
    id: uuid.UUID
    proposal_id: uuid.UUID
    sale_id: uuid.UUID
    status: Literal["prepared", "processing", "unknown", "conflict", "rejected", "authorized"]
    environment: Literal["homologation"]
    request_hash: str
    business_snapshot: dict
    number: int | None
    cae: str | None
    cae_expiry: date | None
    document_id: uuid.UUID | None
    file_status: Literal["pending", "ready", "failed"]
    diagnostics: list[dict] = Field(default_factory=list)
    next_action_at: datetime | None
    created_at: datetime
    updated_at: datetime
    attempts: list[FiscalEmissionAttemptRead]
    file_versions: list[FiscalEmissionFileRead]
    allowed_actions: FiscalEmissionActions


class FiscalReadinessValidate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    series_id: uuid.UUID

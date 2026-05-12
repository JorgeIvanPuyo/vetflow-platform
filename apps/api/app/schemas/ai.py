from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


AI_DISCLAIMER = "Texto sugerido por IA. Revisa antes de guardar."


class AIPatientContext(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    species: str | None = Field(default=None, max_length=80)
    breed: str | None = Field(default=None, max_length=120)
    sex: str | None = Field(default=None, max_length=80)
    age: str | None = Field(default=None, max_length=80)
    weight_kg: float | None = Field(default=None, gt=0)


class RewriteClinicalNoteRequest(BaseModel):
    field: str = Field(min_length=1, max_length=80)
    text: str = Field(min_length=5, max_length=4000)
    patient_context: AIPatientContext | None = None

    @field_validator("field", "text")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Field cannot be empty")
        return stripped


class RewriteClinicalNoteResponse(BaseModel):
    suggestion: str
    disclaimer: str = AI_DISCLAIMER


class ConsultationSummaryInput(BaseModel):
    patient_name: str | None = Field(default=None, max_length=120)
    species: str | None = Field(default=None, max_length=80)
    breed: str | None = Field(default=None, max_length=120)
    sex: str | None = Field(default=None, max_length=80)
    age: str | None = Field(default=None, max_length=80)
    weight_kg: float | None = Field(default=None, gt=0)
    reason: str | None = Field(default=None, max_length=1000)
    anamnesis: str | None = Field(default=None, max_length=4000)
    physical_exam: str | None = Field(default=None, max_length=4000)
    presumptive_diagnosis: str | None = Field(default=None, max_length=4000)
    diagnostic_plan: str | None = Field(default=None, max_length=4000)
    therapeutic_plan: str | None = Field(default=None, max_length=4000)
    instructions: str | None = Field(default=None, max_length=4000)

    @field_validator(
        "patient_name",
        "species",
        "breed",
        "sex",
        "age",
        "reason",
        "anamnesis",
        "physical_exam",
        "presumptive_diagnosis",
        "diagnostic_plan",
        "therapeutic_plan",
        "instructions",
    )
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @model_validator(mode="after")
    def validate_clinical_content(self) -> "ConsultationSummaryInput":
        clinical_fields = [
            self.reason,
            self.anamnesis,
            self.physical_exam,
            self.presumptive_diagnosis,
            self.diagnostic_plan,
            self.therapeutic_plan,
            self.instructions,
        ]
        if not any(value for value in clinical_fields):
            raise ValueError("Consultation must include clinical information")
        return self


class GenerateConsultationSummaryRequest(BaseModel):
    consultation: ConsultationSummaryInput
    summary_type: Literal["clinical", "owner_friendly"] = "clinical"


class GenerateConsultationSummaryResponse(BaseModel):
    summary: str
    disclaimer: str = AI_DISCLAIMER

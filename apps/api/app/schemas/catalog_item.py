import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator


CatalogType = Literal[
    "mucous_membrane",
    "hydration",
    "inventory_category",
    "inventory_subcategory",
    "exam_type",
    "preventive_care_type",
    "document_type",
    "follow_up_template",
    "species",
    "breed",
    "diagnostic_tag",
    "prescription_template",
]
CATALOG_TYPES: tuple[str, ...] = (
    "mucous_membrane",
    "hydration",
    "inventory_category",
    "inventory_subcategory",
    "exam_type",
    "preventive_care_type",
    "document_type",
    "follow_up_template",
    "species",
    "breed",
    "diagnostic_tag",
    "prescription_template",
)

# Catalog types that nest under another catalog type (child -> required parent type).
# A parent_id is only accepted for these types, and it must reference an active-or-not
# item of the mapped parent type within the same tenant.
PARENT_CATALOG_TYPES: dict[str, str] = {
    "inventory_subcategory": "inventory_category",
    "breed": "species",
}


class CatalogItemBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    code: str | None = Field(default=None, max_length=80)
    sort_order: int = 0
    parent_id: uuid.UUID | None = None

    @field_validator("name", "description", "code", mode="before")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value


class CatalogItemCreate(CatalogItemBase):
    pass


class CatalogItemUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    code: str | None = Field(default=None, max_length=80)
    sort_order: int | None = None
    parent_id: uuid.UUID | None = None

    @field_validator("name", "description", "code", mode="before")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value


class CatalogItemRead(CatalogItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    catalog_type: str
    normalized_name: str
    is_active: bool
    created_by_user_id: uuid.UUID | None = None
    created_by_user_name: str | None = None
    created_by_user_email: str | None = None
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_by_user_id")
    def serialize_created_by_user_id(
        self,
        value: uuid.UUID | None,
    ) -> uuid.UUID | None:
        if self.created_by_user_name or self.created_by_user_email:
            return value
        return None


class CatalogItemReorderItem(BaseModel):
    id: uuid.UUID
    sort_order: int


class CatalogItemReorderRequest(BaseModel):
    items: list[CatalogItemReorderItem] = Field(min_length=1)

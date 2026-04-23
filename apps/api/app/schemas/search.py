import uuid

from pydantic import BaseModel


class SearchResultItem(BaseModel):
    type: str
    id: uuid.UUID
    title: str
    subtitle: str
    owner_id: uuid.UUID | None = None
    patient_id: uuid.UUID | None = None


class SearchMeta(BaseModel):
    query: str

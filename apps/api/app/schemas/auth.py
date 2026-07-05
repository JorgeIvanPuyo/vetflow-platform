import uuid

from pydantic import BaseModel


class CurrentUserRead(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    is_active: bool
    tenant_id: uuid.UUID
    tenant_name: str

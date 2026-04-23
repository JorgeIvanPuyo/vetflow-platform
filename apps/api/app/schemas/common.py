from typing import Any

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


class SingleItemResponse(BaseModel):
    data: Any
    meta: dict[str, Any] = Field(default_factory=dict)


class ListMeta(BaseModel):
    page: int = 1
    page_size: int
    total: int


class ListResponse(BaseModel):
    data: list[Any]
    meta: ListMeta

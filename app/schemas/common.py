"""Shared schema building blocks: base model, pagination envelope, error shape."""

from math import ceil
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field


class APIModel(BaseModel):
    """Base for all API schemas.

    - `from_attributes` lets response models serialize ORM objects directly.
    - `str_strip_whitespace` sanitizes all incoming string fields.
    """

    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


ItemT = TypeVar("ItemT")


class Page(BaseModel, Generic[ItemT]):
    """Standard envelope for every list endpoint."""

    items: list[ItemT]
    total: int = Field(examples=[42])
    page: int = Field(examples=[1])
    page_size: int = Field(examples=[20])
    pages: int = Field(examples=[3])

    @classmethod
    def build(cls, items: list[ItemT], total: int, page: int, page_size: int) -> "Page[ItemT]":
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=ceil(total / page_size) if total else 0,
        )


class ErrorInfo(BaseModel):
    code: str = Field(examples=["not_found"])
    message: str = Field(examples=["Project not found"])
    details: list[dict] | None = None


class ErrorResponse(BaseModel):
    """Documents the standard error envelope in OpenAPI."""

    error: ErrorInfo
    request_id: str | None = None

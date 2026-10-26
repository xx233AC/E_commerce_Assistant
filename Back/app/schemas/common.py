from typing import Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)


class Meta(StrictModel):
    request_id: UUID


class ApiResponse(StrictModel, Generic[T]):
    data: T
    meta: Meta


class Ack(StrictModel):
    ok: bool
    message: str = Field(min_length=1, max_length=1000)


class ErrorDetail(StrictModel):
    field: str | None
    row_number: int | None
    code: str
    message: str


class ErrorBody(StrictModel):
    code: str
    message: str
    details: list[ErrorDetail]
    retryable: bool


class ErrorResponse(StrictModel):
    error: ErrorBody
    request_id: UUID

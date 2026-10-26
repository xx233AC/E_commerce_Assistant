from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, ConfigDict, Field

from app.schemas.common import StrictModel


class UserRead(StrictModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    version: int = Field(ge=1, le=2147483647)
    created_at: AwareDatetime
    updated_at: AwareDatetime
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    display_name: str = Field(min_length=1, max_length=100)
    role: Literal["admin", "operator", "viewer"]
    status: Literal["active", "disabled"]
    last_login_at: AwareDatetime | None

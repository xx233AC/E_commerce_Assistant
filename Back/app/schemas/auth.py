from typing import Literal

from pydantic import Field, SecretStr

from app.schemas.common import StrictModel
from app.schemas.user import UserRead


class LoginRequest(StrictModel):
    username: str = Field(min_length=3, max_length=64)
    password: SecretStr = Field(min_length=1, max_length=128)


class LoginResult(StrictModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: Literal[7200] = 7200
    user: UserRead

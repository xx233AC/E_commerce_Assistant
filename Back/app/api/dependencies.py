from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.exceptions import unauthorized
from app.db.session import get_db
from app.services.auth import AuthContext, authenticate

DbSession = Annotated[Session, Depends(get_db)]
bearer = HTTPBearer(auto_error=False, bearerFormat="JWT")


def get_auth_context(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> AuthContext:
    if credentials is None:
        raise unauthorized("请先登录")
    return authenticate(db, credentials.credentials)


CurrentAuth = Annotated[AuthContext, Depends(get_auth_context)]

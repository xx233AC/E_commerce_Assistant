import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from pwdlib import PasswordHash

from app.core.config import get_settings
from app.core.exceptions import unauthorized

TOKEN_TTL_SECONDS = 7200
ISSUER = "commerce-assistant"
AUDIENCE = "commerce-front"
password_hasher = PasswordHash.recommended()
DUMMY_HASH = password_hasher.hash(secrets.token_urlsafe(32))


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, encoded: str) -> bool:
    return password_hasher.verify(password, encoded)


def create_token(user_id: UUID, session_id: UUID, now: datetime) -> str:
    return jwt.encode(
        {"sub": str(user_id), "sid": str(session_id), "iat": now,
         "exp": now + timedelta(seconds=TOKEN_TTL_SECONDS),
         "iss": ISSUER, "aud": AUDIENCE},
        get_settings().jwt_secret.get_secret_value(), algorithm="HS256",
    )


def read_token(token: str) -> tuple[UUID, UUID]:
    try:
        claims = jwt.decode(
            token, get_settings().jwt_secret.get_secret_value(),
            algorithms=["HS256"], issuer=ISSUER, audience=AUDIENCE,
            options={"require": ["sub", "sid", "iat", "exp", "iss", "aud"]},
        )
        return UUID(claims["sub"]), UUID(claims["sid"])
    except (jwt.InvalidTokenError, ValueError, TypeError, AttributeError):
        raise unauthorized() from None

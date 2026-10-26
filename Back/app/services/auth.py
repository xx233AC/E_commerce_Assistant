from dataclasses import dataclass
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.exceptions import unauthorized
from app.core.rate_limit import lock_login_limits, reset_account_limit
from app.core.security import (
    DUMMY_HASH, TOKEN_TTL_SECONDS, create_token, read_token, utcnow, verify_password,
)
from app.models.session import LoginSession
from app.models.user import User
from app.schemas.auth import LoginRequest, LoginResult
from app.schemas.user import UserRead


@dataclass
class AuthContext:
    user: User
    session: LoginSession


def login(db: Session, payload: LoginRequest, ip: str) -> LoginResult:
    failure = None
    result = None
    with db.begin():
        limits = lock_login_limits(db, payload.username, ip)
        user = db.scalar(select(User).where(
            User.username == payload.username,
        ).with_for_update())
        encoded = user.password_hash if user else DUMMY_HASH
        valid = verify_password(payload.password.get_secret_value(), encoded)
        if not valid or user is None or user.status != "active":
            for row in limits:
                row.failures += 1
            failure = unauthorized("账号或密码错误，或账号不可用")
        else:
            reset_account_limit(limits, user.username)
            now = utcnow()
            session_id = uuid4()
            db.add(LoginSession(
                id=session_id, user_id=user.id, auth_version=user.auth_version,
                created_at=now, expires_at=now + timedelta(seconds=TOKEN_TTL_SECONDS),
            ))
            user.last_login_at = now
            user.updated_at = now
            user.version += 1
            db.flush()
            result = LoginResult(
                access_token=create_token(user.id, session_id, now),
                user=UserRead.model_validate(user),
            )
    # 必须先提交失败计数，再抛出异常，否则限流记录会被回滚。
    if failure:
        raise failure
    assert result is not None
    return result


def authenticate(db: Session, token: str) -> AuthContext:
    user_id, session_id = read_token(token)
    row = db.execute(select(User, LoginSession).join(
        LoginSession, LoginSession.user_id == User.id,
    ).where(
        User.id == user_id,
        User.status == "active",
        LoginSession.id == session_id,
        LoginSession.revoked_at.is_(None),
        LoginSession.expires_at > utcnow(),
        LoginSession.auth_version == User.auth_version,
    )).first()
    if row is None:
        raise unauthorized()
    return AuthContext(user=row[0], session=row[1])


def logout(db: Session, auth: AuthContext) -> None:
    result = db.execute(update(LoginSession).where(
        LoginSession.id == auth.session.id,
        LoginSession.revoked_at.is_(None),
    ).values(revoked_at=utcnow()))
    if result.rowcount != 1:
        db.rollback()
        raise unauthorized()
    db.commit()

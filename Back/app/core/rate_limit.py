import hashlib
import math

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.exceptions import ApiError
from app.core.security import utcnow
from app.models.login_limit import LoginLimit

WINDOW_SECONDS = 300


def lock_login_limits(db: Session, username: str, ip: str) -> list[LoginLimit]:
    # 用户名最多连续失败5次，IP在窗口内最多失败30次。
    entries = [("account:" + username, 5), ("ip:" + ip, 30)]
    entries = sorted((hashlib.sha256(key.encode()).hexdigest(), limit)
                     for key, limit in entries)
    buckets = []
    for key, limit in entries:
        db.execute(insert(LoginLimit).values(
            key=key, failures=0, window_start=utcnow(),
        ).on_conflict_do_nothing(index_elements=[LoginLimit.key]))
        row = db.scalar(select(LoginLimit).where(
            LoginLimit.key == key,
        ).with_for_update())
        now = utcnow()  # 获取锁之后重新读取时间。
        elapsed = (now - row.window_start).total_seconds()
        if elapsed >= WINDOW_SECONDS:
            row.failures = 0
            row.window_start = now
            elapsed = 0
        if row.failures >= limit:
            wait = max(1, math.ceil(WINDOW_SECONDS - elapsed))
            raise ApiError(429, "RATE_LIMITED", "登录失败次数过多，请稍后重试",
                           retryable=True, headers={"Retry-After": str(wait)})
        buckets.append(row)
    return buckets


def reset_account_limit(buckets: list[LoginLimit], username: str) -> None:
    key = hashlib.sha256(("account:" + username).encode()).hexdigest()
    for row in buckets:
        if row.key == key:
            row.failures = 0
            row.window_start = utcnow()

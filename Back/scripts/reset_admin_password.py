"""Interactive local recovery; never prints or writes the new password."""
import getpass
import re
import warnings

from sqlalchemy import select, text
from sqlalchemy.exc import OperationalError

from app.core.exceptions import ApiError
from app.db.session import SessionLocal
from app.models.user import User
from app.services.common import Context
from app.services.users import patch_user


def reset_password(db, username: str, password: str) -> None:
    if not re.fullmatch(r'[A-Za-z0-9_.-]{3,64}', username):
        raise ValueError('用户名格式不正确')
    if not 12 <= len(password) <= 128:
        raise ValueError('密码须为12至128个字符')
    db.execute(text('SELECT pg_advisory_xact_lock(7310042)'))
    user = db.scalar(select(User).where(User.username == username).with_for_update())
    if user is None or user.role != 'admin':
        raise ValueError('未找到该管理员账号；此脚本不会创建账号或修改普通用户权限')
    if user.status != 'active':
        raise ValueError('该管理员已停用，请由其他有效管理员处理')
    # Reuse password hashing, version updates and session revocation from user management.
    patch_user(Context(db, {}, params={'user_id': str(user.id)},
                       headers={'if-match': f'"{user.version}"'}, body={'password': password}))


def main() -> None:
    username = input('需要重置密码的管理员用户名：').strip()
    # Refuse getpass's plaintext fallback in unsupported IDE consoles.
    with warnings.catch_warnings():
        warnings.simplefilter('error', getpass.GetPassWarning)
        password = getpass.getpass('新密码（12至128个字符，输入不显示）：')
        confirmation = getpass.getpass('再次输入新密码：')
    if password != confirmation:
        raise ValueError('两次密码不一致，未修改账号')
    with SessionLocal.begin() as db:
        reset_password(db, username, password)
    print('管理员密码已重置，旧登录会话已退出。请使用新密码登录；密码不会保存到文本文件。')


if __name__ == '__main__':
    try:
        main()
    except getpass.GetPassWarning:
        raise SystemExit('当前控制台不支持隐藏密码，请在 PowerShell 或 IDE 的 Terminal 中执行。') from None
    except (EOFError, KeyboardInterrupt):
        raise SystemExit('已取消。') from None
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    except ApiError as exc:
        raise SystemExit(exc.message) from None
    except OperationalError:
        raise SystemExit('数据库连接失败，请检查 PostgreSQL 服务、15433 SSH 隧道和 Back/.env。') from None

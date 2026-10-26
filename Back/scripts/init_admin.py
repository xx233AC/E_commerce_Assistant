import getpass
import re

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User


def main() -> None:
    username = input("管理员用户名：").strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,64}", username):
        raise SystemExit("用户名须为3至64位字母、数字、下划线、点或短横线")
    display_name = input("显示名称：").strip()
    if not 1 <= len(display_name) <= 100:
        raise SystemExit("显示名称须为1至100个字符")
    password = getpass.getpass("管理员密码（12至128个字符）：")
    if not 12 <= len(password) <= 128:
        raise SystemExit("密码长度不符合要求")
    if password != getpass.getpass("再次输入密码："):
        raise SystemExit("两次密码不一致")
    with SessionLocal.begin() as db:
        if db.scalar(select(User.id).where(User.username == username)):
            raise SystemExit("用户名已存在；初始化脚本不会覆盖已有账号")
        db.add(User(username=username, display_name=display_name,
                    password_hash=hash_password(password), role="admin", status="active"))
    print("管理员创建成功，可以登录。")


if __name__ == "__main__":
    main()

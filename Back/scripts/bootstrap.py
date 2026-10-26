"""Initialize only operational configuration and the first real administrator."""
from pathlib import Path
import secrets
from sqlalchemy import select,func
from app.db.session import SessionLocal
from app.db.repository import Repo
from app.models.user import User
from app.core.security import hash_password
from app.services.settings import initialize

def main():
    credential=None
    with SessionLocal.begin() as db:
        initialize(Repo(db))
        if not db.scalar(select(func.count()).select_from(User)):
            password=secrets.token_urlsafe(18)
            db.add(User(username='admin',display_name='店铺管理员',password_hash=hash_password(password),role='admin',status='active'))
            credential='用户名：admin\n初始密码：'+password+'\n请登录后在用户管理中修改密码。\n'
    if credential:
        folder=Path(__file__).resolve().parents[1]/'.local'
        folder.mkdir(exist_ok=True)
        (folder/'initial-admin.txt').write_text(credential,encoding='utf-8')
    print('Operational settings initialized. Initial credentials, if created, are in Back/.local/initial-admin.txt.')

if __name__=='__main__':main()

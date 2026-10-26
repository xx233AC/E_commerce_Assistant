from uuid import UUID
from sqlalchemy import select, update, text
from app.core.exceptions import ApiError
from app.core.security import hash_password, utcnow
from app.models.user import User
from app.models.session import LoginSession
from app.schemas.user import UserRead


def list_users(ctx):
    rows=ctx.db.scalars(select(User).order_by(User.updated_at.desc(),User.id.desc())).all()
    rows=[u for u in rows if all(getattr(u,k)==ctx.query[k] for k in ('role','status') if k in ctx.query)]
    return ctx.page([UserRead.model_validate(u).model_dump(mode='json') for u in rows])


def create_user(ctx):
    b=ctx.body
    ctx.db.execute(text('SELECT pg_advisory_xact_lock(7310042)'))
    if ctx.db.scalar(select(User).where(User.username==b['username'])):
        raise ApiError(409,'DUPLICATE_USERNAME','用户名已存在')
    user=User(username=b['username'],display_name=b['display_name'],password_hash=hash_password(b['password']),role=b['role'],status=b.get('status','active'))
    ctx.db.add(user);ctx.db.flush()
    return UserRead.model_validate(user).model_dump(mode='json')


def patch_user(ctx):
    # Serialize administrator changes, including changes to different user rows.
    ctx.db.execute(text('SELECT pg_advisory_xact_lock(7310042)'))
    user=ctx.db.scalar(select(User).where(User.id==UUID(ctx.params['user_id'])).with_for_update())
    if user is None: raise ApiError(404,'NOT_FOUND','用户不存在')
    ctx.check_version({'version':user.version})
    b=ctx.body
    losing_admin=user.role=='admin' and user.status=='active' and (b.get('role',user.role)!='admin' or b.get('status',user.status)!='active')
    if losing_admin and len(ctx.db.scalars(select(User.id).where(User.role=='admin',User.status=='active')).all())<=1:
        raise ApiError(409,'LAST_ADMIN_REQUIRED','必须保留至少一位有效管理员')
    if 'password' in b or any(k in b and b[k]!=getattr(user,k) for k in ('role','status')):
        user.auth_version+=1
        ctx.db.execute(update(LoginSession).where(LoginSession.user_id==user.id,LoginSession.revoked_at.is_(None)).values(revoked_at=utcnow()))
    for k,v in b.items():
        setattr(user,'password_hash' if k=='password' else k,hash_password(v) if k=='password' else v)
    user.version+=1;user.updated_at=utcnow();ctx.db.flush()
    return UserRead.model_validate(user).model_dump(mode='json')

HANDLERS={'GET /users':list_users,'POST /users':create_user,'PATCH /users/{user_id}':patch_user}

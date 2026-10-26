from fastapi import APIRouter, Request, Response

from app.api.dependencies import CurrentAuth, DbSession
from app.schemas.auth import LoginRequest, LoginResult
from app.schemas.common import Ack, ApiResponse, ErrorResponse, Meta
from app.schemas.user import UserRead
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["认证"], responses={
    status: {"model": ErrorResponse}
    for status in (401, 422, 429, 500, 503)
})


@router.post("/login", response_model=ApiResponse[LoginResult])
def login(payload: LoginRequest, request: Request, db: DbSession):
    ip = request.client.host if request.client else "unknown"
    result = auth_service.login(db, payload, ip)
    return ApiResponse[LoginResult](
        data=result, meta=Meta(request_id=request.state.request_id),
    )


@router.get("/me", response_model=ApiResponse[UserRead])
def me(request: Request, response: Response, auth: CurrentAuth):
    response.headers["ETag"] = f'"{auth.user.version}"'
    return ApiResponse[UserRead](
        data=UserRead.model_validate(auth.user),
        meta=Meta(request_id=request.state.request_id),
    )


@router.post("/logout", response_model=ApiResponse[Ack])
def logout(request: Request, db: DbSession, auth: CurrentAuth):
    auth_service.logout(db, auth)
    return ApiResponse[Ack](
        data=Ack(ok=True, message="已退出登录"),
        meta=Meta(request_id=request.state.request_id),
    )

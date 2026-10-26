import logging
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError
from starlette.exceptions import HTTPException

logger = logging.getLogger(__name__)


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, *,
                 details: list | None = None, retryable: bool = False,
                 headers: dict[str, str] | None = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details or []
        self.retryable = retryable
        self.headers = headers or {}


def unauthorized(message: str = "登录已失效，请重新登录") -> ApiError:
    return ApiError(401, "UNAUTHENTICATED", message,
                    headers={"WWW-Authenticate": "Bearer"})


def error_response(request: Request, error: ApiError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", str(uuid4()))
    return JSONResponse(
        status_code=error.status,
        content={
            "error": {
                "code": error.code, "message": error.message,
                "details": error.details, "retryable": error.retryable,
            },
            "request_id": request_id,
        },
        headers={**error.headers, "X-Request-ID": request_id,
                 "Cache-Control": "no-store"},
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, exc: ApiError):
        return error_response(request, exc)

    @app.exception_handler(RequestValidationError)
    async def handle_validation(request: Request, exc: RequestValidationError):
        # 不返回 exc.body 或错误中的 input，避免暴露密码。
        details = [{
            "field": ".".join(map(str, item["loc"]))[:300] or None,
            "row_number": None,
            "code": item["type"][:100],
            "message": "字段缺失或格式不正确",
        } for item in exc.errors()[:1000]]
        return error_response(request, ApiError(
            422, "VALIDATION_ERROR", "请求参数不符合要求", details=details,
        ))

    @app.exception_handler(HTTPException)
    async def handle_http_error(request: Request, exc: HTTPException):
        names = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}
        return error_response(request, ApiError(
            exc.status_code, names.get(exc.status_code, "HTTP_ERROR"),
            "请求地址、方法或内容不符合要求", headers=exc.headers,
        ))

    @app.exception_handler(OperationalError)
    async def handle_database_error(request: Request, exc: OperationalError):
        logger.error("Database unavailable request_id=%s", request.state.request_id)
        return error_response(request, ApiError(
            503, "DEPENDENCY_UNAVAILABLE", "数据库暂不可用，请稍后重试",
            retryable=True,
        ))

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception):
        # 不记录请求体、令牌或可能包含 SQL 参数的异常文本。
        logger.error("Unexpected %s request_id=%s",
                     type(exc).__name__, request.state.request_id)
        return error_response(request, ApiError(
            500, "INTERNAL_ERROR", "服务处理失败，请联系管理员",
        ))

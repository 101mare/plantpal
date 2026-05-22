"""Application error types and a FastAPI exception handler."""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Base for all expected, user-facing errors. Carries an HTTP status + code."""

    status_code = 400
    code = "app_error"

    def __init__(
        self, message: str | None = None, *, code: str | None = None, status_code: int | None = None
    ):
        self.message = message or self.code
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code
        super().__init__(self.message)


class AuthError(AppError):
    status_code = 401
    code = "unauthenticated"


class CsrfError(AppError):
    status_code = 403
    code = "csrf_failed"


class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class TokenInvalidError(AppError):
    status_code = 400
    code = "invalid_token"


class TokenExpiredError(AppError):
    status_code = 410
    code = "token_expired"


class TokenUsedError(AppError):
    status_code = 409
    code = "token_already_used"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class PayloadTooLargeError(AppError):
    status_code = 413
    code = "upload_too_large"


class UnsupportedMediaError(AppError):
    status_code = 415
    code = "unsupported_media_type"


class UnprocessableError(AppError):
    status_code = 422
    code = "unprocessable"


class RateLimitError(AppError):
    status_code = 429
    code = "rate_limited"

    def __init__(self, message: str | None = None, *, retry_after: int = 60):
        self.retry_after = retry_after
        super().__init__(message or "Too many attempts. Try again later.")


def install_exception_handlers(app) -> None:
    @app.exception_handler(AppError)
    async def _handle_app_error(_: Request, exc: AppError):
        headers = {}
        if isinstance(exc, RateLimitError):
            headers["Retry-After"] = str(exc.retry_after)
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
            headers=headers,
        )

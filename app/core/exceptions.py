"""
Centralized Error and Exception Handling
Defines custom application exceptions and error response formats.
"""

from typing import Any, Dict, Optional
from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.core.logging import get_logger

logger = get_logger(__name__)


class AppException(Exception):
    """Base application exception."""

    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        code: str = "INTERNAL_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code
        self.details = details or {}


class DatabaseUnavailableException(AppException):
    """Raised when PostgreSQL cannot be reached or connection fails."""

    def __init__(self, message: str = "Database service unavailable", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="DATABASE_UNAVAILABLE",
            details=details,
        )


class EntityNotFoundException(AppException):
    """Raised when a requested resource is not found."""

    def __init__(
        self,
        entity_name_or_message: str,
        entity_id: Optional[Any] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        if entity_id is not None:
            message = f"{entity_name_or_message} with ID '{entity_id}' was not found"
            err_details = {"entity": str(entity_name_or_message), "id": str(entity_id)}
        else:
            message = entity_name_or_message
            err_details = {"message": entity_name_or_message}

        if details:
            err_details.update(details)

        super().__init__(
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
            code="ENTITY_NOT_FOUND",
            details=err_details,
        )


class ValidationException(AppException):
    """Raised on business logic validation failure."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422),
            code="VALIDATION_ERROR",
            details=details,
        )


class AuthenticationFailedException(AppException):
    """Raised on authentication failure without disclosing which field failed."""

    def __init__(self, message: str = "Invalid username or password"):
        super().__init__(
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="AUTHENTICATION_FAILED",
        )


class SessionExpiredException(AppException):
    """Raised when session is expired or revoked."""

    def __init__(self, message: str = "Session has expired or was revoked. Please log in again."):
        super().__init__(
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="SESSION_EXPIRED",
        )


class ForbiddenException(AppException):
    """Raised when an authenticated user lacks required role, permission, or scope."""

    def __init__(self, message: str = "You do not have permission to perform this action"):
        super().__init__(
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            code="FORBIDDEN",
        )


class AccountInactiveException(AppException):
    """Raised when account is disabled, suspended, or archived."""

    def __init__(self, status_name: str):
        super().__init__(
            message=f"Account is {status_name.lower()}. Authentication is denied.",
            status_code=status.HTTP_403_FORBIDDEN,
            code="ACCOUNT_INACTIVE",
            details={"account_status": status_name},
        )


class ImmutableAuditException(AppException):
    """Raised when attempt is made to update or delete audit logs."""

    def __init__(self, message: str = "Audit records are append-only and strictly immutable"):
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            code="IMMUTABLE_AUDIT_LOG",
        )


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Handles all custom application exceptions."""
    logger.warning(f"AppException: [{exc.code}] {exc.message} (status: {exc.status_code})")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            },
        },
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handles FastAPI Pydantic request validation errors."""
    errors = []
    for err in exc.errors():
        loc_parts = [str(p) for p in err.get("loc", []) if str(p) != "body"]
        loc = " -> ".join(loc_parts) if loc_parts else "body"
        errors.append({"field": loc, "message": err.get("msg")})

    logger.warning(f"Validation failure on {request.method} {request.url.path}: {errors}")
    summary_parts = [f"{e['field']}: {e['message']}" for e in errors if e.get("field")]
    if not summary_parts:
        summary_parts = [e.get("message", "") for e in errors if e.get("message")]
    msg = f"Validation error: {'; '.join(summary_parts)}" if summary_parts else "Invalid request parameters or payload"

    return JSONResponse(
        status_code=getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422),
        content={
            "success": False,
            "error": {
                "code": "REQUEST_VALIDATION_ERROR",
                "message": msg,
                "details": {"validation_errors": errors},
            },
        },
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handles unhandled exceptions without leaking stack traces or credentials."""
    logger.exception(f"Unhandled Exception on {request.method} {request.url.path}: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected internal server error occurred.",
                "details": {},
            },
        },
    )

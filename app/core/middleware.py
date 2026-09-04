"""
Request Middleware
Provides correlation ID tracking, request latency logging, security headers injection,
and in-memory sliding-window rate limiting.
"""

import time
import uuid
from collections import defaultdict
from threading import Lock
from typing import Dict, List, Tuple
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from app.core.config import get_settings
from app.core.logging import correlation_id_ctx, get_logger

logger = get_logger(__name__)
settings = get_settings()


class RequestCorrelationMiddleware(BaseHTTPMiddleware):
    """
    Extracts or generates an X-Request-ID header for correlation tracking across logs.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-ID")
        if not request_id or len(request_id) > 64:
            request_id = str(uuid.uuid4())

        token = correlation_id_ctx.set(request_id)
        start_time = time.perf_counter()

        try:
            response = await call_next(request)
            process_time_ms = (time.perf_counter() - start_time) * 1000.0

            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time-Ms"] = f"{process_time_ms:.2f}"

            logger.info(
                f"{request.method} {request.url.path} "
                f"status={response.status_code} "
                f"duration={process_time_ms:.2f}ms"
            )
            return response
        except Exception:
            process_time_ms = (time.perf_counter() - start_time) * 1000.0
            logger.error(
                f"{request.method} {request.url.path} failed after {process_time_ms:.2f}ms"
            )
            raise
        finally:
            correlation_id_ctx.reset(token)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Injects standard production security headers on all HTTP responses.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)

        if settings.ENABLE_SECURITY_HEADERS:
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-XSS-Protection"] = "1; mode=block"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=(), payment=()"
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
                "img-src 'self' data: https://fastapi.tiangolo.com; "
                "font-src 'self' data: https://fonts.gstatic.com; "
                "connect-src 'self'; "
                "frame-ancestors 'none';"
            )

            if settings.ENFORCE_HTTPS or settings.is_production:
                response.headers["Strict-Transport-Security"] = (
                    "max-age=31536000; includeSubDomains; preload"
                )

        return response


class RateLimitingMiddleware(BaseHTTPMiddleware):
    """
    Thread-safe in-memory sliding-window rate limiter for sensitive and global endpoints.
    Requires no external Redis or message queue.
    """

    _lock = Lock()
    _requests: Dict[str, List[float]] = defaultdict(list)

    @classmethod
    def reset(cls):
        """Clears all in-memory rate limiting counters (primarily for tests)."""
        with cls._lock:
            cls._requests.clear()

    def _clean_and_check(self, key: str, limit: int, window_seconds: int = 60) -> Tuple[bool, int, int]:
        now = time.time()
        cutoff = now - window_seconds

        with self._lock:
            # Filter timestamps outside the window
            valid_timestamps = [ts for ts in self._requests[key] if ts > cutoff]
            self._requests[key] = valid_timestamps

            count = len(valid_timestamps)
            if count >= limit:
                remaining = 0
                reset_seconds = int(valid_timestamps[0] + window_seconds - now) if valid_timestamps else window_seconds
                return False, remaining, max(1, reset_seconds)

            self._requests[key].append(now)
            remaining = limit - count - 1
            return True, remaining, window_seconds

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        client_ip = request.client.host if request.client else "127.0.0.1"
        path = request.url.path

        # Sensitive Authentication & Reset Endpoints
        if path in ["/api/v1/auth/login", "/dev/auth/login"] or path.endswith("/reset-password"):
            key = f"auth_sensitive:{client_ip}:{path}"
            limit = settings.RATE_LIMIT_LOGIN_PER_MINUTE
            allowed, remaining, reset_sec = self._clean_and_check(key, limit=limit, window_seconds=60)
            if not allowed:
                logger.warning(f"Rate limit exceeded for client {client_ip} on {path}")
                return JSONResponse(
                    status_code=429,
                    content={
                        "success": False,
                        "error": {
                            "code": "RATE_LIMIT_EXCEEDED",
                            "message": f"Too many authentication attempts. Please try again in {reset_sec} seconds.",
                            "details": {"retry_after_seconds": reset_sec},
                        },
                    },
                    headers={"Retry-After": str(reset_sec)},
                )

        # Global IP Rate Limit (skip in testing unless configured)
        if settings.APP_ENV != "testing":
            effective_limit = settings.RATE_LIMIT_GLOBAL_PER_MINUTE
            if (settings.DEBUG or settings.APP_ENV == "development") and client_ip in ("127.0.0.1", "localhost", "::1"):
                effective_limit = max(effective_limit, 600)

            global_key = f"global:{client_ip}"
            allowed, remaining, reset_sec = self._clean_and_check(
                global_key, limit=effective_limit, window_seconds=60
            )
            if not allowed:
                logger.warning(f"Global rate limit exceeded for client {client_ip}")
                return JSONResponse(
                    status_code=429,
                    content={
                        "success": False,
                        "error": {
                            "code": "GLOBAL_RATE_LIMIT_EXCEEDED",
                            "message": f"Too many requests from your IP. Please try again in {reset_sec} seconds.",
                            "details": {"retry_after_seconds": reset_sec},
                        },
                    },
                    headers={"Retry-After": str(reset_sec)},
                )

        return await call_next(request)

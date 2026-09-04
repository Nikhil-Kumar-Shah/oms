"""
FastAPI Application Entry Point & Lifespan Management
Paradox Sports OMS - Hardened Production Boundary
"""

import secrets
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles

from app.api.router import api_v1_router
from app.core.config import get_settings
from app.core.database import engine, verify_database_connection
from app.core.exceptions import (
    AppException,
    app_exception_handler,
    generic_exception_handler,
    validation_exception_handler,
)
from app.core.logging import get_logger, setup_logging
from app.core.middleware import (
    RateLimitingMiddleware,
    RequestCorrelationMiddleware,
    SecurityHeadersMiddleware,
)

settings = get_settings()

# Configure logging at module import
setup_logging(settings.LOG_LEVEL)
logger = get_logger("app.main")

# HTTP Basic Authentication Scheme for Restricted Documentation
docs_basic_auth = HTTPBasic(auto_error=False)


def verify_docs_credentials(credentials: Optional[HTTPBasicCredentials] = Depends(docs_basic_auth)) -> str:
    """
    Enforces HTTP Basic Authentication for Swagger UI (/docs), ReDoc (/redoc),
    and OpenAPI specification (/openapi.json).
    Uses environment configuration (API_DOCS_USERNAME and API_DOCS_PASSWORD).
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required for API documentation",
            headers={"WWW-Authenticate": "Basic"},
        )

    is_user_valid = secrets.compare_digest(credentials.username, settings.API_DOCS_USERNAME)
    is_pass_valid = secrets.compare_digest(credentials.password, settings.API_DOCS_PASSWORD)

    if not (is_user_valid and is_pass_valid):
        logger.warning(f"Unauthorized documentation access attempt for user '{credentials.username}'")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid documentation credentials",
            headers={"WWW-Authenticate": "Basic"},
        )

    return credentials.username


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application Lifespan Context Manager.
    Validates PostgreSQL database connection on startup and cleans up on shutdown.
    """
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION} [{settings.APP_ENV}]")

    # Startup: Verify PostgreSQL database connectivity
    try:
        health_info = verify_database_connection()
        logger.info(
            f"PostgreSQL connection verified successfully. "
            f"Latency: {health_info.get('latency_ms')}ms"
        )
        from app.core.database import SessionLocal, sync_database_enums
        sync_database_enums()
        from app.services.rbac_service import ensure_canonical_roles_and_permissions
        from app.services.config_service import ensure_canonical_system_configs
        with SessionLocal() as db_session:
            ensure_canonical_roles_and_permissions(db_session)
            ensure_canonical_system_configs(db_session)
            db_session.commit()
    except Exception as exc:
        logger.critical(f"FATAL: PostgreSQL database is unreachable on startup: {exc}")

    yield

    # Shutdown: Clean up database pool connections
    logger.info("Shutting down application. Disposing PostgreSQL connection pool...")
    engine.dispose()
    logger.info("Application shutdown complete.")


def create_app() -> FastAPI:
    """Application factory for FastAPI instance with complete production middleware stack."""
    # Disable default unauthenticated docs routes
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="Operations Management System for Paradox Sports Department",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )

    # 1. Rate Limiting Middleware
    app.add_middleware(RateLimitingMiddleware)

    # 2. Security Headers Middleware
    app.add_middleware(SecurityHeadersMiddleware)

    # 3. CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 4. Trusted Host Middleware (when allowed hosts is explicitly restricted)
    if settings.ALLOWED_HOSTS and "*" not in settings.ALLOWED_HOSTS:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=settings.ALLOWED_HOSTS,
        )

    # 5. Correlation ID & Latency Tracking Middleware
    app.add_middleware(RequestCorrelationMiddleware)

    # Exception Handlers
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

    # Static Assets (for potential public assets)
    app.mount("/static", StaticFiles(directory="static"), name="static")

    # Authoritative API v1 Routes (/dev removed completely)
    app.include_router(api_v1_router)

    # -------------------------------------------------------------------------
    # Public Root & Minimal Health Probes
    # -------------------------------------------------------------------------
    @app.get("/", tags=["Public Boundary"], summary="API Root Metadata")
    async def root_metadata():
        """Public minimal service discovery metadata. Does not redirect to /dev."""
        return {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "status": "online",
        }

    @app.get("/health", tags=["Public Boundary"], summary="Public Minimal Health Probe")
    async def public_health():
        """Public operational health check. Returns safe status without leaking internal details."""
        return {
            "status": "healthy",
        }

    # -------------------------------------------------------------------------
    # Restricted Documentation Routes (Protected by HTTP Basic Auth)
    # -------------------------------------------------------------------------
    if settings.ENABLE_DOCS:
        @app.get("/docs", include_in_schema=False, response_class=HTMLResponse)
        async def restricted_swagger_ui(username: str = Depends(verify_docs_credentials)):
            """Restricted Swagger UI for authenticated administrators and developers."""
            return get_swagger_ui_html(
                openapi_url="/openapi.json",
                title=f"{settings.APP_NAME} - Swagger UI",
            )

        @app.get("/redoc", include_in_schema=False, response_class=HTMLResponse)
        async def restricted_redoc(username: str = Depends(verify_docs_credentials)):
            """Restricted ReDoc UI for authenticated administrators and developers."""
            return get_redoc_html(
                openapi_url="/openapi.json",
                title=f"{settings.APP_NAME} - ReDoc",
            )

        @app.get("/openapi.json", include_in_schema=False, response_class=JSONResponse)
        async def restricted_openapi_schema(username: str = Depends(verify_docs_credentials)):
            """Restricted OpenAPI specification JSON."""
            return get_openapi(
                title=app.title,
                version=app.version,
                description=app.description,
                routes=app.routes,
            )

    return app


app = create_app()

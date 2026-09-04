"""
Health Check API Routes
"""

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from app.core.health import get_app_health, get_database_health
from app.schemas.health import AppHealthResponse, DatabaseHealthResponse

router = APIRouter(prefix="/health", tags=["Health"])


@router.get(
    "",
    response_model=AppHealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Application Health",
    description="Returns current application liveness and metadata.",
)
async def check_app_health() -> AppHealthResponse:
    return AppHealthResponse(**get_app_health())


@router.get(
    "/database",
    response_model=DatabaseHealthResponse,
    status_code=status.HTTP_200_OK,
    summary="PostgreSQL Database Health",
    description="Performs live query against PostgreSQL to verify connectivity and latency.",
    responses={
        503: {
            "model": DatabaseHealthResponse,
            "description": "Database service is unavailable or connection failed",
        }
    },
)
async def check_database_health():
    health_data = get_database_health()
    if health_data.get("status") != "healthy":
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=health_data,
        )
    return DatabaseHealthResponse(**health_data)

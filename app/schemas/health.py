"""
Health Check Schemas
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class AppHealthResponse(BaseModel):
    status: str = Field(..., example="healthy")
    app_name: str = Field(..., example="Paradox Sports OMS")
    version: str = Field(..., example="0.1.0")
    environment: str = Field(..., example="development")
    timestamp: str


class DatabaseHealthResponse(BaseModel):
    status: str = Field(..., example="healthy")
    database: str = Field(..., example="healthy")
    latency_ms: Optional[float] = Field(None, example=45.2)
    error: Optional[str] = None
    timestamp: str

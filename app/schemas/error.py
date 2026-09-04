"""
Standard Error Schemas
"""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str = Field(..., example="VALIDATION_ERROR")
    message: str = Field(..., example="Field 'name' is required")
    details: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    success: bool = Field(default=False)
    error: ErrorDetail

"""
API Routes for SystemTestRecord Foundation Verification
"""

from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.test_record import (
    SystemTestRecordCreate,
    SystemTestRecordListResponse,
    SystemTestRecordResponse,
)
from app.services.test_record_service import SystemTestRecordService

router = APIRouter(prefix="/test-records", tags=["System Test Records"])


@router.post(
    "",
    response_model=SystemTestRecordResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Test Record",
    description="Creates a new temporary test record to verify database write and transaction commit.",
)
def create_test_record(
    payload: SystemTestRecordCreate,
    db: Session = Depends(get_db),
) -> SystemTestRecordResponse:
    service = SystemTestRecordService(db)
    record = service.create(payload)
    return SystemTestRecordResponse.model_validate(record)


@router.get(
    "",
    response_model=SystemTestRecordListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Test Records",
    description="Retrieves all system test records from PostgreSQL.",
)
def list_test_records(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> SystemTestRecordListResponse:
    service = SystemTestRecordService(db)
    records = service.list_all(limit=limit, offset=offset)
    total = service.count()
    return SystemTestRecordListResponse(
        total=total,
        items=[SystemTestRecordResponse.model_validate(r) for r in records],
    )


@router.get(
    "/{record_id}",
    response_model=SystemTestRecordResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Test Record by ID",
    description="Retrieves a specific test record by UUID from PostgreSQL.",
)
def get_test_record(
    record_id: UUID,
    db: Session = Depends(get_db),
) -> SystemTestRecordResponse:
    service = SystemTestRecordService(db)
    record = service.get_by_id(record_id)
    return SystemTestRecordResponse.model_validate(record)

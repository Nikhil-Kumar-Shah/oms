"""
Ownership Transfers & Account Succession API Endpoints
"""

from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.api.dependencies import require_permissions, require_user_session
from app.core.database import get_db
from app.models.governance import TransferResourceType, TransferStatus
from app.models.user import User
from app.schemas.governance import (
    AccountSuccessionCreate,
    AccountSuccessionPreviewResponse,
    OwnershipTransferCreate,
    OwnershipTransferListResponse,
    OwnershipTransferResponse,
    OwnershipTransferReviewRequest,
)
from app.services.transfer_service import OwnershipTransferService

router = APIRouter(prefix="/transfers", tags=["Ownership Transfers & Account Succession"])


def _format_transfer_response(t) -> OwnershipTransferResponse:
    return OwnershipTransferResponse(
        id=t.id,
        resource_type=t.resource_type,
        resource_id=t.resource_id,
        current_owner_id=t.current_owner_id,
        current_owner_username=t.current_owner.username if t.current_owner else None,
        requested_owner_id=t.requested_owner_id,
        requested_owner_username=t.requested_owner.username if t.requested_owner else None,
        requested_by_id=t.requested_by_id,
        requested_by_username=t.requested_by.username if t.requested_by else None,
        reviewed_by_id=t.reviewed_by_id,
        reviewed_by_username=t.reviewed_by.username if t.reviewed_by else None,
        reason=t.reason,
        status=t.status,
        remarks=t.remarks,
        created_at=t.created_at,
        reviewed_at=t.reviewed_at,
        completed_at=t.completed_at,
    )


@router.get("", response_model=OwnershipTransferListResponse, dependencies=[Depends(require_permissions(["transfers.read"]))])
def list_transfers(
    resource_type: Optional[TransferResourceType] = Query(None),
    status: Optional[TransferStatus] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    service = OwnershipTransferService(db)
    items, total = service.list_transfers(
        resource_type=resource_type,
        status=status,
        limit=limit,
        offset=offset,
    )
    return OwnershipTransferListResponse(total=total, items=[_format_transfer_response(t) for t in items])


@router.get(
    "/succession-preview",
    response_model=AccountSuccessionPreviewResponse,
    summary="Preview Account Ownership Succession",
    description="Calculates active operational responsibilities transitioning to successor while confirming historical data preservation.",
    dependencies=[Depends(require_permissions(["transfers.read"]))],
)
def preview_account_succession(
    previous_user_id: UUID = Query(..., description="Departing previous user account ID"),
    successor_user_id: UUID = Query(..., description="Successor user account ID"),
    db: Session = Depends(get_db),
) -> AccountSuccessionPreviewResponse:
    service = OwnershipTransferService(db)
    return service.preview_account_succession(
        previous_user_id=previous_user_id,
        successor_user_id=successor_user_id,
    )


@router.post(
    "/succession",
    response_model=OwnershipTransferResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Initiate Account Ownership Succession",
    description="Initiates governed account succession workflow subject to four-eyes review.",
    dependencies=[Depends(require_permissions(["transfers.request"]))],
)
def initiate_account_succession(
    data: AccountSuccessionCreate,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
) -> OwnershipTransferResponse:
    service = OwnershipTransferService(db)
    transfer = service.request_transfer(
        OwnershipTransferCreate(
            resource_type=TransferResourceType.ACCOUNT,
            resource_id=data.previous_user_id,
            requested_owner_id=data.successor_user_id,
            reason=data.reason,
        ),
        requested_by_id=current_user.id,
    )
    db.commit()
    return _format_transfer_response(service.get_transfer_by_id(transfer.id))


@router.post("", response_model=OwnershipTransferResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_permissions(["transfers.request"]))])
def request_ownership_transfer(
    data: OwnershipTransferCreate,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    service = OwnershipTransferService(db)
    transfer = service.request_transfer(data, requested_by_id=current_user.id)
    db.commit()
    return _format_transfer_response(service.get_transfer_by_id(transfer.id))


@router.get("/{transfer_id}", response_model=OwnershipTransferResponse, dependencies=[Depends(require_permissions(["transfers.read"]))])
def get_transfer(
    transfer_id: UUID,
    db: Session = Depends(get_db),
):
    service = OwnershipTransferService(db)
    return _format_transfer_response(service.get_transfer_by_id(transfer_id))


@router.post("/{transfer_id}/review", response_model=OwnershipTransferResponse, dependencies=[Depends(require_permissions(["transfers.approve"]))])
def review_ownership_transfer(
    transfer_id: UUID,
    data: OwnershipTransferReviewRequest,
    current_user: User = Depends(require_user_session),
    db: Session = Depends(get_db),
):
    service = OwnershipTransferService(db)
    transfer = service.review_transfer(transfer_id, reviewer_id=current_user.id, data=data)
    db.commit()
    return _format_transfer_response(service.get_transfer_by_id(transfer.id))

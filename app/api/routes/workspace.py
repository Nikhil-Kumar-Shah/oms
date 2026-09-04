"""
Unified Operational Workspace API Routes
Paradox Sports OMS - Phase 1 Workspace Enhancements
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.api.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.workspace import UnifiedMyWorkResponse
from app.services.workspace_service import WorkspaceService

router = APIRouter(prefix="/workspace", tags=["Unified Workspace"])


@router.get("/my-work", response_model=UnifiedMyWorkResponse)
def get_my_work(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieves the server-authoritative unified 'My Work' operational dashboard.
    Identity is strictly derived from the authenticated session token.
    """
    return WorkspaceService.get_unified_my_work(db, current_user)

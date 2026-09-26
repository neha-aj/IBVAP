from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ibvap_common.auth import TokenPayload, require_role

from app.db.session import get_db
from app.schemas.admin_audit_log import AdminAuditLogListResponse, AdminAuditLogEntryRead, ChainIntegrity
from app.services import admin_audit_log_service

router = APIRouter(prefix="/api/v1/cameras/audit-log", tags=["admin-audit-log"])


@router.get("/verify-chain", response_model=ChainIntegrity)
async def verify_chain(
    session: AsyncSession = Depends(get_db),
    _user: TokenPayload = Depends(require_role("admin")),
) -> ChainIntegrity:
    """Recomputes the entire admin-action audit log from genesis and
    reports whether it's still intact -- i.e. whether any past entry has
    been edited, deleted, or reordered since it was written."""
    intact, checked, broken_id = await admin_audit_log_service.verify_chain(session)
    return ChainIntegrity(intact=intact, entries_checked=checked, first_broken_entry_id=broken_id)


@router.get("", response_model=AdminAuditLogListResponse)
async def list_admin_audit_log(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200, alias="pageSize"),
    session: AsyncSession = Depends(get_db),
    _user: TokenPayload = Depends(require_role("admin")),
) -> AdminAuditLogListResponse:
    """Every admin-level camera action (create/update/delete), newest
    first -- who did it, when, and a short summary of what changed."""
    entries, total = await admin_audit_log_service.list_entries(session, page=page, page_size=page_size)
    return AdminAuditLogListResponse(
        items=[
            AdminAuditLogEntryRead(
                id=str(e.id), action=e.action, actor=e.actor, target_type=e.target_type,
                target_id=e.target_id, details=e.details, entry_hash=e.entry_hash, created_at=e.created_at,
            )
            for e in entries
        ],
        total=total, page=page, page_size=page_size,
    )

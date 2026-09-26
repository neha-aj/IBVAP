"""Hash-chained log of admin-level actions on cameras (create/update/
delete) -- who did it, when, and a short human-readable summary. Same
chaining idea as media-service's evidence chain-of-custody log
(app/services/audit_log_service.py there): each entry's hash covers its
own fields plus the previous entry's hash, so altering or deleting a past
row breaks every hash after it, which `verify_chain` detects by
recomputing the chain from genesis. This is a separate, service-local
chain -- not shared with media-service's."""

from __future__ import annotations

import datetime as dt
import hashlib
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_audit_log import AdminAuditChainTip, AdminAuditLogEntry

GENESIS_HASH = "0" * 64
_TIP_ID = 1
_ENTRY_PREFIX = b"IBVAP-ADMIN-AUDIT/1\0"


def _entry_hash(
    *, prev_hash: str, action: str, actor: str | None, target_type: str, target_id: str,
    details: str | None, created_at: dt.datetime,
) -> str:
    payload = _ENTRY_PREFIX + "\0".join(
        [prev_hash, action, actor or "", target_type, target_id, details or "", created_at.isoformat()]
    ).encode()
    return hashlib.sha256(payload).hexdigest()


async def append_audit_entry(
    session: AsyncSession,
    *,
    action: str,
    actor: str | None,
    target_type: str,
    target_id: str,
    details: str | None,
) -> AdminAuditLogEntry:
    """Appends one entry to the chain. `SELECT ... FOR UPDATE` on the tip
    row serializes concurrent appends onto a single, unforked chain."""
    tip = (
        await session.execute(select(AdminAuditChainTip).where(AdminAuditChainTip.id == _TIP_ID).with_for_update())
    ).scalar_one()

    created_at = dt.datetime.now(dt.UTC)
    entry_hash = _entry_hash(
        prev_hash=tip.entry_hash, action=action, actor=actor, target_type=target_type,
        target_id=target_id, details=details, created_at=created_at,
    )
    entry = AdminAuditLogEntry(
        action=action, actor=actor, target_type=target_type, target_id=target_id, details=details,
        prev_hash=tip.entry_hash, entry_hash=entry_hash, created_at=created_at,
    )
    session.add(entry)
    tip.entry_hash = entry_hash
    tip.updated_at = created_at
    await session.commit()
    return entry


async def list_entries(session: AsyncSession, *, page: int = 1, page_size: int = 50) -> tuple[list[AdminAuditLogEntry], int]:
    total = (await session.execute(select(func.count()).select_from(AdminAuditLogEntry))).scalar_one()
    result = await session.execute(
        select(AdminAuditLogEntry)
        .order_by(AdminAuditLogEntry.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(result.scalars().all()), int(total)


async def verify_chain(session: AsyncSession) -> tuple[bool, int, str | None]:
    """Recomputes the whole chain from genesis. Returns
    `(intact, entries_checked, first_broken_entry_id)`."""
    result = await session.execute(select(AdminAuditLogEntry).order_by(AdminAuditLogEntry.created_at))
    entries = list(result.scalars().all())

    prev_hash = GENESIS_HASH
    for entry in entries:
        expected = _entry_hash(
            prev_hash=prev_hash, action=entry.action, actor=entry.actor, target_type=entry.target_type,
            target_id=entry.target_id, details=entry.details, created_at=entry.created_at,
        )
        if entry.prev_hash != prev_hash or entry.entry_hash != expected:
            return False, len(entries), str(entry.id)
        prev_hash = entry.entry_hash

    return True, len(entries), None

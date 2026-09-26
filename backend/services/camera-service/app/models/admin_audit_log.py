import datetime as dt
import uuid

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class AdminAuditLogEntry(Base):
    """Who did what admin-level action to a camera, and when -- distinct
    from media-service's evidence chain-of-custody log, which only covers
    view/download/verify of evidence, not admin CRUD. Same hash-chained
    shape as that log (each entry's hash covers its own fields plus the
    previous entry's hash, so editing/deleting a past row is detectable via
    verify_chain) -- this is a separate, service-local implementation
    (camera-service's own schema/table), not a shared one: DB Spec's "no
    cross-schema foreign keys, no shared ORM models" boundary means each
    service owns its own audit table the same way media-service does."""

    __tablename__ = "admin_audit_log"
    __table_args__ = {"schema": "camera"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    action: Mapped[str] = mapped_column(String, nullable=False)  # "camera.created" | "camera.updated" | "camera.deleted"
    # Who, if known -- null only if a token somehow carried no username,
    # which shouldn't happen in practice (require_role always resolves one).
    actor: Mapped[str | None] = mapped_column(String, nullable=True)
    target_type: Mapped[str] = mapped_column(String, nullable=False)  # "camera"
    target_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    details: Mapped[str | None] = mapped_column(String, nullable=True)  # short human-readable summary
    prev_hash: Mapped[str] = mapped_column(String, nullable=False)
    entry_hash: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AdminAuditChainTip(Base):
    """Singleton row holding the current chain tip's hash -- read with
    `SELECT ... FOR UPDATE` before every append so concurrent admin actions
    serialize onto one unforked chain, same reasoning as media-service's
    own AuditChainTip."""

    __tablename__ = "admin_audit_chain_tip"
    __table_args__ = {"schema": "camera"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entry_hash: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)

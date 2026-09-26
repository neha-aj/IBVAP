"""Admin action audit log (hash-chained), for camera create/update/delete

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-27

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_GENESIS_HASH = "0" * 64


def upgrade() -> None:
    op.create_table(
        "admin_audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                   server_default=sa.text("gen_random_uuid()")),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("actor", sa.String(), nullable=True),
        sa.Column("target_type", sa.String(), nullable=False),
        sa.Column("target_id", sa.String(), nullable=False),
        sa.Column("details", sa.String(), nullable=True),
        sa.Column("prev_hash", sa.String(), nullable=False),
        sa.Column("entry_hash", sa.String(), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema="camera",
    )
    op.create_index("ix_camera_admin_audit_log_target_id", "admin_audit_log", ["target_id"], schema="camera")

    op.create_table(
        "admin_audit_chain_tip",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entry_hash", sa.String(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        schema="camera",
    )
    # Single seeded row (id=1) so `append_audit_entry` can always
    # `SELECT ... FOR UPDATE` it without a first-row special case.
    op.execute(
        f"INSERT INTO camera.admin_audit_chain_tip (id, entry_hash, updated_at) "
        f"VALUES (1, '{_GENESIS_HASH}', now())"
    )


def downgrade() -> None:
    op.drop_table("admin_audit_chain_tip", schema="camera")
    op.drop_table("admin_audit_log", schema="camera")

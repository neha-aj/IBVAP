"""Admin-tunable rule thresholds table

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-27

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rule_setting",
        sa.Column("key", sa.String(), primary_key=True),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("updated_by", sa.String(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        schema="events",
    )


def downgrade() -> None:
    op.drop_table("rule_setting", schema="events")

"""add pairing_mode to stage_items

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-09-01 00:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

revision: str | None = "d4e5f6a7b8c9"
down_revision: str | None = "c3d4e5f6a7b8"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "stage_items",
        sa.Column("pairing_mode", sa.Text(), server_default="SOCIAL", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("stage_items", "pairing_mode")

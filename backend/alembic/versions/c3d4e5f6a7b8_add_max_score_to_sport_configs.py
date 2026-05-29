"""add max_score to sport_configs

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-05-29 21:52:00.000000

"""

import sqlalchemy as sa

from alembic import op

revision: str | None = "c3d4e5f6a7b8"
down_revision: str | None = "b2c3d4e5f6a7"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "sport_configs",
        sa.Column("max_score", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("sport_configs", "max_score")

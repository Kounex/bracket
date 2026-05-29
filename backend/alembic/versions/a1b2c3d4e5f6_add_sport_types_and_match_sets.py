"""add sport types and match sets

Revision ID: a1b2c3d4e5f6
Revises: c1ab44651e79
Create Date: 2026-05-29 20:00:00.000000

"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM

from alembic import op

# revision identifiers, used by Alembic.
revision: str | None = "a1b2c3d4e5f6"
down_revision: str | None = "c1ab44651e79"
branch_labels: str | None = None
depends_on: str | None = None

sport_type_enum = ENUM(
    "SIMPLE",
    "TENNIS",
    "BADMINTON",
    "TABLE_TENNIS",
    "VOLLEYBALL",
    "PADEL",
    name="sport_type",
    create_type=True,
)


def upgrade() -> None:
    sport_type_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "tournaments",
        sa.Column("sport_type", sport_type_enum, server_default="SIMPLE", nullable=False),
    )

    op.create_table(
        "sport_configs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tournament_id", sa.BigInteger(), nullable=False),
        sa.Column("num_sets", sa.Integer(), nullable=False),
        sa.Column("points_per_set", sa.Integer(), nullable=True),
        sa.Column("points_last_set", sa.Integer(), nullable=True),
        sa.Column("min_point_difference", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["tournament_id"], ["tournaments.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tournament_id"),
    )
    op.create_index(op.f("ix_sport_configs_id"), "sport_configs", ["id"], unique=False)

    op.create_table(
        "match_sets",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("match_id", sa.BigInteger(), nullable=False),
        sa.Column("set_number", sa.Integer(), nullable=False),
        sa.Column("score1", sa.Integer(), server_default="0", nullable=False),
        sa.Column("score2", sa.Integer(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(["match_id"], ["matches.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("match_id", "set_number"),
    )
    op.create_index(op.f("ix_match_sets_id"), "match_sets", ["id"], unique=False)
    op.create_index("ix_match_sets_match_id", "match_sets", ["match_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_match_sets_match_id", table_name="match_sets")
    op.drop_index(op.f("ix_match_sets_id"), table_name="match_sets")
    op.drop_table("match_sets")
    op.drop_index(op.f("ix_sport_configs_id"), table_name="sport_configs")
    op.drop_table("sport_configs")
    op.drop_column("tournaments", "sport_type")
    sport_type_enum.drop(op.get_bind())

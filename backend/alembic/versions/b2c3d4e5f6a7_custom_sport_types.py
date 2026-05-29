"""custom sport types - move sport identity into sport_configs

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-29 21:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str | None = "b2c3d4e5f6a7"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "sport_configs",
        sa.Column("name", sa.String(), server_default="Custom", nullable=False),
    )

    op.execute("""
        UPDATE sport_configs
        SET name = tournaments.sport_type
        FROM tournaments
        WHERE sport_configs.tournament_id = tournaments.id
    """)

    op.drop_column("tournaments", "sport_type")
    op.execute("DROP TYPE IF EXISTS sport_type")


def downgrade() -> None:
    sport_type_enum = sa.Enum(
        "SIMPLE", "TENNIS", "BADMINTON", "TABLE_TENNIS", "VOLLEYBALL", "PADEL",
        name="sport_type", create_type=True,
    )
    sport_type_enum.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "tournaments",
        sa.Column("sport_type", sport_type_enum, server_default="SIMPLE", nullable=False),
    )

    op.execute("""
        UPDATE tournaments
        SET sport_type = sport_configs.name::sport_type
        FROM sport_configs
        WHERE sport_configs.tournament_id = tournaments.id
          AND sport_configs.name IN ('SIMPLE', 'TENNIS', 'BADMINTON', 'TABLE_TENNIS', 'VOLLEYBALL', 'PADEL')
    """)

    op.drop_column("sport_configs", "name")

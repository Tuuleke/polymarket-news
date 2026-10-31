"""store timestamps with time zone

Existing naive values were written with datetime.utcnow() or parsed from
UTC ISO strings, so they are reinterpreted as UTC.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-31 15:00:00

"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUMNS = [("markets", "end_date"), ("markets", "fetched_at"), ("articles", "created_at")]


def upgrade() -> None:
    for table, column in _COLUMNS:
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN {column} "
            f"TYPE timestamptz USING {column} AT TIME ZONE 'UTC'"
        )


def downgrade() -> None:
    for table, column in _COLUMNS:
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN {column} "
            f"TYPE timestamp USING {column} AT TIME ZONE 'UTC'"
        )

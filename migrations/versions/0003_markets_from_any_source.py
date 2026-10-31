"""markets from any source

Adds the `source` column and source-neutral identifiers so markets from Kalshi,
Manifold and Polymarket share one table. Existing rows came from Polymarket.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-31 16:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("markets", "polymarket_id", new_column_name="external_id")
    op.alter_column("markets", "clob_token_id", new_column_name="history_ref")
    op.drop_index("ix_markets_polymarket_id", table_name="markets")
    # server_default backfills existing rows, then is dropped so new rows must say.
    op.add_column(
        "markets", sa.Column("source", sa.String(), nullable=False, server_default="polymarket")
    )
    op.add_column(
        "markets", sa.Column("volume_unit", sa.String(), nullable=False, server_default="usd")
    )
    op.alter_column("markets", "source", server_default=None)
    op.alter_column("markets", "volume_unit", server_default=None)
    op.add_column("markets", sa.Column("event_id", sa.String(), nullable=True))
    op.add_column("markets", sa.Column("url", sa.String(), nullable=True))
    op.create_unique_constraint(
        "uq_markets_source_external_id", "markets", ["source", "external_id"]
    )


def downgrade() -> None:
    # The old schema can only hold Polymarket markets; others are dropped with their data.
    others = "SELECT id FROM markets WHERE source <> 'polymarket'"
    op.execute(f"DELETE FROM articles WHERE market_id IN ({others})")
    op.execute(f"DELETE FROM market_snapshots WHERE market_id IN ({others})")
    op.execute("DELETE FROM markets WHERE source <> 'polymarket'")
    op.drop_constraint("uq_markets_source_external_id", "markets", type_="unique")
    op.drop_column("markets", "url")
    op.drop_column("markets", "event_id")
    op.drop_column("markets", "volume_unit")
    op.drop_column("markets", "source")
    op.create_index("ix_markets_polymarket_id", "markets", ["external_id"], unique=True)
    op.alter_column("markets", "history_ref", new_column_name="clob_token_id")
    op.alter_column("markets", "external_id", new_column_name="polymarket_id")

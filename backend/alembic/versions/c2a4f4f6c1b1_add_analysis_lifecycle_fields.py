"""Add durable analysis lifecycle and version fields.

Revision ID: c2a4f4f6c1b1
Revises: 8beff4d8d7df
Create Date: 2026-09-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c2a4f4f6c1b1"
down_revision: Union[str, Sequence[str], None] = "8beff4d8d7df"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "analysis_sessions",
        sa.Column("analysis_version", sa.String(), nullable=False, server_default="1"),
    )
    op.add_column("analysis_sessions", sa.Column("model_version", sa.String(), nullable=True))
    op.add_column("analysis_sessions", sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("analysis_sessions", sa.Column("error", sa.Text(), nullable=True))
    op.alter_column("analysis_sessions", "analysis_version", server_default=None)


def downgrade() -> None:
    op.drop_column("analysis_sessions", "error")
    op.drop_column("analysis_sessions", "processed_at")
    op.drop_column("analysis_sessions", "model_version")
    op.drop_column("analysis_sessions", "analysis_version")
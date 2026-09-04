"""Scope conversations to the analysis version.

Revision ID: e8f7a6b5c4d3
Revises: d7f6a1b2c3d4
Create Date: 2026-09-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e8f7a6b5c4d3"
down_revision: Union[str, Sequence[str], None] = "d7f6a1b2c3d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("conversations", sa.Column("analysis_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_conversations_analysis_id",
        "conversations",
        "analysis_sessions",
        ["analysis_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_conversations_analysis_id", "conversations", ["analysis_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_conversations_analysis_id", table_name="conversations")
    op.drop_constraint("fk_conversations_analysis_id", "conversations", type_="foreignkey")
    op.drop_column("conversations", "analysis_id")
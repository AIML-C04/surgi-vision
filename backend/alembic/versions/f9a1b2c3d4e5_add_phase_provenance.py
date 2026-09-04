"""Add phase recognition provenance.

Revision ID: f9a1b2c3d4e5
Revises: e8f7a6b5c4d3
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f9a1b2c3d4e5"
down_revision: Union[str, Sequence[str], None] = "e8f7a6b5c4d3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("surgical_phases", sa.Column("model_provider", sa.String(), nullable=True))
    op.add_column("surgical_phases", sa.Column("model_version", sa.String(), nullable=True))
    op.add_column("surgical_phases", sa.Column("taxonomy_version", sa.String(), nullable=True))
    op.add_column("surgical_phases", sa.Column("evidence", sa.JSON(), nullable=True))
    op.add_column("surgical_phases", sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=True))


def downgrade() -> None:
    op.drop_column("surgical_phases", "created_at")
    op.drop_column("surgical_phases", "evidence")
    op.drop_column("surgical_phases", "taxonomy_version")
    op.drop_column("surgical_phases", "model_version")
    op.drop_column("surgical_phases", "model_provider")
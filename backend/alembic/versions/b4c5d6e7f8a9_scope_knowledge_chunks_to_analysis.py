"""Scope knowledge chunks to an analysis version.

Revision ID: b4c5d6e7f8a9
Revises: a1b2c3d4e5f6
"""

from alembic import op
import sqlalchemy as sa


revision = "b4c5d6e7f8a9"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("video_knowledge_chunks", sa.Column("analysis_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_video_knowledge_chunks_analysis_id",
        "video_knowledge_chunks",
        "analysis_sessions",
        ["analysis_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_video_knowledge_chunks_analysis_id", "video_knowledge_chunks", ["analysis_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_video_knowledge_chunks_analysis_id", table_name="video_knowledge_chunks")
    op.drop_constraint("fk_video_knowledge_chunks_analysis_id", "video_knowledge_chunks", type_="foreignkey")
    op.drop_column("video_knowledge_chunks", "analysis_id")

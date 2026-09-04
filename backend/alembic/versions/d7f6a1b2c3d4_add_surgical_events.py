"""Add structured surgical events.

Revision ID: d7f6a1b2c3d4
Revises: c2a4f4f6c1b1
Create Date: 2026-09-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d7f6a1b2c3d4"
down_revision: Union[str, Sequence[str], None] = "c2a4f4f6c1b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "surgical_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("video_id", sa.Uuid(), nullable=False),
        sa.Column("analysis_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("start_time", sa.Float(), nullable=False),
        sa.Column("end_time", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=True),
        sa.Column("source_detection_ids", sa.JSON(), nullable=True),
        sa.Column("source_track_ids", sa.JSON(), nullable=True),
        sa.Column("model_version", sa.String(), nullable=True),
        sa.Column("dedupe_key", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=True),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["analysis_id"], ["analysis_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("analysis_id", "dedupe_key", name="uq_surgical_events_analysis_dedupe"),
    )
    op.create_index("ix_surgical_events_id", "surgical_events", ["id"], unique=False)
    op.create_index("ix_surgical_events_video_id", "surgical_events", ["video_id"], unique=False)
    op.create_index("ix_surgical_events_analysis_id", "surgical_events", ["analysis_id"], unique=False)
    op.create_index("ix_surgical_events_event_type", "surgical_events", ["event_type"], unique=False)
    op.create_index("ix_surgical_events_start_time", "surgical_events", ["start_time"], unique=False)
    op.create_index("ix_surgical_events_video_start", "surgical_events", ["video_id", "start_time"], unique=False)
    op.create_index("ix_surgical_events_analysis_start", "surgical_events", ["analysis_id", "start_time"], unique=False)
    op.add_column("video_knowledge_chunks", sa.Column("metadata", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("video_knowledge_chunks", "metadata")
    op.drop_index("ix_surgical_events_analysis_start", table_name="surgical_events")
    op.drop_index("ix_surgical_events_video_start", table_name="surgical_events")
    op.drop_index("ix_surgical_events_start_time", table_name="surgical_events")
    op.drop_index("ix_surgical_events_event_type", table_name="surgical_events")
    op.drop_index("ix_surgical_events_analysis_id", table_name="surgical_events")
    op.drop_index("ix_surgical_events_video_id", table_name="surgical_events")
    op.drop_index("ix_surgical_events_id", table_name="surgical_events")
    op.drop_table("surgical_events")

"""Add research evaluation entities and analysis performance fields.

Revision ID: a1b2c3d4e5f6
Revises: f9a1b2c3d4e5
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "f9a1b2c3d4e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("analysis_sessions", sa.Column("processing_duration", sa.Float(), nullable=True))
    op.add_column("analysis_sessions", sa.Column("processed_frames", sa.Integer(), nullable=True))
    op.add_column("analysis_sessions", sa.Column("skipped_frames", sa.Integer(), nullable=True))
    op.create_table("evaluation_datasets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("version", sa.String(), nullable=False),
        sa.Column("annotation_format", sa.String(), nullable=False),
        sa.Column("taxonomy_version", sa.String(), nullable=True),
        sa.Column("taxonomy_classes", sa.JSON(), nullable=True),
        sa.Column("ground_truth_available", sa.Boolean(), nullable=False),
        sa.Column("annotations", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evaluation_datasets_id", "evaluation_datasets", ["id"], unique=False)
    op.create_table("evaluation_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("analysis_id", sa.Uuid(), nullable=True),
        sa.Column("model_provider", sa.String(), nullable=True),
        sa.Column("model_name", sa.String(), nullable=True),
        sa.Column("model_version", sa.String(), nullable=True),
        sa.Column("checkpoint_identifier", sa.String(), nullable=True),
        sa.Column("task", sa.String(), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("sample_counts", sa.JSON(), nullable=True),
        sa.Column("metrics", sa.JSON(), nullable=True),
        sa.Column("errors", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=True),
        sa.ForeignKeyConstraint(["dataset_id"], ["evaluation_datasets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["analysis_id"], ["analysis_sessions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evaluation_runs_id", "evaluation_runs", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_evaluation_runs_id", table_name="evaluation_runs")
    op.drop_table("evaluation_runs")
    op.drop_index("ix_evaluation_datasets_id", table_name="evaluation_datasets")
    op.drop_table("evaluation_datasets")
    op.drop_column("analysis_sessions", "skipped_frames")
    op.drop_column("analysis_sessions", "processed_frames")
    op.drop_column("analysis_sessions", "processing_duration")
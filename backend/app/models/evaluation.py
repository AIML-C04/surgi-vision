import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, JSON, String, Text, Uuid
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class EvaluationDataset(Base):
    __tablename__ = "evaluation_datasets"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    version = Column(String, nullable=False)
    annotation_format = Column(String, nullable=False, default="json-manifest")
    taxonomy_version = Column(String)
    taxonomy_classes = Column(JSON)
    ground_truth_available = Column(Boolean, nullable=False, default=False)
    annotations = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")
    runs = relationship("EvaluationRun", back_populates="dataset", cascade="all, delete")


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4, index=True)
    dataset_id = Column(Uuid, ForeignKey("evaluation_datasets.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    analysis_id = Column(Uuid, ForeignKey("analysis_sessions.id", ondelete="SET NULL"))
    model_provider = Column(String)
    model_name = Column(String)
    model_version = Column(String)
    checkpoint_identifier = Column(String)
    task = Column(String, nullable=False, default="detection")
    configuration = Column(JSON, nullable=False)
    status = Column(String, nullable=False, default="pending")
    sample_counts = Column(JSON)
    metrics = Column(JSON)
    errors = Column(JSON)
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    dataset = relationship("EvaluationDataset", back_populates="runs")
    user = relationship("User")
    analysis = relationship("AnalysisSession")

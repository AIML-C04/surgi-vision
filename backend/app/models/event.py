from sqlalchemy import Column, String, Float, ForeignKey, DateTime, Uuid, JSON, UniqueConstraint, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base
import uuid


EVENT_TYPES = {
    "INSTRUMENT_DETECTED",
    "INSTRUMENT_ENTERED",
    "INSTRUMENT_REMOVED",
    "INSTRUMENT_ACTIVITY",
    "INSTRUMENT_EXCHANGE",
    "INSTRUMENT_TRANSITION",
    "INSTRUMENT_CO_OCCURRENCE",
    "PHASE_CHANGE",
    "TISSUE_INTERACTION",
    "IMPORTANT_VISUAL_EVENT",
}


class SurgicalEvent(Base):
    __tablename__ = "surgical_events"
    __table_args__ = (
        UniqueConstraint("analysis_id", "dedupe_key", name="uq_surgical_events_analysis_dedupe"),
        Index("ix_surgical_events_video_start", "video_id", "start_time"),
        Index("ix_surgical_events_analysis_start", "analysis_id", "start_time"),
    )

    id = Column(Uuid, primary_key=True, default=uuid.uuid4, index=True)
    video_id = Column(Uuid, ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    analysis_id = Column(Uuid, ForeignKey("analysis_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String, nullable=False, index=True)
    start_time = Column(Float, nullable=False, index=True)
    end_time = Column(Float, nullable=False)
    confidence = Column(Float)
    event_metadata = Column("metadata", JSON)
    evidence = Column(JSON)
    source_detection_ids = Column(JSON)
    source_track_ids = Column(JSON)
    model_version = Column(String)
    dedupe_key = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    video = relationship("Video")
    analysis = relationship("AnalysisSession", back_populates="events")

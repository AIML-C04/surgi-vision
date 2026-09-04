from sqlalchemy import Column, String, Float, ForeignKey, DateTime, Integer, Uuid, JSON, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base
import uuid

class Video(Base):
    __tablename__ = "videos"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(Uuid, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    duration = Column(Float)
    resolution = Column(String)
    file_size = Column(Integer) # in bytes
    status = Column(String, default="uploaded") # uploaded, processing, processed, error
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user = relationship("User", backref="videos")
    analyses = relationship("AnalysisSession", back_populates="video", cascade="all, delete")

class AnalysisSession(Base):
    __tablename__ = "analysis_sessions"
    
    id = Column(Uuid, primary_key=True, default=uuid.uuid4, index=True)
    video_id = Column(Uuid, ForeignKey("videos.id"), nullable=False)
    model_provider = Column(String, nullable=False) # mock, local, huggingface
    analysis_version = Column(String, nullable=False, default="1")
    model_version = Column(String)
    status = Column(String, default="pending") # pending, processing, completed, error
    progress = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))
    processed_at = Column(DateTime(timezone=True))
    processing_duration = Column(Float)
    processed_frames = Column(Integer)
    skipped_frames = Column(Integer)
    error = Column(Text)
    
    # Store the final generated report path or structured data
    report_data = Column(JSON)
    
    video = relationship("Video", back_populates="analyses")
    detections = relationship("Detection", back_populates="analysis", cascade="all, delete")
    tracks = relationship("Track", back_populates="analysis", cascade="all, delete")
    phases = relationship("SurgicalPhase", back_populates="analysis", cascade="all, delete")
    events = relationship("SurgicalEvent", back_populates="analysis", cascade="all, delete")

class Detection(Base):
    __tablename__ = "detections"
    
    id = Column(Uuid, primary_key=True, default=uuid.uuid4, index=True)
    analysis_id = Column(Uuid, ForeignKey("analysis_sessions.id"), nullable=False)
    frame_id = Column(Integer, nullable=False)
    timestamp = Column(Float, nullable=False)
    class_name = Column(String, nullable=False)
    confidence = Column(Float, nullable=False)
    # [x1, y1, x2, y2]
    bbox = Column(JSON, nullable=False)
    track_id = Column(Integer)
    
    analysis = relationship("AnalysisSession", back_populates="detections")

class Track(Base):
    __tablename__ = "tracks"
    
    id = Column(Uuid, primary_key=True, default=uuid.uuid4, index=True)
    analysis_id = Column(Uuid, ForeignKey("analysis_sessions.id"), nullable=False)
    track_id = Column(Integer, nullable=False)
    class_name = Column(String, nullable=False)
    first_seen = Column(Float, nullable=False)
    last_seen = Column(Float, nullable=False)
    
    analysis = relationship("AnalysisSession", back_populates="tracks")

class SurgicalPhase(Base):
    __tablename__ = "surgical_phases"
    
    id = Column(Uuid, primary_key=True, default=uuid.uuid4, index=True)
    analysis_id = Column(Uuid, ForeignKey("analysis_sessions.id"), nullable=False)
    name = Column(String, nullable=False)
    start_time = Column(Float, nullable=False)
    end_time = Column(Float)
    confidence = Column(Float)
    model_provider = Column(String)
    model_version = Column(String)
    taxonomy_version = Column(String)
    evidence = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    analysis = relationship("AnalysisSession", back_populates="phases")

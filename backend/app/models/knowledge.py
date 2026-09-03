from sqlalchemy import Column, String, Float, ForeignKey, DateTime, Integer, Uuid, JSON, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base
import uuid

class VideoKnowledgeChunk(Base):
    __tablename__ = "video_knowledge_chunks"
    
    id = Column(Uuid, primary_key=True, default=uuid.uuid4, index=True)
    video_id = Column(Uuid, ForeignKey("videos.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    source_type = Column(String, nullable=False) # e.g. "detection", "transcript", "metadata"
    start_time = Column(Float)
    end_time = Column(Float)
    content = Column(Text, nullable=False)
    embedding_model = Column(String) # e.g. "all-MiniLM-L6-v2"
    # We will use a JSON array for embeddings in SQLite to allow fallback, or Vector if pgvector
    embedding = Column(JSON) 
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    video = relationship("Video")
    user = relationship("User")

class Conversation(Base):
    __tablename__ = "conversations"
    
    id = Column(Uuid, primary_key=True, default=uuid.uuid4, index=True)
    video_id = Column(Uuid, ForeignKey("videos.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    messages = relationship("Message", back_populates="conversation", cascade="all, delete")

class Message(Base):
    __tablename__ = "messages"
    
    id = Column(Uuid, primary_key=True, default=uuid.uuid4, index=True)
    conversation_id = Column(Uuid, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    role = Column(String, nullable=False) # "user" or "assistant"
    content = Column(Text, nullable=False)
    evidence = Column(JSON) # e.g. [{"timestamp": 10.5, "text": "...", "type": "detection"}]
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    conversation = relationship("Conversation", back_populates="messages")

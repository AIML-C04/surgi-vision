from sqlalchemy import Column, String, Float, ForeignKey, DateTime, Integer, Uuid, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base
import uuid

class LiveSession(Base):
    __tablename__ = "live_sessions"
    
    id = Column(Uuid, primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    pairing_code = Column(String, unique=True, index=True, nullable=False)
    status = Column(String, default="pending") # pending, active, completed, failed
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user = relationship("User")

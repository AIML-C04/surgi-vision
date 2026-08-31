from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from app.schemas.user import UserResponse

class VideoBase(BaseModel):
    title: str

class VideoCreate(VideoBase):
    pass

class VideoResponse(VideoBase):
    id: UUID
    user_id: UUID
    filename: str
    duration: Optional[float]
    resolution: Optional[str]
    file_size: Optional[int]
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

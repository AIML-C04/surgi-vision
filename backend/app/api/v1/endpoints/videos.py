import os
import shutil
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Any
from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.video import Video
from app.schemas.video import VideoResponse

router = APIRouter()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload", response_model=VideoResponse)
async def upload_video(
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    # Validate file type
    if not file.filename.endswith(('.mp4', '.mov', '.avi')):
        raise HTTPException(status_code=400, detail="Invalid file type. Only .mp4, .mov, .avi are supported.")
    
    unique_filename = f"{uuid4()}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    file_size = os.path.getsize(file_path)
    
    # Store video in DB
    video = Video(
        user_id=current_user.id,
        title=title,
        filename=unique_filename,
        file_path=file_path,
        file_size=file_size,
        status="uploaded"
    )
    db.add(video)
    db.commit()
    db.refresh(video)
    
    return video

@router.get("/", response_model=List[VideoResponse])
def get_videos(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    return db.query(Video).filter(Video.user_id == current_user.id).order_by(Video.created_at.desc()).all()

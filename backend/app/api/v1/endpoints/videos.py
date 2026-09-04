import os
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Any
from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.video import Video
from app.schemas.video import VideoResponse
from app.services.storage.provider import get_storage_provider

router = APIRouter()
storage = get_storage_provider()

@router.post("/upload", response_model=VideoResponse)
async def upload_video(
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    # Validate file type
    allowed_extensions = ('.mp4', '.mov', '.avi', '.webm')
    if not any(file.filename.lower().endswith(ext) for ext in allowed_extensions):
        raise HTTPException(status_code=400, detail="Invalid file type.")
    
    file_id = uuid4()
    # Upload file
    try:
        file_path = storage.upload_file(
            user_id=str(current_user.id),
            file_id=str(file_id),
            file_name=file.filename,
            file=file.file
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
        
    file.file.seek(0, 2)
    file_size = file.file.tell()
    
    # Store video in DB
    video = Video(
        id=file_id,
        user_id=current_user.id,
        title=title,
        filename=file.filename,
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
    videos = db.query(Video).filter(Video.user_id == current_user.id).order_by(Video.created_at.desc()).all()
    # we don't modify DB model URL here, the frontend can construct it or we can add a property.
    return videos

@router.get("/{video_id}/url")
def get_video_url(
    video_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    from uuid import UUID
    try:
        vid_uuid = UUID(video_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid video ID format")
        
    video = db.query(Video).filter(Video.id == vid_uuid, Video.user_id == current_user.id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
        
    url = storage.get_file_url(video.file_path)
    return {"url": url}

@router.delete("/{video_id}")
def delete_video(
    video_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    from uuid import UUID
    try:
        vid_uuid = UUID(video_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid video ID format")
        
    video = db.query(Video).filter(Video.id == vid_uuid, Video.user_id == current_user.id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
        
    # Delete related knowledge chunks manually (if cascade is not fully configured)
    from app.models.knowledge import VideoKnowledgeChunk
    from app.models.video import AnalysisSession, Detection, Track
    
    db.query(VideoKnowledgeChunk).filter(VideoKnowledgeChunk.video_id == vid_uuid).delete()
    
    # Delete analysis sessions and related tracking/detections
    sessions = db.query(AnalysisSession).filter(AnalysisSession.video_id == vid_uuid).all()
    for session in sessions:
        db.query(Detection).filter(Detection.analysis_id == session.id).delete()
        db.query(Track).filter(Track.analysis_id == session.id).delete()
        db.delete(session)
        
    # Delete from storage
    try:
        storage.delete_file(video.file_path)
    except Exception as e:
        print(f"Failed to delete storage object: {e}")
        
    # Delete video record
    db.delete(video)
    db.commit()
    
    return {"status": "success", "message": "Video deleted"}

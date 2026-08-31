from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from typing import Any
from uuid import UUID
from app.core.database import get_db, SessionLocal
from app.api.deps import get_current_user
from app.models.user import User
from app.models.video import Video, AnalysisSession, Detection
from app.services.ai.processor import process_video_background, manager

router = APIRouter()

@router.post("/", response_model=Any)
async def create_analysis(
    video_id: UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    video = db.query(Video).filter(Video.id == video_id, Video.user_id == current_user.id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
        
    import os
    analysis = AnalysisSession(
        video_id=video.id,
        model_provider=os.getenv("MODEL_PROVIDER", "mock")
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    
    # We pass a new DB session to the background task to avoid concurrency issues with the request session
    bg_db = SessionLocal()
    background_tasks.add_task(process_video_background, str(analysis.id), video.duration or 10.0, bg_db)
    
    return {"analysis_id": analysis.id, "status": "started"}

@router.websocket("/ws/{analysis_id}")
async def websocket_endpoint(websocket: WebSocket, analysis_id: str):
    await manager.connect(websocket, analysis_id)
    try:
        while True:
            # We don't expect much client->server communication for this demo, just keepalive
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, analysis_id)

@router.get("/{analysis_id}")
def get_analysis_status(
    analysis_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    analysis = db.query(AnalysisSession).filter(AnalysisSession.id == analysis_id).first()
    if not analysis or analysis.video.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    return {
        "id": str(analysis.id),
        "status": analysis.status,
        "progress": analysis.progress,
        "video_title": analysis.video.title,
        "model_provider": analysis.model_provider
    }

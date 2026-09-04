from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from typing import Any
from uuid import UUID
from app.core.database import get_db, SessionLocal
from app.api.deps import get_current_user
from app.models.user import User
from app.models.video import Video, AnalysisSession, Detection, Track
from app.models.event import SurgicalEvent
from app.services.ai.processor import process_video_background, recover_knowledge_indexing_background, manager

router = APIRouter()


def _configured_analysis_version() -> str:
    import os
    return os.getenv("ANALYSIS_VERSION", "1")


def _configured_model_version() -> str:
    import os
    return os.getenv("MODEL_VERSION") or os.getenv("MODEL_PATH") or os.getenv("MODEL_PROVIDER", "mock")

@router.post("/", response_model=Any)
async def create_analysis(
    video_id: UUID,
    reanalyze: bool = False,
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    video = db.query(Video).filter(Video.id == video_id, Video.user_id == current_user.id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
        
    existing_analysis = db.query(AnalysisSession).filter(
        AnalysisSession.video_id == video.id
    ).order_by(AnalysisSession.created_at.desc()).first()

    analysis_version = _configured_analysis_version()
    model_version = _configured_model_version()
    
    if existing_analysis and not reanalyze:
        if existing_analysis.status == "processing":
            return {"analysis_id": existing_analysis.id, "status": existing_analysis.status}
        if (
            existing_analysis.status == "completed"
            and existing_analysis.analysis_version == analysis_version
            and (not existing_analysis.model_version or existing_analysis.model_version == model_version)
        ):
            return {"analysis_id": existing_analysis.id, "status": existing_analysis.status}
        if (
            existing_analysis.status == "error"
            and existing_analysis.analysis_version == analysis_version
            and (not existing_analysis.model_version or existing_analysis.model_version == model_version)
            and (existing_analysis.error or "").startswith("Knowledge indexing failed:")
            and db.query(Detection).filter(Detection.analysis_id == existing_analysis.id).count() > 0
            and db.query(Track).filter(Track.analysis_id == existing_analysis.id).count() > 0
            and db.query(SurgicalEvent).filter(SurgicalEvent.analysis_id == existing_analysis.id).count() > 0
        ):
            existing_analysis.status = "processing"
            existing_analysis.error = None
            existing_analysis.progress = min(existing_analysis.progress or 0, 99.9)
            video.status = "processing"
            db.commit()
            bg_db = SessionLocal()
            background_tasks.add_task(recover_knowledge_indexing_background, str(existing_analysis.id), bg_db)
            return {"analysis_id": existing_analysis.id, "status": "recovering"}
            
    if reanalyze:
        # Delete old knowledge chunks to prevent duplicates
        from app.models.knowledge import VideoKnowledgeChunk
        db.query(VideoKnowledgeChunk).filter(VideoKnowledgeChunk.video_id == video.id).delete()
        
    import os
    analysis = AnalysisSession(
        video_id=video.id,
        model_provider=os.getenv("MODEL_PROVIDER", "mock"),
        analysis_version=analysis_version,
        model_version=model_version,
    )
    db.add(analysis)
    video.status = "processing"
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

@router.get("/by-video/{video_id}")
def get_analysis_by_video(
    video_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    video = db.query(Video).filter(Video.id == video_id, Video.user_id == current_user.id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
        
    analysis = db.query(AnalysisSession).filter(AnalysisSession.video_id == video.id).order_by(AnalysisSession.created_at.desc()).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    import os
    return {
        "id": str(analysis.id),
        "status": analysis.status,
        "progress": analysis.progress,
        "analysis_version": analysis.analysis_version,
        "model_version": analysis.model_version,
        "processed_at": analysis.processed_at,
        "error": analysis.error,
        "video_title": analysis.video.title,
        "video_id": str(analysis.video_id),
        "model_provider": analysis.model_provider,
        "llm_provider": os.getenv("LLM_PROVIDER", "huggingface")
    }

@router.get("/{analysis_id}")
def get_analysis_status(
    analysis_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    analysis = db.query(AnalysisSession).filter(AnalysisSession.id == analysis_id).first()
    if not analysis or analysis.video.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    import os
    return {
        "id": str(analysis.id),
        "status": analysis.status,
        "progress": analysis.progress,
        "analysis_version": analysis.analysis_version,
        "model_version": analysis.model_version,
        "processed_at": analysis.processed_at,
        "error": analysis.error,
        "video_title": analysis.video.title,
        "video_id": str(analysis.video_id),
        "model_provider": analysis.model_provider,
        "llm_provider": os.getenv("LLM_PROVIDER", "huggingface")
    }

@router.get("/{analysis_id}/detections")
def get_analysis_detections(
    analysis_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    analysis = db.query(AnalysisSession).filter(AnalysisSession.id == analysis_id).first()
    if not analysis or analysis.video.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Analysis not found")
        
    detections = db.query(Detection).filter(Detection.analysis_id == analysis_id).order_by(Detection.timestamp).all()
    
    grouped = {}
    for d in detections:
        ts = round(d.timestamp, 1)
        if ts not in grouped:
            grouped[ts] = []
        grouped[ts].append({
            "class": d.class_name,
            "confidence": d.confidence,
            "bbox": d.bbox,
            "track_id": d.track_id
        })
        
    return grouped

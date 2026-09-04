import os
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks, Query
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from typing import List, Any, Optional
from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.video import Video, AnalysisSession, SurgicalPhase
from app.models.event import SurgicalEvent
from app.schemas.video import VideoResponse
from app.services.storage.provider import get_storage_provider
from app.services.phase_recognition import get_phase_provider, serialize_phase

router = APIRouter()
storage = get_storage_provider()


def _latest_completed_analysis(db: Session, video_id):
    return (
        db.query(AnalysisSession)
        .filter(AnalysisSession.video_id == video_id, AnalysisSession.status == "completed")
        .order_by(AnalysisSession.created_at.desc())
        .first()
    )


def _latest_event_analysis(db: Session, video_id):
    """Return the current completed analysis, or recoverable persisted events.

    A knowledge-indexing failure happens after event extraction. Those events are
    still valid evidence and must not be hidden behind a misleading 409.
    """
    analysis = (
        db.query(AnalysisSession)
        .filter(AnalysisSession.video_id == video_id)
        .order_by(AnalysisSession.created_at.desc())
        .first()
    )
    if not analysis:
        return None
    if analysis.status == "completed":
        return analysis
    if analysis.status == "error" and db.query(SurgicalEvent).filter(SurgicalEvent.analysis_id == analysis.id).count() > 0:
        return analysis
    return None


def _phase_status(db: Session, video: Video) -> dict[str, Any]:
    try:
        provider = get_phase_provider()
    except RuntimeError as exc:
        return {"available": False, "status": "failed", "provider": None, "model_version": None, "taxonomy_version": None, "reason": str(exc)}
    analysis = _latest_completed_analysis(db, video.id)
    if not provider.available:
        return {"available": False, "status": "unavailable", "provider": None, "model_version": None, "taxonomy_version": None, "reason": "No validated phase recognition model configured for this analysis.", "analysis_id": str(analysis.id) if analysis else None}
    if not analysis:
        return {"available": True, "status": "processing", "provider": provider.provider_name, "model_version": provider.model_version, "taxonomy_version": provider.taxonomy_version, "reason": "Phase recognition is being processed.", "analysis_id": None}
    phases = db.query(SurgicalPhase).filter(SurgicalPhase.analysis_id == analysis.id).count()
    return {"available": True, "status": "completed", "provider": provider.provider_name, "model_version": provider.model_version, "taxonomy_version": provider.taxonomy_version, "reason": None if phases else "No phase segments were produced by the configured model.", "analysis_id": str(analysis.id)}


@router.get("/{video_id}/phase-status")
def get_phase_status(video_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> Any:
    try:
        vid_uuid = UUID(video_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid video ID format")
    video = db.query(Video).filter(Video.id == vid_uuid, Video.user_id == current_user.id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return _phase_status(db, video)


@router.get("/{video_id}/phases")
def get_video_phases(video_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> Any:
    try:
        vid_uuid = UUID(video_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid video ID format")
    video = db.query(Video).filter(Video.id == vid_uuid, Video.user_id == current_user.id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    analysis = _latest_completed_analysis(db, video.id)
    status = _phase_status(db, video)
    phases = db.query(SurgicalPhase).filter(SurgicalPhase.analysis_id == analysis.id).order_by(SurgicalPhase.start_time).all() if analysis else []
    return {**status, "video_id": str(video.id), "analysis_id": str(analysis.id) if analysis else None, "phases": [serialize_phase(phase) for phase in phases]}

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
    if not url:
        raise HTTPException(
            status_code=404, 
            detail="Video file not found in storage. The file may need to be re-uploaded."
        )
    return {"url": url}


@router.post("/{video_id}/events/generate")
def generate_video_events(
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

    analysis = _latest_event_analysis(db, video.id)
    if not analysis:
        raise HTTPException(status_code=409, detail="A completed analysis is required before event generation")

    existing_event_count = db.query(SurgicalEvent).filter(SurgicalEvent.analysis_id == analysis.id).count()
    if existing_event_count:
        return {
            "analysis_id": str(analysis.id),
            "event_count": existing_event_count,
            "status": "available",
            "analysis_status": analysis.status,
        }

    try:
        from app.services.events.extractor import extract_events
        event_count = extract_events(db, str(analysis.id))
    except Exception as exc:
        db.rollback()
        analysis.status = "error"
        analysis.error = f"Event extraction failed: {exc}"
        analysis.processed_at = datetime.now(timezone.utc)
        db.commit()
        raise HTTPException(status_code=500, detail="Event extraction failed")

    return {
        "analysis_id": str(analysis.id),
        "event_count": event_count,
        "status": "completed",
    }


@router.get("/{video_id}/events")
def get_video_events(
    video_id: str,
    event_type: Optional[str] = Query(default=None),
    start_time: Optional[float] = Query(default=None, ge=0),
    end_time: Optional[float] = Query(default=None, ge=0),
    instrument: Optional[str] = Query(default=None),
    min_confidence: Optional[float] = Query(default=None, ge=0, le=1),
    limit: int = Query(default=500, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
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

    analysis = _latest_event_analysis(db, video.id)
    if not analysis:
        return {"analysis_id": None, "event_intelligence_available": False, "events": []}

    query = db.query(SurgicalEvent).filter(SurgicalEvent.analysis_id == analysis.id)
    if event_type:
        query = query.filter(SurgicalEvent.event_type == event_type)
    if start_time is not None:
        query = query.filter(SurgicalEvent.end_time >= start_time)
    if end_time is not None:
        query = query.filter(SurgicalEvent.start_time <= end_time)
    if min_confidence is not None:
        query = query.filter(SurgicalEvent.confidence >= min_confidence)
    total_events = query.count()
    if instrument:
        # Metadata is JSON across supported databases; instrument filtering is
        # applied after the authorized, paginated analysis query below.
        query = query.order_by(SurgicalEvent.start_time)
        candidates = query.all()
        events = [
            event for event in candidates
            if instrument.lower() in str(event.event_metadata or {}).lower()
        ][offset:offset + limit]
    else:
        events = query.order_by(SurgicalEvent.start_time).offset(offset).limit(limit).all()

    return {
        "analysis_id": str(analysis.id),
        "event_intelligence_available": total_events > 0,
        "total_events": total_events,
        "events": [
            {
                "id": str(event.id),
                "video_id": str(event.video_id),
                "analysis_id": str(event.analysis_id),
                "event_type": event.event_type,
                "start_time": event.start_time,
                "end_time": event.end_time,
                "confidence": event.confidence,
                "metadata": event.event_metadata,
                "evidence": event.evidence,
                "source_detection_ids": event.source_detection_ids,
                "source_track_ids": event.source_track_ids,
                "model_version": event.model_version,
                "created_at": event.created_at,
            }
            for event in events
        ],
    }


@router.get("/{video_id}/instruments")
def get_video_instrument_intelligence(
    video_id: str,
    instrument: Optional[str] = Query(default=None),
    rank_by: str = Query(default="detection_count"),
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

    analysis = (
        db.query(AnalysisSession)
        .filter(AnalysisSession.video_id == video.id, AnalysisSession.status == "completed")
        .order_by(AnalysisSession.created_at.desc())
        .first()
    )
    if not analysis:
        return {
            "video_id": str(video.id),
            "analysis_id": None,
            "instrument_intelligence_available": False,
            "instruments": [],
            "co_occurrences": [],
            "transitions": [],
        }

    from app.services.instrument_intelligence import get_instrument_intelligence
    result = get_instrument_intelligence(db, analysis)
    allowed_rankings = {
        "detection_count",
        "visible_duration",
        "activity_segment_count",
        "average_confidence",
        "peak_confidence",
    }
    if rank_by not in allowed_rankings:
        raise HTTPException(status_code=400, detail=f"Unsupported rank_by value: {rank_by}")
    if instrument:
        result["instruments"] = [
            item for item in result["instruments"]
            if item["class_name"].lower() == instrument.lower()
        ]
    result["instruments"] = sorted(
        result["instruments"],
        key=lambda item: item.get(rank_by) or 0,
        reverse=True,
    )
    result["instrument_intelligence_available"] = bool(result["instruments"])
    result["rank_by"] = rank_by
    return result

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
        db.query(SurgicalEvent).filter(SurgicalEvent.analysis_id == session.id).delete()
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

@router.get("/{video_id}/report")
def get_video_report(
    video_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    from uuid import UUID
    from collections import defaultdict
    try:
        vid_uuid = UUID(video_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid video ID format")
        
    video = db.query(Video).filter(Video.id == vid_uuid, Video.user_id == current_user.id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
        
    analysis = (
        db.query(AnalysisSession)
        .filter(AnalysisSession.video_id == video.id, AnalysisSession.status == "completed")
        .order_by(AnalysisSession.created_at.desc())
        .first()
    )
    
    if not analysis:
        # Report unavailable
        return {
            "available": False,
            "message": "No completed analysis available for this video."
        }
        
    # Get Instrument Intelligence
    from app.services.instrument_intelligence import get_instrument_intelligence
    inst_intel = get_instrument_intelligence(db, analysis)
    
    # Get Events
    events = (
        db.query(SurgicalEvent)
        .filter(SurgicalEvent.analysis_id == analysis.id)
        .order_by(SurgicalEvent.start_time)
        .all()
    )
    
    # Aggregate Event Summary
    event_summary = defaultdict(int)
    for e in events:
        event_summary[e.event_type] += 1
        
    # Build Key Moments
    # Priority: ENTERED, REMOVED, CO_OCCURRENCE, ACTIVITY
    key_moments = []
    priority_types = ["INSTRUMENT_ENTERED", "INSTRUMENT_REMOVED", "INSTRUMENT_CO_OCCURRENCE", "INSTRUMENT_ACTIVITY"]
    
    for e in events:
        if e.event_type in priority_types:
            instruments = (e.event_metadata or {}).get("instruments") or []
            if not instruments and (e.event_metadata or {}).get("instrument"):
                instruments = [(e.event_metadata or {}).get("instrument")]
                
            label = e.event_type.replace("INSTRUMENT_", "").replace("_", " ").title()
            if e.event_type == "INSTRUMENT_ENTERED":
                label = f"{instruments[0] if instruments else 'Instrument'} Entered"
            elif e.event_type == "INSTRUMENT_REMOVED":
                label = f"{instruments[0] if instruments else 'Instrument'} Removed"
            elif e.event_type == "INSTRUMENT_CO_OCCURRENCE":
                label = f"{' + '.join(instruments)} Co-occurrence"
            elif e.event_type == "INSTRUMENT_ACTIVITY":
                label = f"{instruments[0] if instruments else 'Instrument'} Activity"
                
            key_moments.append({
                "id": str(e.id),
                "timestamp": e.start_time,
                "event_type": e.event_type,
                "label": label,
                "instruments": instruments,
                "confidence": e.confidence,
                "evidence": e.evidence
            })
            
    # Attempt AI Summary using structured data (Optionally)
    ai_summary = None
    try:
        import json
        from app.services.rag.llm import get_llm_provider
        import os
        
        provider_name = os.getenv("LLM_PROVIDER", "huggingface").lower()
        # Only try if we have a real LLM configured to avoid slow mock or failing real LLM breaking the report
        if provider_name == "huggingface":
            llm = get_llm_provider()
            
            summary_context = f"Total Detections: {inst_intel.get('detection_count', 0)}. "
            summary_context += f"Instruments detected: {', '.join([i['class_name'] for i in inst_intel.get('instruments', [])])}. "
            summary_context += f"Event counts: {json.dumps(dict(event_summary))}. "
            
            prompt = (
                "Write a highly concise, professional executive summary of this surgical video intelligence. "
                "Use formal, analytical language. Do NOT fabricate any clinical conclusions, success/failure, or diagnoses. "
                "State only what the model detected based on the provided numbers."
            )
            
            # Simple direct call since we want a pure summary
            # using the existing generic ask() method
            ai_summary = llm.ask(prompt, summary_context, history="")
    except Exception as exc:
        print(f"AI Summary generation failed for report: {exc}")
        ai_summary = None
        
    return {
        "available": True,
        "procedure_overview": {
            "video_title": video.title,
            "duration": video.duration,
            "analysis_id": str(analysis.id),
            "analysis_version": analysis.analysis_version,
            "model_version": analysis.model_version,
            "processed_at": analysis.processed_at,
            "total_detections": inst_intel.get("detection_count", 0),
            "total_tracks": inst_intel.get("track_count", 0),
            "total_events": len(events),
            "instrument_class_count": inst_intel.get("instrument_count", 0)
        },
        "instrument_intelligence": inst_intel.get("instruments", []),
        "event_summary": dict(event_summary),
        "key_moments": key_moments,
        "phase_recognition": {
            "available": bool(analysis.phases),
            "status": "completed" if analysis.phases else "unavailable",
            "message": None if analysis.phases else "No validated phase recognition model is configured for this analysis.",
            "phases": [serialize_phase(phase) for phase in analysis.phases],
        },
        "ai_summary": ai_summary
    }

import os
import asyncio
import cv2
import time
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.video import Video, AnalysisSession, Detection, Track
from app.services.ai.mock_provider import MockInferenceProvider

# In-memory connection manager for simple WebSocket broadcasting
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, set] = {}

    async def connect(self, websocket, analysis_id: str):
        await websocket.accept()
        if analysis_id not in self.active_connections:
            self.active_connections[analysis_id] = set()
        self.active_connections[analysis_id].add(websocket)

    def disconnect(self, websocket, analysis_id: str):
        if analysis_id in self.active_connections:
            self.active_connections[analysis_id].remove(websocket)
            if not self.active_connections[analysis_id]:
                del self.active_connections[analysis_id]

    async def broadcast(self, message: dict, analysis_id: str):
        if analysis_id in self.active_connections:
            for connection in self.active_connections[analysis_id]:
                try:
                    await connection.send_json(message)
                except Exception:
                    pass

manager = ConnectionManager()

# Singleton provider to load model only once
_provider_instance = None

def get_provider():
    global _provider_instance
    if _provider_instance is None:
        model_provider = os.getenv("MODEL_PROVIDER", "mock")
        if model_provider in ["local", "real"]:
            try:
                from app.services.ai.real_provider import RealInferenceProvider
                _provider_instance = RealInferenceProvider()
            except Exception as e:
                print(f"Error loading RealInferenceProvider: {e}")
                raise RuntimeError(f"MODEL_PROVIDER=real but model failed to load: {e}")
        else:
            _provider_instance = MockInferenceProvider()
    return _provider_instance


async def recover_knowledge_indexing_background(analysis_id: str, db: Session):
    """Finish an analysis that failed only after detections/events were persisted."""
    from uuid import UUID

    try:
        session = db.query(AnalysisSession).filter(AnalysisSession.id == UUID(analysis_id)).first()
        if not session:
            return
        video = db.query(Video).filter(Video.id == session.video_id).first()
        if not video:
            return

        await manager.broadcast({"event": "analysis_started", "stage": "knowledge_indexing"}, analysis_id)
        from app.services.rag.indexer import generate_knowledge_from_analysis
        chunk_count = generate_knowledge_from_analysis(
            db,
            str(session.id),
            str(session.video_id),
            str(video.user_id),
        )
        if chunk_count == 0:
            raise RuntimeError("Knowledge indexing produced no chunks from persisted analysis data")

        session.status = "completed"
        session.error = None
        session.progress = 100.0
        session.completed_at = datetime.now(timezone.utc)
        session.processed_at = session.completed_at
        video.status = "processed"
        db.commit()
        await manager.broadcast({"event": "analysis_completed", "knowledge_chunks": chunk_count}, analysis_id)
    except Exception as exc:
        db.rollback()
        session = db.query(AnalysisSession).filter(AnalysisSession.id == UUID(analysis_id)).first()
        if session:
            session.status = "error"
            session.error = f"Knowledge indexing failed: {exc}"
            session.processed_at = datetime.now(timezone.utc)
            video = db.query(Video).filter(Video.id == session.video_id).first()
            if video:
                video.status = "error"
            db.commit()
        await manager.broadcast({"event": "analysis_failed", "error": f"Knowledge indexing failed: {exc}"}, analysis_id)
    finally:
        db.close()


async def process_video_background(analysis_id: str, video_duration: float, db: Session):
    """Processes a video frame by frame using the configured AI provider."""
    from uuid import UUID
    
    try:
        session = db.query(AnalysisSession).filter(AnalysisSession.id == UUID(analysis_id)).first()
    except Exception as e:
        print(f"Failed to query AnalysisSession: {e}")
        return
        
    if not session:
        return
        
    session.status = "processing"
    session.error = None
    db.commit()
    
    try:
        provider = get_provider()
    except Exception as e:
        print(f"Provider load failed: {e}")
        session.status = "error"
        session.error = str(e)
        session.processed_at = datetime.now(timezone.utc)
        db.commit()
        await manager.broadcast({"event": "analysis_failed", "error": f"Model failed to load: {e}"}, analysis_id)
        return
    
    video = db.query(Video).filter(Video.id == session.video_id).first()
    
    import tempfile
    import urllib.request
    
    if os.getenv("STORAGE_PROVIDER", "local") == "local":
        video_path = os.path.join("uploads", video.file_path)
        temp_file_path = None
    else:
        from app.services.storage.provider import get_storage_provider
        storage = get_storage_provider()
        video_url = storage.get_file_url(video.file_path)
        # Download to temporary file
        fd, temp_file_path = tempfile.mkstemp(suffix=".mp4")
        os.close(fd)
        try:
            urllib.request.urlretrieve(video_url, temp_file_path)
        except Exception as e:
            print(f"Failed to download video: {e}")
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
            session.status = "error"
            session.error = "Could not download remote video"
            session.processed_at = datetime.now(timezone.utc)
            db.commit()
            await manager.broadcast({"event": "analysis_failed", "error": "Could not download remote video"}, analysis_id)
            return
        video_path = temp_file_path
        
    await manager.broadcast({"event": "analysis_started"}, analysis_id)
    
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        session.status = "error"
        session.error = "Could not open video file"
        session.processed_at = datetime.now(timezone.utc)
        db.commit()
        await manager.broadcast({"event": "analysis_failed", "error": "Could not open video file"}, analysis_id)
        return

    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    # Configurable frame sampling
    sample_rate = int(os.getenv("PROCESS_EVERY_N_FRAMES", 5)) # process 6 fps approx
    
    frame_id = 0
    processed_frame_count = 0
    start_time = time.time()
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
            
        timestamp = frame_id / fps
        
        # Only process every Nth frame to simulate real-time processing constraints
        if frame_id % sample_rate == 0:
            processed_frame_count += 1
            
            # Note: in real-provider, it takes the 'frame' array directly
            if isinstance(provider, MockInferenceProvider):
                # MockProvider doesn't need the frame image
                prediction = provider.analyze_frame(frame_id, timestamp)
                # simulate processing delay for mock
                await asyncio.sleep(0.05)
            else:
                prediction = provider.analyze_frame(frame_id, timestamp, frame)
                # Yield to event loop to allow WebSocket messages to be sent
                await asyncio.sleep(0.001)
                
            # Store in DB
            for det in prediction['detections']:
                d = Detection(
                    analysis_id=analysis_id,
                    frame_id=frame_id,
                    timestamp=timestamp,
                    class_name=det['class'],
                    confidence=det['confidence'],
                    bbox=det['bbox'],
                    track_id=det.get('track_id')
                )
                db.add(d)
                
            progress = (frame_id / total_frames) * 100 if total_frames > 0 else 0
            session.progress = min(progress, 99.9)
            
            # Commit periodically
            if frame_id % (sample_rate * 10) == 0:
                db.commit()
                
            await manager.broadcast({
                "event": "frame_processed",
                "progress": round(progress, 2),
                "prediction": prediction
            }, analysis_id)
            
        frame_id += 1

    cap.release()
    if temp_file_path and os.path.exists(temp_file_path):
        try:
            os.remove(temp_file_path)
        except OSError as e:
            print(f"Failed to remove temp file: {e}")
    
    end_time = time.time()
    processing_time = end_time - start_time
    session.processing_duration = processing_time
    session.processed_frames = processed_frame_count
    session.skipped_frames = max(0, total_frames - processed_frame_count)
    print(f"Video processing finished in {processing_time:.2f}s")
    
    # Generate Tracks from detections
    tracks_map = {}
    all_detections = db.query(Detection).filter(Detection.analysis_id == session.id).all()
    for d in all_detections:
        if d.track_id is not None:
            if d.track_id not in tracks_map:
                tracks_map[d.track_id] = {"class_name": d.class_name, "first": d.timestamp, "last": d.timestamp}
            else:
                tracks_map[d.track_id]["first"] = min(tracks_map[d.track_id]["first"], d.timestamp)
                tracks_map[d.track_id]["last"] = max(tracks_map[d.track_id]["last"], d.timestamp)
                
    for tid, info in tracks_map.items():
        t = Track(
            analysis_id=session.id,
            track_id=tid,
            class_name=info["class_name"],
            first_seen=info["first"],
            last_seen=info["last"]
        )
        db.add(t)
    
    db.commit()

    # Derive temporal intelligence from persisted detections and tracks before indexing knowledge.
    try:
        from app.services.events.extractor import extract_events
        event_count = extract_events(db, str(session.id))
        print(f"Event extraction completed: analysis_id={session.id} events={event_count}")
    except Exception as e:
        print(f"Error generating events: {e}")
        session.status = "error"
        session.error = f"Event extraction failed: {e}"
        session.processed_at = datetime.now(timezone.utc)
        video.status = "error"
        db.commit()
        await manager.broadcast({"event": "analysis_failed", "error": session.error}, analysis_id)
        return

    try:
        from app.services.phase_recognition import recognize_and_persist_phases
        phase_result = recognize_and_persist_phases(db, session)
        print(f"Phase recognition status: analysis_id={session.id} status={phase_result['status']}")
    except Exception as e:
        print(f"Phase recognition unavailable: {e}")

    # Generate knowledge chunks
    try:
        from app.services.rag.indexer import generate_knowledge_from_analysis
        generate_knowledge_from_analysis(db, str(session.id), str(session.video_id), str(video.user_id))
    except Exception as e:
        print(f"Error generating knowledge: {e}")
        session.status = "error"
        session.error = f"Knowledge indexing failed: {e}"
        session.processed_at = datetime.now(timezone.utc)
        video.status = "error"
        db.commit()
        await manager.broadcast({"event": "analysis_failed", "error": session.error}, analysis_id)
        return

    session.status = "completed"
    session.progress = 100.0
    session.completed_at = datetime.now(timezone.utc)
    session.processed_at = session.completed_at
    video.status = "processed"
    db.commit()
    
    await manager.broadcast({"event": "analysis_completed"}, analysis_id)

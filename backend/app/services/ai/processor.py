import os
import asyncio
import cv2
import time
from sqlalchemy.orm import Session
from app.models.video import Video, AnalysisSession, Detection, Track, SurgicalPhase
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
    db.commit()
    
    provider = get_provider()
    
    video = db.query(Video).filter(Video.id == session.video_id).first()
    video_path = video.file_path
    
    await manager.broadcast({"event": "analysis_started"}, analysis_id)
    
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        session.status = "failed"
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
    start_time = time.time()
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
            
        timestamp = frame_id / fps
        
        # Only process every Nth frame to simulate real-time processing constraints
        if frame_id % sample_rate == 0:
            
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
    
    end_time = time.time()
    processing_time = end_time - start_time
    print(f"Video processing finished in {processing_time:.2f}s")
    
    session.status = "completed"
    session.progress = 100.0
    db.commit()
    
    # Generate knowledge chunks
    try:
        from app.services.rag.indexer import generate_knowledge_from_analysis
        generate_knowledge_from_analysis(db, str(session.id), str(session.video_id), str(video.user_id))
    except Exception as e:
        print(f"Error generating knowledge: {e}")
    
    await manager.broadcast({"event": "analysis_completed"}, analysis_id)

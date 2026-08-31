import os
import asyncio
from backend.app.core.database import SessionLocal
from backend.app.models.video import Video, AnalysisSession
from backend.app.services.ai.processor import process_video_background
from uuid import UUID

async def test_process():
    os.environ["MODEL_PROVIDER"] = "real"
    os.environ["PROCESS_EVERY_N_FRAMES"] = "5"
    os.environ["MODEL_PATH"] = "models/yolov8s_cholec80.pt"
    
    db = SessionLocal()
    video = db.query(Video).order_by(Video.id.desc()).first()
    if not video:
        print("No video found")
        return
        
    print(f"Testing with video {video.id} at {video.file_path}")
    
    analysis = AnalysisSession(
        video_id=video.id,
        model_provider="real"
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    
    print(f"Created analysis {analysis.id}")
    
    # Run the background task directly
    await process_video_background(str(analysis.id), video.duration or 10.0, db)
    
    # Check if detections were stored
    from backend.app.models.video import Detection
    count = db.query(Detection).filter(Detection.analysis_id == analysis.id).count()
    print(f"Total detections saved to DB: {count}")

if __name__ == "__main__":
    asyncio.run(test_process())

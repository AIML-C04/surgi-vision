from sqlalchemy.orm import Session
from app.models.video import Detection, AnalysisSession, Video
from app.models.knowledge import VideoKnowledgeChunk
import json

def generate_knowledge_from_analysis(db: Session, analysis_id: str, video_id: str, user_id: str):
    # Group detections by 10-second intervals
    detections = db.query(Detection).filter(Detection.analysis_id == analysis_id).order_by(Detection.timestamp).all()
    
    if not detections:
        return
        
    intervals = {}
    for d in detections:
        interval_idx = int(d.timestamp // 10)
        if interval_idx not in intervals:
            intervals[interval_idx] = set()
        intervals[interval_idx].add(d.class_name)
        
    for interval_idx, classes in intervals.items():
        start_time = interval_idx * 10.0
        end_time = start_time + 10.0
        
        content = f"At {start_time}s to {end_time}s, the following objects were detected: {', '.join(list(classes))}."
        
        chunk = VideoKnowledgeChunk(
            video_id=video_id,
            user_id=user_id,
            source_type="detection",
            start_time=start_time,
            end_time=end_time,
            content=content,
            embedding_model="none", # We will implement real embeddings later or mock
            embedding=None
        )
        db.add(chunk)
        
    db.commit()

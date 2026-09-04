from uuid import UUID

from sqlalchemy.orm import Session

from app.models.video import Detection, AnalysisSession
from app.models.event import SurgicalEvent
from app.models.knowledge import VideoKnowledgeChunk

def generate_knowledge_from_analysis(db: Session, analysis_id: str, video_id: str, user_id: str) -> int:
    """Index one persisted analysis without crossing video, user, or version scope."""
    analysis_uuid = UUID(str(analysis_id))
    video_uuid = UUID(str(video_id))
    user_uuid = UUID(str(user_id))
    analysis = db.query(AnalysisSession).filter(AnalysisSession.id == analysis_uuid).first()
    if not analysis:
        raise ValueError(f"Analysis session not found: {analysis_id}")
    if analysis.video_id != video_uuid or analysis.video.user_id != user_uuid:
        raise ValueError("Knowledge indexing scope does not match the analysis owner or video")

    # Group detections by 10-second intervals
    detections = db.query(Detection).filter(Detection.analysis_id == analysis_uuid).order_by(Detection.timestamp).all()
    intervals = {}
    for d in detections:
        interval_idx = int(d.timestamp // 10)
        if interval_idx not in intervals:
            intervals[interval_idx] = set()
        intervals[interval_idx].add(d.class_name)
        
    from app.services.rag.embeddings import generate_embeddings
    
    contents = []
    chunks = []
    
    for interval_idx, classes in intervals.items():
        start_time = interval_idx * 10.0
        end_time = start_time + 10.0
        
        content = f"At {start_time}s to {end_time}s, the following objects were detected: {', '.join(list(classes))}."
        contents.append(content)
        
        chunk = VideoKnowledgeChunk(
            video_id=video_uuid,
            analysis_id=analysis_uuid,
            user_id=user_uuid,
            source_type="detection",
            start_time=start_time,
            end_time=end_time,
            content=content,
            chunk_metadata={
                "analysis_id": str(analysis_uuid),
                "source": "persisted_detection",
                "start_time": start_time,
                "end_time": end_time,
            },
            embedding_model="all-MiniLM-L6-v2",
        )
        chunks.append(chunk)
        
    events = db.query(SurgicalEvent).filter(SurgicalEvent.analysis_id == analysis_uuid).order_by(SurgicalEvent.start_time).all()
    for event in events:
        # ``metadata`` is SQLAlchemy's class-level MetaData; event JSON is mapped
        # explicitly as event_metadata to prevent that naming collision.
        event_metadata = event.event_metadata or {}
        instrument = event_metadata.get("instrument")
        instruments = event_metadata.get("instruments")
        subject = instrument or ", ".join(instruments or []) or event.event_type
        content = (
            f"{event.event_type} involving {subject} occurred from "
            f"{event.start_time}s to {event.end_time}s."
        )
        contents.append(content)
        chunks.append(VideoKnowledgeChunk(
            video_id=video_uuid,
            analysis_id=analysis_uuid,
            user_id=user_uuid,
            source_type="event",
            start_time=event.start_time,
            end_time=event.end_time,
            content=content,
            chunk_metadata={
                "analysis_id": str(analysis_uuid),
                "source": "persisted_event",
                "event_id": str(event.id),
                "event_type": event.event_type,
            },
            embedding_model="all-MiniLM-L6-v2",
        ))

    if not chunks:
        return 0

    embeddings = generate_embeddings(contents)
    if len(embeddings) != len(chunks):
        raise RuntimeError("Embedding generation returned an incomplete knowledge index")
    for chunk, embedding in zip(chunks, embeddings):
        chunk.embedding = embedding

    # A retry replaces only this analysis version's knowledge; it never touches
    # chunks belonging to a previous completed analysis.
    db.query(VideoKnowledgeChunk).filter(VideoKnowledgeChunk.analysis_id == analysis_uuid).delete(synchronize_session=False)
    db.add_all(chunks)
    db.commit()
    return len(chunks)

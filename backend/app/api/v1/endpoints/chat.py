from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID
from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.video import Video
from app.models.knowledge import Conversation, Message, VideoKnowledgeChunk
from app.services.rag.llm import get_llm_provider

router = APIRouter()
llm = get_llm_provider()

class ChatRequest(BaseModel):
    query: str
    video_id: UUID
    conversation_id: Optional[UUID] = None

class Evidence(BaseModel):
    timestamp: float
    text: str

class ChatResponse(BaseModel):
    conversation_id: UUID
    answer: str
    evidence: List[Evidence]

@router.post("/", response_model=ChatResponse)
def ask_question(
    req: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Verify ownership of video
    video = db.query(Video).filter(Video.id == req.video_id, Video.user_id == current_user.id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
        
    # Retrieve knowledge for this specific video and user
    chunks = db.query(VideoKnowledgeChunk).filter(
        VideoKnowledgeChunk.video_id == req.video_id,
        VideoKnowledgeChunk.user_id == current_user.id
    ).all()
    
    # Simple keyword search fallback for RAG
    # In production with pgvector, we would do a semantic search here
    from app.core.config import settings
    
    if "postgresql" in settings.DATABASE_URL:
        from app.services.rag.embeddings import generate_embeddings
        query_embedding = generate_embeddings([req.query])
        if query_embedding:
            # pgvector L2 distance
            chunks = db.query(VideoKnowledgeChunk).filter(
                VideoKnowledgeChunk.video_id == req.video_id,
                VideoKnowledgeChunk.user_id == current_user.id
            ).order_by(VideoKnowledgeChunk.embedding.l2_distance(query_embedding[0])).limit(5).all()
        else:
            chunks = db.query(VideoKnowledgeChunk).filter(
                VideoKnowledgeChunk.video_id == req.video_id,
                VideoKnowledgeChunk.user_id == current_user.id
            ).limit(5).all()
    else:
        chunks = db.query(VideoKnowledgeChunk).filter(
            VideoKnowledgeChunk.video_id == req.video_id,
            VideoKnowledgeChunk.user_id == current_user.id
        ).all()
        
    relevant_chunks = chunks[:5] 
    
    context_text = "\n".join([f"[{c.start_time}s]: {c.content}" for c in relevant_chunks])
    
    # Ask LLM
    answer = llm.ask(req.query, context_text)
    
    # Create conversation if not exists
    if not req.conversation_id:
        conversation = Conversation(video_id=video.id, user_id=current_user.id, title=req.query[:50])
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        req.conversation_id = conversation.id
    else:
        conversation = db.query(Conversation).filter(
            Conversation.id == req.conversation_id, 
            Conversation.user_id == current_user.id
        ).first()
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
            
    # Format evidence
    evidence = []
    if "NOT AVAILABLE" not in answer:
        for c in relevant_chunks[:3]:
            evidence.append(Evidence(timestamp=c.start_time, text=c.content))
            
    # Save messages
    user_msg = Message(
        conversation_id=conversation.id,
        role="user",
        content=req.query
    )
    asst_msg = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=answer,
        evidence=[e.dict() for e in evidence]
    )
    
    db.add(user_msg)
    db.add(asst_msg)
    db.commit()
    
    return ChatResponse(
        conversation_id=conversation.id,
        answer=answer,
        evidence=evidence
    )

@router.get("/{conversation_id}")
def get_conversation(
    conversation_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id
    ).first()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
        
    return {
        "id": conversation.id,
        "title": conversation.title,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "evidence": m.evidence
            } for m in conversation.messages
        ]
    }

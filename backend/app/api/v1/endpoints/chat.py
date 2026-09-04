from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Any, List, Optional
from uuid import UUID
from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.video import Video
from app.models.knowledge import Conversation, Message, VideoKnowledgeChunk
from app.services.rag.llm import LLMConfigurationError, LLMProviderError, get_llm_provider

router = APIRouter()

class ChatRequest(BaseModel):
    query: str
    video_id: UUID
    conversation_id: Optional[UUID] = None
    selected_context: Optional[dict[str, Any]] = None

class Evidence(BaseModel):
    evidence_id: Optional[str] = None
    timestamp: Optional[float] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    text: Optional[str] = None
    type: Optional[str] = None
    event_id: Optional[str] = None
    event_type: Optional[str] = None
    instrument: Optional[str] = None
    instruments: List[str] = Field(default_factory=list)
    confidence: Optional[float] = None
    track_ids: List[Any] = Field(default_factory=list)
    frame_ids: List[int] = Field(default_factory=list)
    detection_ids: List[str] = Field(default_factory=list)
    model_version: Optional[str] = None
    source: Optional[str] = None

class ChatResponse(BaseModel):
    conversation_id: UUID
    answer: str
    evidence: List[Evidence]
    support: str = "insufficient_evidence"

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
        
    from app.services.copilot_evidence import retrieve_copilot_evidence

    try:
        structured = retrieve_copilot_evidence(db, req.video_id, current_user.id, req.query, selected_context=req.selected_context)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    unavailable_reason = structured.get("evaluation_reason") if structured.get("evaluation_unavailable") else None
    phase_unavailable = structured.get("phase_unavailable", False)

    # Knowledge must come from the same analysis version as structured evidence.
    # This prevents a reanalysis from mixing older vector chunks into Copilot.
    chunk_scope = [
        VideoKnowledgeChunk.video_id == req.video_id,
        VideoKnowledgeChunk.user_id == current_user.id,
    ]
    if structured["analysis"]:
        chunk_scope.append(VideoKnowledgeChunk.analysis_id == UUID(structured["analysis"]["id"]))
    
    # Simple keyword search fallback for RAG
    # In production with pgvector, we would do a semantic search here
    from app.core.config import settings
    
    if "postgresql" in settings.DATABASE_URL:
        from app.services.rag.embeddings import generate_embeddings
        try:
            query_embedding = generate_embeddings([req.query])
            if query_embedding:
                # pgvector L2 distance
                chunks = db.query(VideoKnowledgeChunk).filter(*chunk_scope).order_by(VideoKnowledgeChunk.embedding.l2_distance(query_embedding[0])).limit(5).all()
            else:
                chunks = db.query(VideoKnowledgeChunk).filter(*chunk_scope).limit(5).all()
        except Exception as e:
            print(f"Embedding error: {e}")
            chunks = db.query(VideoKnowledgeChunk).filter(*chunk_scope).limit(5).all()
    else:
        chunks = db.query(VideoKnowledgeChunk).filter(*chunk_scope).all()
        
    relevant_chunks = chunks[:5] 
    
    # Create conversation if not exists
    if not req.conversation_id:
        conversation = Conversation(
            video_id=video.id,
            analysis_id=UUID(structured["analysis"]["id"]) if structured["analysis"] else None,
            user_id=current_user.id,
            title=req.query[:50],
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        req.conversation_id = conversation.id
    else:
        conversation = db.query(Conversation).filter(
            Conversation.id == req.conversation_id, 
            Conversation.user_id == current_user.id,
            Conversation.video_id == req.video_id
        ).first()
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        if structured["analysis"]:
            requested_analysis_id = UUID(structured["analysis"]["id"])
            if conversation.analysis_id and conversation.analysis_id != requested_analysis_id:
                raise HTTPException(status_code=409, detail="Conversation belongs to an older analysis version")
            if conversation.analysis_id is None:
                conversation.analysis_id = requested_analysis_id
                db.commit()
            
    # Save user message first so it persists even if LLM fails
    user_msg = Message(
        conversation_id=conversation.id,
        role="user",
        content=req.query
    )
    db.add(user_msg)
    db.commit()
    db.refresh(conversation) # Get updated messages
    
    # Format history (last 6 messages max to prevent token overflow)
    history_lines = []
    # conversation.messages is ordered by creation, exclude the newly added user_msg at the end if we just want prior history
    # Actually, let's include prior messages
    for m in conversation.messages[:-1][-6:]:
        role_label = "User" if m.role == "user" else "Assistant"
        history_lines.append(f"{role_label}: {m.content}")
    history_text = "\n".join(history_lines) if history_lines else "No previous history."
    
    rag_context = "\n".join([f"[{c.start_time}s]: {c.content}" for c in relevant_chunks])
    if not structured["evidence"] and not rag_context:
        context_text = "No relevant context extracted from this video."
    else:
        context_text = "STRUCTURED VIDEO EVIDENCE:\n" + structured["context"]
        context_text += "\nINDEXED VIDEO KNOWLEDGE:\n" + (rag_context or "No relevant indexed knowledge extracted from this video.")

    # Ask LLM
    try:
        import os
        if phase_unavailable:
            answer = "Phase recognition is not available for this analysis."
        elif unavailable_reason:
            answer = unavailable_reason
        else:
            llm = get_llm_provider()
            print(f"LLM provider: {os.getenv('LLM_PROVIDER', 'huggingface')}")
            print(f"LLM model: {os.getenv('LLM_MODEL', 'openai/gpt-oss-20b')}")
            print(f"Retrieved context chunks: {len(relevant_chunks)}")
            print("Generating response...")
            answer = llm.ask(req.query, context_text, history_text)
    except LLMConfigurationError:
        print("LLM configuration failure: Hugging Face token is not configured")
        raise HTTPException(status_code=503, detail="Copilot is not configured.")
    except LLMProviderError as e:
        print(f"LLM provider failure: {e}")
        raise HTTPException(status_code=503, detail="Copilot model/provider is temporarily unavailable.")
    except ValueError as e:
        print(f"LLM configuration failure: {str(e)}")
        raise HTTPException(status_code=503, detail="Copilot is not configured.")
    except Exception as e:
        print(f"LLM Generation Failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Copilot provider error: configured provider unavailable.")
    
    # Format evidence
    from app.services.copilot_response import parse_generated_response
    trusted_by_id = {item["evidence_id"]: item for item in structured["evidence"]}
    parsed_answer, parsed_support, cited_ids, malformed = parse_generated_response(answer, set(trusted_by_id))
    evidence = []
    if not malformed and "not available" not in parsed_answer.lower() and "insufficient" not in parsed_answer.lower():
        if parsed_support is None:
            evidence.extend(Evidence(**item) for item in structured["evidence"])
            evidence.extend(Evidence(timestamp=c.start_time, end_time=c.end_time, text=c.content, type="knowledge", source="indexed_video_knowledge") for c in relevant_chunks[:3])
        else:
            evidence.extend(Evidence(**trusted_by_id[evidence_id]) for evidence_id in cited_ids)

    support = parsed_support or ("supported" if evidence else "insufficient_evidence")
    if not evidence and support == "supported":
        support = "insufficient_evidence"
    if malformed:
        support = "insufficient_evidence"
            
    # Save assistant message
    asst_msg = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=parsed_answer,
        evidence=[e.model_dump() for e in evidence]
    )
    
    db.add(asst_msg)
    db.commit()
    
    return ChatResponse(
        conversation_id=conversation.id,
        answer=parsed_answer,
        evidence=evidence,
        support=support
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

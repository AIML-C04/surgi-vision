from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Any
from datetime import datetime, timedelta
import secrets
import string
import uuid
import json
from jose import JWTError, jwt
from app.core.config import settings
from app.services.live_intelligence import LiveInferenceSession
from app.core.database import get_db, SessionLocal
from app.api.deps import get_current_user
from app.models.user import User
from app.models.live import LiveSession

router = APIRouter()

class LiveSessionCreateResponse(BaseModel):
    session_id: uuid.UUID
    pairing_code: str
    expires_at: datetime

@router.post("/create", response_model=LiveSessionCreateResponse)
def create_live_session(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Generate 6 digit code
    code = ''.join(secrets.choice(string.digits) for i in range(6))
    expires = datetime.utcnow() + timedelta(minutes=10)
    
    session = LiveSession(
        user_id=current_user.id,
        pairing_code=code,
        expires_at=expires
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    
    return {
        "session_id": session.id,
        "pairing_code": session.pairing_code,
        "expires_at": session.expires_at
    }

class LiveConnectionManager:
    def __init__(self):
        # session_id -> {"host": websocket, "client": websocket}
        self.active_sessions = {}
        self.inference_sessions: dict[str, LiveInferenceSession] = {}

    async def connect(self, websocket: WebSocket, session_id: str, role: str):
        await websocket.accept()
        if session_id not in self.active_sessions:
            self.active_sessions[session_id] = {}
        self.active_sessions[session_id][role] = websocket

    def disconnect(self, websocket: WebSocket, session_id: str, role: str):
        if session_id in self.active_sessions:
            if role in self.active_sessions[session_id]:
                del self.active_sessions[session_id][role]
            if not self.active_sessions[session_id]:
                del self.active_sessions[session_id]

    async def forward_message(self, message: str, session_id: str, from_role: str):
        if session_id in self.active_sessions:
            target_role = "host" if from_role == "client" else "client"
            target_ws = self.active_sessions[session_id].get(target_role)
            if target_ws:
                await target_ws.send_text(message)

live_manager = LiveConnectionManager()


def _authenticated_session(websocket: WebSocket, session_id: str):
    token = websocket.query_params.get("token")
    if not token:
        return None
    try:
        claims = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = uuid.UUID(str(claims.get("sub")))
        session_uuid = uuid.UUID(session_id)
    except (JWTError, ValueError, TypeError):
        return None
    db = SessionLocal()
    session = db.query(LiveSession).filter(LiveSession.id == session_uuid, LiveSession.user_id == user_id).first()
    db.close()
    return session


async def _send_live_update(websocket: WebSocket, payload: dict[str, Any]):
    try:
        await websocket.send_json(payload)
    except Exception:
        pass

@router.websocket("/ws/{session_id}/{role}")
async def live_websocket_endpoint(websocket: WebSocket, session_id: str, role: str):
    if role not in {"host", "client"}:
        await websocket.close(code=1008)
        return
    session = _authenticated_session(websocket, session_id)
    
    if not session or session.expires_at < datetime.utcnow() or session.status == "failed":
        await websocket.close(code=1008)
        return
        
    await live_manager.connect(websocket, session_id, role)
    db = SessionLocal()
    session.status = "active"
    db.merge(session)
    db.commit()
    db.close()
    if role == "host" and settings.LIVE_INFERENCE_ENABLED and session_id not in live_manager.inference_sessions:
        engine = LiveInferenceSession(session_id, lambda payload: _send_live_update(websocket, payload), settings.LIVE_MAX_QUEUE_SIZE)
        live_manager.inference_sessions[session_id] = engine
        await engine.start()
    
    try:
        while True:
            # We use receive() to handle both text and bytes
            message = await websocket.receive()
            if "text" in message:
                await live_manager.forward_message(message["text"], session_id, role)
            elif "bytes" in message and role == "host":
                import cv2
                import numpy as np
                nparr = np.frombuffer(message["bytes"], np.uint8)
                frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                engine = live_manager.inference_sessions.get(session_id)
                if frame is not None and engine:
                    await engine.submit(frame)
    except WebSocketDisconnect:
        live_manager.disconnect(websocket, session_id, role)
    finally:
        if role == "host":
            engine = live_manager.inference_sessions.pop(session_id, None)
            if engine:
                await engine.stop()
        if not live_manager.active_sessions.get(session_id):
            db = SessionLocal()
            stored = db.query(LiveSession).filter(LiveSession.id == uuid.UUID(session_id)).first()
            if stored:
                stored.status = "completed"
                db.commit()
            db.close()
        
@router.post("/verify")
def verify_pairing_code(
    code: str,
    db: Session = Depends(get_db)
):
    session = db.query(LiveSession).filter(
        LiveSession.pairing_code == code,
        LiveSession.expires_at > datetime.utcnow()
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Invalid or expired pairing code")
        
    return {"session_id": str(session.id)}

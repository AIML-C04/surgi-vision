from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Any
from datetime import datetime, timedelta
import secrets
import string
import uuid
import json
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

@router.websocket("/ws/{session_id}/{role}")
async def live_websocket_endpoint(websocket: WebSocket, session_id: str, role: str):
    # Basic auth should be done here in production via token in URL or initial message
    # For this demo, we assume the pairing code was exchanged and verified before connecting
    
    db = SessionLocal()
    session = db.query(LiveSession).filter(LiveSession.id == uuid.UUID(session_id)).first()
    db.close()
    
    if not session or session.expires_at < datetime.utcnow() or session.status == "failed":
        await websocket.close(code=1008)
        return
        
    await live_manager.connect(websocket, session_id, role)
    
    try:
        while True:
            data = await websocket.receive_text()
            # Forward signaling data (SDP, ICE candidates) to the other peer
            await live_manager.forward_message(data, session_id, role)
    except WebSocketDisconnect:
        live_manager.disconnect(websocket, session_id, role)
        
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

from fastapi import APIRouter
from app.api.v1.endpoints import auth, videos, analysis, chat, live

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(videos.router, prefix="/videos", tags=["videos"])
api_router.include_router(analysis.router, prefix="/analysis", tags=["analysis"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(live.router, prefix="/live", tags=["live"])

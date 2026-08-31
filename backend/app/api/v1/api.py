from fastapi import APIRouter
from app.api.v1.endpoints import auth, videos, analysis

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(videos.router, prefix="/videos", tags=["videos"])
api_router.include_router(analysis.router, prefix="/analysis", tags=["analysis"])
# api_router.include_router(users.router, prefix="/users", tags=["users"])
# api_router.include_router(videos.router, prefix="/videos", tags=["videos"])
# api_router.include_router(analysis.router, prefix="/analysis", tags=["analysis"])

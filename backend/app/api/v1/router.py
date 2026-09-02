from fastapi import APIRouter

from app.api.v1.endpoints import auth, sessions, rag


# This is the master router for the v1 API
api_v1_router = APIRouter()

# Include the individual feature routers with their URL prefixes and tags
api_v1_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_v1_router.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
api_v1_router.include_router(rag.router, prefix="/rag", tags=["rag"])
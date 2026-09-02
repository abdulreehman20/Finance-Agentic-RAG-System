from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from app.api.v1.router import api_v1_router
from app.core.config import get_settings
from app.db.db import init_db

settings = get_settings()

sentry_dsn = settings.SENTRY_DSN
sentry_sdk.init(
    dsn=sentry_dsn,
    send_default_pii=True,
    enable_logs=True,
    traces_sample_rate=1.0,
    profile_session_sample_rate=1.0,
    profile_lifecycle="trace",
)


# Use lifespan to handle database startup tasks
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


# Initialize the FastAPI app
app = FastAPI(
    title="Backend",
    description="Backend for the application",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
    version="0.1.0",
)

# Required for OAuth social-login state (Google, GitHub, etc.)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SESSION_SECRET or "dev-session-secret-change-in-env",
    session_cookie=settings.SESSION_COOKIE_NAME,
    max_age=settings.SESSION_MAX_AGE,
    https_only=settings.is_production,
    same_site="lax",
)


# Root route
@app.get("/")
def read_root():
    return {"message": "Hello World"}


# Health check route
@app.get("/health")
def health_check():
    return {"status": "ok"}


# error route
@app.get("/error")
def error():
    raise Exception("Test error")




# Mount the entire v1 API structure
app.include_router(api_v1_router, prefix="/api/v1")

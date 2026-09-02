# Authlib Integration Guide — FastAPI Backend

This guide walks through integrating **Authlib** into a **new** FastAPI project with email/password sign-up, sign-in, logout, a protected `/me` route, and optional session management. Follow it step by step when bootstrapping auth from scratch.

> **Note:** Authlib is an OAuth 2.0 / OpenID Connect and JOSE (JWT) library — not a turnkey auth product like Clerk or Auth0. You build the sign-up and login routes yourself; Authlib handles JWT signing/verification and (optionally) social OAuth flows.

Official references:

- [Authlib FastAPI OAuth Client](https://docs.authlib.org/en/stable/oauth2/client/web/fastapi.html)
- [Authlib JWT (JOSE)](https://docs.authlib.org/en/stable/jose/jwt.html)
- [FastAPI Security — OAuth2 with Password and Bearer](https://fastapi.tiangolo.com/tutorial/security/simple-oauth2/)

---

## Table of contents

1. [What is Authlib & its benefits](#1-what-is-authlib--its-benefits)
2. [Packages to install](#2-packages-to-install)
3. [Configuration](#3-configuration)
4. [Login, sign-up, logout & me routes](#4-login-sign-up-logout--me-routes)
5. [Session management (do you need it separately?)](#5-session-management-do-you-need-it-separately)
6. [Wire everything in `main.py`](#6-wire-everything-in-mainpy)
7. [Final thoughts](#7-final-thoughts)

---

## 1. What is Authlib & its benefits

### What is Authlib?

**Authlib** is a Python library for building and consuming OAuth 1.0, OAuth 2.0, and OpenID Connect systems. It also provides JOSE primitives (JWS, JWE, JWK, JWT) for creating and verifying tokens.

In a typical FastAPI API you use Authlib in two ways:

| Use case | Authlib module | What you get |
|----------|----------------|--------------|
| Email/password API auth | `authlib.jose.jwt` | Sign and verify access tokens (JWT) |
| Social login (Google, GitHub, …) | `authlib.integrations.starlette_client` | OAuth redirect + callback flows |
| Full OAuth2 provider (advanced) | `authlib.oauth2` authorization server | You become an OAuth issuer — rarely needed for a single app |

Authlib does **not** ship ready-made `/signup` or `/login` handlers, password reset, or a user admin UI. You implement those routes and use Authlib for standards-compliant tokens and OAuth.

### Benefits

| Benefit | Description |
|---------|-------------|
| **Standards-compliant** | Implements RFC 6749 (OAuth 2.0), OIDC, JWT (RFC 7519), and related specs |
| **FastAPI / Starlette native** | First-class async integration via `starlette_client` |
| **Flexible** | Use only JWT, only social login, or both |
| **No vendor lock-in** | You own users, passwords, and tokens in your database |
| **Async-friendly** | Works with FastAPI’s async request model |
| **JOSE toolkit** | Encode/decode JWTs, validate claims (`exp`, `iss`, etc.) in one place |

### When Authlib is a good fit

- You want **self-hosted** email/password auth with JWT bearer tokens.
- You need **“Login with Google/GitHub”** alongside your own accounts.
- You want full control over user records and token lifetime.

### When to consider something else

- You want hosted auth, MFA, and user management UI out of the box → Clerk, Auth0, Firebase Auth, etc.
- You only need simple API keys → FastAPI `APIKeyHeader` is enough.

---

## 2. Packages to install

### Core dependencies

```bash
# Using uv (recommended)
uv add "fastapi[standard]" authlib bcrypt pydantic-settings sqlmodel asyncpg "sqlalchemy[asyncio]" email-validator cryptography

# Or using pip
pip install "fastapi[standard]" authlib bcrypt pydantic-settings sqlmodel asyncpg "sqlalchemy[asyncio]" email-validator cryptography
```

### What each package does

| Package | Purpose |
|---------|---------|
| `fastapi[standard]` | Web framework + Starlette (includes `SessionMiddleware`) |
| `authlib` | JWT encode/decode + optional OAuth client |
| `bcrypt` | Password hashing (never store plaintext passwords) |
| `pydantic-settings` | Load `JWT_SECRET`, DB URL, etc. from `.env` |
| `sqlmodel` | User + Session models and async DB access |
| `asyncpg` | Async PostgreSQL driver |
| `email-validator` | Validate email fields in Pydantic schemas |
| `cryptography` | Required by Authlib for some JWT algorithms |

### Optional (social login)

```bash
uv add httpx   # Authlib uses httpx for OAuth token exchange
```

### Suggested project layout

```
my-fastapi-app/
├── app/
│   ├── main.py
│   ├── core/
│   │   ├── config.py
│   │   └── security.py
│   ├── db/
│   │   ├── db.py
│   │   ├── schemas.py
│   │   └── models/
│   │       ├── user.py
│   │       └── session.py      # optional — server-side sessions
│   ├── dependencies/
│   │   └── auth.py
│   └── api/
│       └── v1/
│           └── auth.py
├── .env
└── pyproject.toml
```

---

## 3. Configuration

### Environment variables (`.env`)

```env
# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/myapp

# JWT (Authlib signs access tokens with this)
JWT_SECRET=change-me-to-a-long-random-string-at-least-32-chars
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# Starlette session cookie (required for OAuth social login state)
SESSION_SECRET=another-long-random-string-at-least-32-chars
SESSION_COOKIE_NAME=app_session
SESSION_MAX_AGE=86400

# App
APP_BASE_URL=http://localhost:8000
ENVIRONMENT=development
DEBUG=true

# Optional — Google OAuth
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
```

Generate secrets (example):

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Settings class (`app/core/config.py`)

```python
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str = Field(default="")
    JWT_SECRET: str = Field(default="")
    JWT_ALGORITHM: str = Field(default="HS256")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60)
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7)

    SESSION_SECRET: str = Field(default="")
    SESSION_COOKIE_NAME: str = Field(default="app_session")
    SESSION_MAX_AGE: int = Field(default=86400)

    APP_BASE_URL: str = Field(default="http://localhost:8000")
    ENVIRONMENT: str = Field(default="development")
    DEBUG: bool = Field(default=False)

    GOOGLE_CLIENT_ID: str = Field(default="")
    GOOGLE_CLIENT_SECRET: str = Field(default="")

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

### Database setup (`app/db/db.py`)

```python
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.db.models.user import User  # noqa: F401
from app.db.models.session import UserSession  # noqa: F401 — if using server sessions

settings = get_settings()

engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG)
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
```

### Security helpers (`app/core/security.py`)

```python
from datetime import datetime, timedelta, timezone
import secrets
import uuid

import bcrypt
from authlib.jose import jwt

from app.core.config import get_settings

settings = get_settings()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(*, sub: str, email: str) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": sub,
        "email": email,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    header = {"alg": settings.JWT_ALGORITHM}
    return jwt.encode(header, payload, settings.JWT_SECRET).decode()


def create_refresh_token() -> str:
    """Opaque refresh token stored in DB — not a JWT."""
    return secrets.token_urlsafe(48)


def decode_access_token(token: str) -> dict:
    claims = jwt.decode(token, settings.JWT_SECRET)
    claims.validate()
    if claims.get("type") != "access":
        raise ValueError("Invalid token type")
    return dict(claims)
```

### Pydantic schemas (`app/db/schemas.py`)

```python
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class SignUpRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    first_name: str = Field(min_length=1)
    last_name: str = Field(min_length=1)


class SignInRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class AuthResponse(BaseModel):
    user_id: str
    email: str
    full_name: str
    access_token: str
    refresh_token: str | None = None
    token_type: str = "Bearer"


class UserProfile(BaseModel):
    user_id: str
    email: str
    full_name: str
    role: str
    created_at: datetime


class LogoutRequest(BaseModel):
    refresh_token: str | None = None
```

---

## 4. Login, sign-up, logout & me routes

### User model (`app/db/models/user.py`)

```python
from datetime import datetime, timezone
import uuid

from sqlmodel import Field, SQLModel


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        primary_key=True,
        max_length=36,
    )
    email: str = Field(unique=True, index=True, max_length=320)
    password_hash: str = Field(nullable=False)
    full_name: str | None = Field(default=None, max_length=512)
    role: str = Field(default="user", max_length=64)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)
```

### Auth dependency (`app/dependencies/auth.py`)

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.security import decode_access_token
from app.db.db import get_session
from app.db.models.user import User

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: AsyncSession = Depends(get_session),
) -> User:
    try:
        payload = decode_access_token(credentials.credentials)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await session.exec(select(User).where(User.id == payload["sub"]))
    user = result.first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user
```

### Auth router (`app/api/v1/auth.py`)

```python
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from app.db.db import get_session
from app.db.models.session import UserSession
from app.db.models.user import User
from app.db.schemas import (
    AuthResponse,
    LogoutRequest,
    SignInRequest,
    SignUpRequest,
    UserProfile,
)
from app.dependencies.auth import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def signup(body: SignUpRequest, session: AsyncSession = Depends(get_session)):
    existing = await session.exec(select(User).where(User.email == body.email))
    if existing.first():
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        full_name=f"{body.first_name} {body.last_name}".strip(),
    )
    session.add(user)
    await session.flush()

    access_token = create_access_token(sub=user.id, email=user.email)
    refresh_token = create_refresh_token()

    db_session = UserSession(
        user_id=user.id,
        refresh_token=refresh_token,
        expires_at=datetime.now(timezone.utc)
        + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
    )
    session.add(db_session)
    await session.commit()
    await session.refresh(user)

    return AuthResponse(
        user_id=user.id,
        email=user.email,
        full_name=user.full_name or "",
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/login", response_model=AuthResponse)
async def login(body: SignInRequest, session: AsyncSession = Depends(get_session)):
    result = await session.exec(select(User).where(User.email == body.email))
    user = result.first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")

    access_token = create_access_token(sub=user.id, email=user.email)
    refresh_token = create_refresh_token()

    db_session = UserSession(
        user_id=user.id,
        refresh_token=refresh_token,
        expires_at=datetime.now(timezone.utc)
        + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
    )
    session.add(db_session)
    await session.commit()

    return AuthResponse(
        user_id=user.id,
        email=user.email,
        full_name=user.full_name or "",
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.get("/me", response_model=UserProfile)
async def me(current_user: User = Depends(get_current_user)):
    return UserProfile(
        user_id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name or "",
        role=current_user.role,
        created_at=current_user.created_at,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    body: LogoutRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Revoke refresh token server-side. Client must delete access token locally."""
    if body.refresh_token:
        result = await session.exec(
            select(UserSession).where(
                UserSession.user_id == current_user.id,
                UserSession.refresh_token == body.refresh_token,
                UserSession.revoked_at.is_(None),
            )
        )
        db_session = result.first()
        if db_session:
            db_session.revoked_at = datetime.now(timezone.utc)
            session.add(db_session)
            await session.commit()
    return None


@router.post("/refresh", response_model=AuthResponse)
async def refresh_token(body: LogoutRequest, session: AsyncSession = Depends(get_session)):
    """Exchange a valid refresh token for a new access token."""
    if not body.refresh_token:
        raise HTTPException(status_code=400, detail="refresh_token is required")

    result = await session.exec(
        select(UserSession).where(
            UserSession.refresh_token == body.refresh_token,
            UserSession.revoked_at.is_(None),
        )
    )
    db_session = result.first()
    if not db_session or db_session.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    user_result = await session.exec(select(User).where(User.id == db_session.user_id))
    user = user_result.first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    access_token = create_access_token(sub=user.id, email=user.email)
    return AuthResponse(
        user_id=user.id,
        email=user.email,
        full_name=user.full_name or "",
        access_token=access_token,
        refresh_token=body.refresh_token,
    )
```

### API summary

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/v1/auth/signup` | No | Register user, return JWT + refresh token |
| `POST` | `/api/v1/auth/login` | No | Verify password, return JWT + refresh token |
| `GET` | `/api/v1/auth/me` | Bearer JWT | Return current user profile |
| `POST` | `/api/v1/auth/logout` | Bearer JWT | Revoke refresh token |
| `POST` | `/api/v1/auth/refresh` | No (refresh token in body) | Issue new access token |

### Client usage

```http
# Sign up
POST /api/v1/auth/signup
Content-Type: application/json

{"email": "user@example.com", "password": "securepass123", "first_name": "Jane", "last_name": "Doe"}

# Protected route
GET /api/v1/auth/me
Authorization: Bearer <access_token>
```

---

## 5. Session management (do you need it separately?)

**Yes — for production apps you should add session management beyond a bare JWT.**

### Two different “sessions”

| Concept | What it is | Provided by |
|---------|------------|-------------|
| **OAuth flow state** | Temporary `state` / `code_verifier` during Google login redirect | `SessionMiddleware` + `request.session` |
| **User session** | Tracks logged-in user across requests | Your design: JWT only, or JWT + refresh tokens in DB |

Authlib’s FastAPI docs require `SessionMiddleware` for **OAuth client** redirects. That is **not** the same as storing “user is logged in” in a cookie — it only holds OAuth handshake data.

### Recommended approach for APIs

| Layer | Mechanism |
|-------|-----------|
| Short-lived access | JWT signed with Authlib (`authlib.jose.jwt`), sent as `Authorization: Bearer` |
| Long-lived session | Opaque refresh token stored in PostgreSQL |
| Logout | Mark refresh token `revoked_at` in DB; client deletes access JWT |
| OAuth social login | `SessionMiddleware` for redirect state only |

### Session model (`app/db/models/session.py`)

```python
from datetime import datetime, timezone
import uuid

from sqlmodel import Field, SQLModel


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class UserSession(SQLModel, table=True):
    """Server-side refresh token record — enables logout and token rotation."""

    __tablename__ = "user_sessions"

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        primary_key=True,
        max_length=36,
    )
    user_id: str = Field(foreign_key="users.id", index=True, max_length=36)
    refresh_token: str = Field(unique=True, index=True, max_length=128)
    expires_at: datetime = Field(nullable=False)
    revoked_at: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=_utc_now)
    user_agent: str | None = Field(default=None, max_length=512)
    ip_address: str | None = Field(default=None, max_length=45)
```

### Optional: list and revoke all sessions (`app/api/v1/sessions.py`)

```python
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db.db import get_session
from app.db.models.session import UserSession
from app.db.models.user import User
from app.dependencies.auth import get_current_user

router = APIRouter(prefix="/auth/sessions", tags=["sessions"])


@router.get("/")
async def list_sessions(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.exec(
        select(UserSession).where(
            UserSession.user_id == current_user.id,
            UserSession.revoked_at.is_(None),
        )
    )
    rows = result.all()
    return [
        {
            "id": s.id,
            "created_at": s.created_at,
            "expires_at": s.expires_at,
            "user_agent": s.user_agent,
        }
        for s in rows
    ]


@router.delete("/{session_id}", status_code=204)
async def revoke_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    result = await db.exec(
        select(UserSession).where(
            UserSession.id == session_id,
            UserSession.user_id == current_user.id,
            UserSession.revoked_at.is_(None),
        )
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    row.revoked_at = datetime.now(timezone.utc)
    db.add(row)
    await db.commit()
```

### Cookie-based sessions (alternative)

If your frontend is same-origin (server-rendered or BFF), you can store `user_id` in `request.session` after login instead of returning a JWT. For SPAs and mobile clients, **JWT + refresh token** is the usual choice.

---

## 6. Wire everything in `main.py`

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from app.api.v1.auth import router as auth_router
from app.api.v1.sessions import router as sessions_router  # optional
from app.core.config import get_settings
from app.db.db import init_db

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="My FastAPI App",
    description="API with Authlib JWT auth",
    version="0.1.0",
    lifespan=lifespan,
)

# Required for OAuth social-login state (Google, GitHub, etc.)
# Also usable for cookie sessions if you choose that model.
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SESSION_SECRET,
    session_cookie=settings.SESSION_COOKIE_NAME,
    max_age=settings.SESSION_MAX_AGE,
    https_only=settings.is_production,
    same_site="lax",
)

# Auth routes
app.include_router(auth_router, prefix="/api/v1")
app.include_router(sessions_router, prefix="/api/v1")  # optional


@app.get("/")
def read_root():
    return {"message": "Hello World"}


@app.get("/health")
def health_check():
    return {"status": "ok"}
```

### Optional: Google OAuth routes (`app/api/v1/oauth.py`)

Add these only if you need social login. They rely on `SessionMiddleware`.

```python
from fastapi import APIRouter, HTTPException
from starlette.requests import Request
from authlib.integrations.starlette_client import OAuth

from app.core.config import get_settings

settings = get_settings()
oauth = OAuth()

oauth.register(
    name="google",
    client_id=settings.GOOGLE_CLIENT_ID,
    client_secret=settings.GOOGLE_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

router = APIRouter(prefix="/auth", tags=["oauth"])


@router.get("/login/google")
async def login_google(request: Request):
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=501, detail="Google OAuth not configured")
    redirect_uri = request.url_for("auth_google_callback")
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/auth/google", name="auth_google_callback")
async def auth_google_callback(request: Request):
    token = await oauth.google.authorize_access_token(request)
    userinfo = token.get("userinfo", {})
  # Upsert user in DB, issue your JWT, redirect to frontend with token
    return {"userinfo": userinfo}
```

Register in `main.py`:

```python
from app.api.v1.oauth import router as oauth_router
app.include_router(oauth_router, prefix="/api/v1")
```

### CORS (if frontend is on another origin)

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## 7. Final thoughts

### Architecture at a glance

```
Client
  │
  ├─ POST /auth/signup  ──► bcrypt hash ──► User row + UserSession row
  ├─ POST /auth/login   ──► verify hash ──► Authlib JWT (access) + refresh token
  ├─ GET  /auth/me      ──► Bearer JWT ──► Authlib jwt.decode + DB lookup
  ├─ POST /auth/logout  ──► revoke refresh token in user_sessions
  └─ POST /auth/refresh ──► validate refresh token ──► new access JWT

OAuth (optional)
  ├─ GET /auth/login/google  ──► SessionMiddleware stores OAuth state
  └─ GET /auth/auth/google     ──► Authlib exchanges code ──► upsert user ──► issue JWT
```

### Security checklist

- [ ] `JWT_SECRET` and `SESSION_SECRET` are long random strings from env — never committed to Git
- [ ] Passwords hashed with `bcrypt`; never log or return passwords
- [ ] Access tokens short-lived (15–60 minutes)
- [ ] Refresh tokens stored server-side and revocable on logout
- [ ] Generic error on login failure: `"Invalid email or password"`
- [ ] `https_only=True` on `SessionMiddleware` in production
- [ ] Run schema changes through Alembic in real projects (not only `create_all`)

### Authlib vs building a full OAuth2 server

Authlib can run a complete [OAuth2 Authorization Server](https://docs.authlib.org/en/stable/oauth2/authorization-server/flask/authorization-server.html) with `/oauth/authorize` and `/oauth/token`. That is useful when **your app is the OAuth provider** for third-party clients. For a typical product API, custom `/signup` and `/login` routes plus Authlib JWT is simpler and easier to maintain.

### What this guide does not cover

- Email verification and password reset flows
- MFA / 2FA
- Rate limiting on auth endpoints
- Alembic migrations for `users` and `user_sessions` tables
- Frontend token storage (prefer httpOnly cookies or secure storage on mobile)

### Next steps after following this guide

1. Add Alembic and create migrations for `User` and `UserSession`.
2. Add tests for signup, login, me, logout, and refresh.
3. Configure CORS for your frontend origin.
4. Add OAuth providers if needed (Google, GitHub).
5. Consider token rotation (issue new refresh token on each `/refresh` call) for higher security.

---

*This document is a standalone integration guide for new FastAPI apps. It is not wired into the Finance RAG backend by default — use it as a reference when implementing Authlib auth.*

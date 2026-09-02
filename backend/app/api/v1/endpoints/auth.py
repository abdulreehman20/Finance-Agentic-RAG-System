from datetime import datetime, timedelta, timezone

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from fastapi import APIRouter, Depends, HTTPException, status

from app.db.db import get_session
from app.db.models.user import User
from app.core.config import get_settings
from app.core.auth import get_current_user
from app.db.models.session import UserSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from app.schemas.schemas import (
    AuthResponse,
    LogoutRequest,
    SignInRequest,
    SignUpRequest,
    UserProfile,
)

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


@router.post(
    "/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED
)
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
async def refresh_token(
    body: LogoutRequest, session: AsyncSession = Depends(get_session)
):
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

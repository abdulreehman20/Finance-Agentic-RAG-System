from datetime import datetime, timezone

from sqlmodel import select
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db.db import get_session
from app.db.models.user import User
from app.core.auth import get_current_user
from app.db.models.session import UserSession

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

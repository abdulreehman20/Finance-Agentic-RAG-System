"""End-to-end tests for Clerk authentication endpoints.

Clerk Backend API and database sessions are mocked so the suite runs without
external credentials. Behaviour assertions mirror the production auth service.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from clerk_backend_api.models import ClerkErrors
from clerk_backend_api.models.clerkerror import ClerkError
from clerk_backend_api.models.clerkerrors import ClerkErrorsData
from clerk_backend_api.security.types import TokenVerificationError, TokenVerificationErrorReason
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.router import api_router
from app.db.db import get_session
from app.db.schemas import UserProfile


# ── Fixtures / helpers ──────────────────────────────────────────────────────────


def _clerk_user(
    *,
    user_id: str = "user_test_123",
    email: str = "alice@example.com",
    first_name: str = "Alice",
    last_name: str = "Doe",
    created_at_ms: int | None = None,
):
    """Build a lightweight stand-in for a Clerk ``User`` model."""

    if created_at_ms is None:
        created_at_ms = int(datetime(2024, 1, 15, tzinfo=timezone.utc).timestamp() * 1000)
    email_obj = SimpleNamespace(id="idn_1", email_address=email)
    return SimpleNamespace(
        id=user_id,
        first_name=first_name,
        last_name=last_name,
        primary_email_address_id="idn_1",
        email_addresses=[email_obj],
        created_at=created_at_ms,
    )


def _clerk_errors(message: str = "Identifier already exists", code: str = "form_identifier_exists"):
    """Construct a ClerkErrors-like failure for duplicate-email scenarios."""

    error = ClerkError(
        message=message,
        long_message=message,
        code=code,
        meta={},
    )
    data = ClerkErrorsData(errors=[error])
    raw = MagicMock()
    raw.status_code = 422
    raw.text = message
    raw.headers = {}
    return ClerkErrors(data=data, raw_response=raw, body=message)


@pytest.fixture
def mock_db_session():
    """Async SQLModel session mock used by sign-up (local user sync)."""

    session = AsyncMock()
    session.get = AsyncMock(return_value=None)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def app(mock_db_session):
    """Minimal FastAPI app with auth routes and overridden DB dependency."""

    test_app = FastAPI()
    test_app.include_router(api_router)

    async def _override_session():
        yield mock_db_session

    test_app.dependency_overrides[get_session] = _override_session
    return test_app


@pytest.fixture
async def client(app):
    """Async HTTP client bound to the test ASGI app."""

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ── Sign-up ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_sign_up_success(client, mock_db_session):
    """Valid credentials create a Clerk user, sync locally, and return a JWT."""

    clerk_user = _clerk_user()
    session_obj = SimpleNamespace(id="sess_abc")
    token_obj = SimpleNamespace(jwt="test.session.jwt")

    with (
        patch("app.services.auth.clerk_client") as clerk,
        patch("app.core.clerk.clerk_client", clerk),
    ):
        clerk.users.create_async = AsyncMock(return_value=clerk_user)
        clerk.sessions.create_async = AsyncMock(return_value=session_obj)
        clerk.sessions.create_token_async = AsyncMock(return_value=token_obj)

        response = await client.post(
            "/api/v1/auth/sign-up",
            json={
                "email": "alice@example.com",
                "password": "SecurePass1!",
                "first_name": "Alice",
                "last_name": "Doe",
            },
        )

    assert response.status_code == 201
    body = response.json()
    assert body["user_id"] == "user_test_123"
    assert body["email"] == "alice@example.com"
    assert body["full_name"] == "Alice Doe"
    assert body["session_token"] == "test.session.jwt"
    assert body["token_type"] == "Bearer"
    mock_db_session.add.assert_called_once()
    mock_db_session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_sign_up_duplicate_email(client):
    """Duplicate email from Clerk surfaces as HTTP 409 Conflict."""

    with patch("app.services.auth.clerk_client") as clerk:
        clerk.users.create_async = AsyncMock(side_effect=_clerk_errors())

        response = await client.post(
            "/api/v1/auth/sign-up",
            json={
                "email": "alice@example.com",
                "password": "SecurePass1!",
                "first_name": "Alice",
                "last_name": "Doe",
            },
        )

    assert response.status_code == 409
    assert "already" in response.json()["detail"].lower() or "identifier" in response.json()[
        "detail"
    ].lower()


# ── Sign-in ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_sign_in_success(client):
    """Correct credentials return a Clerk session JWT."""

    clerk_user = _clerk_user()
    session_obj = SimpleNamespace(id="sess_signin")
    token_obj = SimpleNamespace(jwt="signin.session.jwt")

    with patch("app.services.auth.clerk_client") as clerk:
        clerk.users.list_async = AsyncMock(return_value=[clerk_user])
        clerk.users.verify_password_async = AsyncMock(
            return_value=SimpleNamespace(verified=True)
        )
        clerk.sessions.create_async = AsyncMock(return_value=session_obj)
        clerk.sessions.create_token_async = AsyncMock(return_value=token_obj)

        response = await client.post(
            "/api/v1/auth/sign-in",
            json={"email": "alice@example.com", "password": "SecurePass1!"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == "user_test_123"
    assert body["session_token"] == "signin.session.jwt"
    assert body["token_type"] == "Bearer"


@pytest.mark.asyncio
async def test_sign_in_incorrect_credentials(client):
    """Wrong password yields HTTP 401 Unauthorized."""

    clerk_user = _clerk_user()

    with patch("app.services.auth.clerk_client") as clerk:
        clerk.users.list_async = AsyncMock(return_value=[clerk_user])
        clerk.users.verify_password_async = AsyncMock(
            return_value=SimpleNamespace(verified=False)
        )

        response = await client.post(
            "/api/v1/auth/sign-in",
            json={"email": "alice@example.com", "password": "wrong-password"},
        )

    assert response.status_code == 401
    assert "invalid" in response.json()["detail"].lower()


# ── GET /me ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_me_with_valid_token(client):
    """A valid Bearer token returns the authenticated user profile."""

    profile = UserProfile(
        user_id="user_test_123",
        email="alice@example.com",
        full_name="Alice Doe",
        created_at=datetime(2024, 1, 15, tzinfo=timezone.utc),
    )

    with patch("app.core.security.auth_service.get_current_user", new=AsyncMock(return_value=profile)):
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer valid.jwt.token"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == "user_test_123"
    assert body["email"] == "alice@example.com"
    assert body["full_name"] == "Alice Doe"


@pytest.mark.asyncio
async def test_me_missing_token(client):
    """Requests without an Authorization header receive HTTP 401."""

    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert "missing" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_me_invalid_token(client):
    """Malformed / invalid JWTs receive HTTP 401."""

    with patch(
        "app.services.auth.verify_token",
        side_effect=TokenVerificationError(TokenVerificationErrorReason.TOKEN_INVALID),
    ):
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer not-a-real-token"},
        )

    assert response.status_code == 401
    detail = response.json()["detail"].lower()
    assert "invalid" in detail or "malformed" in detail


# ── Sign-out ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_sign_out_success(client):
    """Authenticated sign-out revokes the Clerk session by ``sid``."""

    profile = UserProfile(
        user_id="user_test_123",
        email="alice@example.com",
        full_name="Alice Doe",
        created_at=datetime(2024, 1, 15, tzinfo=timezone.utc),
    )

    with (
        patch("app.core.security.auth_service.get_current_user", new=AsyncMock(return_value=profile)),
        patch(
            "app.core.security.verify_token",
            return_value={"sub": "user_test_123", "sid": "sess_to_revoke"},
        ),
        patch("app.services.auth.clerk_client") as clerk,
    ):
        clerk.sessions.revoke_async = AsyncMock(return_value=SimpleNamespace(id="sess_to_revoke"))

        response = await client.post(
            "/api/v1/auth/sign-out",
            headers={"Authorization": "Bearer valid.jwt.token"},
        )

    assert response.status_code == 204
    clerk.sessions.revoke_async.assert_awaited_once_with(session_id="sess_to_revoke")

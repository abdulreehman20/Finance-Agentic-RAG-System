# Clerk Integration Guide — Finance RAG Backend

This guide explains how Clerk authentication works in **this** FastAPI backend: sign-up, sign-in, JWT verification, and local user sync.

---

## 1. What is Clerk?

**Clerk** is a hosted user-management and authentication platform. It handles:

| Concern | What Clerk provides |
|---------|---------------------|
| Identity | Email/password, OAuth, SSO, passkeys, MFA |
| Sessions | Secure session tokens (JWTs) |
| User store | Profiles, emails, organizations |
| Backend API | Admin operations (create user, verify password, revoke session) |

In this project:

- **Clerk** is the source of truth for credentials and sessions.
- **PostgreSQL** stores a local copy of core profile fields (`id`, `email`, `full_name`, `created_at`) so the app can relate documents, chats, and other data to users **without** storing passwords.

Official resources:

- [Clerk documentation](https://clerk.com/docs)
- [Clerk Python Backend SDK](https://github.com/clerk/clerk-sdk-python)
- Package: [`clerk-backend-api`](https://pypi.org/project/clerk-backend-api/)

---

## 2. How to add Clerk to a FastAPI backend

### High-level architecture

```
Client (Frontend / API consumer)
        │
        │  POST /api/v1/auth/sign-up | sign-in
        │  Authorization: Bearer <session_jwt>
        ▼
FastAPI backend
  ├── auth router        (app/api/v1/endpoints/auth.py)
  ├── auth service       (app/services/auth.py)  → Clerk Backend API
  ├── security deps      (app/core/security.py)  → JWT verify (CLERK_JWT_KEY)
  └── local User table   (app/db/models/user.py) → Neon Postgres
```

### Step-by-step (what this repo already does)

#### 1. Install the official SDK

```bash
uv add clerk-backend-api
```

Also used for JWT verification helpers that ship with the SDK (`verify_token`, `AuthenticateRequestOptions`).

#### 2. Configure credentials

Load keys via `pydantic-settings` in `app/core/config.py` — never hardcode secrets.

#### 3. Create a shared Clerk client

`app/core/clerk.py` initializes:

```python
from clerk_backend_api import Clerk
from app.core.config import get_settings

clerk_client = Clerk(bearer_auth=get_settings().CLERK_SECRET_KEY or None)
```

#### 4. Implement auth service methods

| Function | Clerk SDK usage |
|----------|-----------------|
| `sign_up` | `users.create_async` → `sessions.create_async` → `sessions.create_token_async` |
| `sign_in` | `users.list_async` (by email) → `users.verify_password_async` → create session + JWT |
| `sign_out` | `sessions.revoke_async(session_id)` |
| `get_current_user` | `verify_token(token, VerifyTokenOptions(jwt_key=...))` → `users.get_async` |

#### 5. Protect routes with a FastAPI dependency

`app/core/security.py` extracts the Bearer token and verifies it with Clerk’s public JWT key (`CLERK_JWT_KEY`) before returning a `UserProfile`.

#### 6. Register the router

`app/api/v1/router.py` mounts auth under `/api/v1`, and `app/main.py` includes that router.

#### 7. Sync users to Postgres on sign-up

After Clerk creates the user, `sync_user_to_db` upserts a local `users` row keyed by the Clerk user ID (e.g. `user_2abc...`).

> **Note:** `sessions.create` is intended for development / custom testing flows. Production apps typically establish sessions via Clerk’s Frontend API and only **verify** tokens on the backend.

---

## 3. Project setup & environment variables

### Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) package manager
- Neon (or any Postgres) database
- A Clerk application in the [Clerk Dashboard](https://dashboard.clerk.com)

### Install dependencies

From the `backend` directory:

```bash
uv sync
```

### Environment variables

Copy `.env.example` → `.env` (or edit `.env` directly) and set:

```env
# Database (asyncpg). Neon URLs with sslmode=require are supported —
# the app strips libpq-only params and enables SSL for asyncpg.
DATABASE_URL=postgresql://USER:PASSWORD@HOST/DB?sslmode=require

# Clerk Authentication
CLERK_SECRET_KEY=sk_test_...          # Backend API secret (Dashboard → API Keys)
CLERK_PUBLISHABLE_KEY=pk_test_...     # Frontend publishable key
CLERK_JWT_KEY=-----BEGIN PUBLIC KEY-----
...
-----END PUBLIC KEY-----              # JWT public key for networkless verification

# Runtime
ENVIRONMENT=development
DEBUG=true
```

| Variable | Where to get it | Used by |
|----------|-----------------|---------|
| `CLERK_SECRET_KEY` | Dashboard → **API Keys** → Secret key | All Backend API calls (`clerk_client`) |
| `CLERK_PUBLISHABLE_KEY` | Dashboard → **API Keys** → Publishable key | Frontend / reference (stored in settings) |
| `CLERK_JWT_KEY` | Dashboard → **API Keys** → **JWT public key** (PEM) | Networkless JWT verification in `security.py` / `auth.py` |

Settings are defined in `app/core/config.py` and loaded with `pydantic-settings`.

### Where keys are wired

| File | Role |
|------|------|
| `app/core/config.py` | Declares `CLERK_*` settings |
| `app/core/clerk.py` | Builds `Clerk(bearer_auth=CLERK_SECRET_KEY)` |
| `app/core/security.py` | Verifies Bearer JWT with `CLERK_JWT_KEY` |
| `app/services/auth.py` | Sign-up / sign-in / sign-out / profile |

### Run the API

```bash
fastapi dev .\app\main.py
```

- API: http://127.0.0.1:8000  
- Swagger docs: http://127.0.0.1:8000/docs  

### Run auth tests

```bash
pytest tests/test_auth.py -v
```

Tests mock the Clerk SDK and the DB session, so real credentials are not required for CI.

---

## 4. APIs created for auth

Base path: **`/api/v1/auth`**

Router: `app/api/v1/endpoints/auth.py`  
Schemas: `app/db/schemas.py`

### Summary

| Method | Endpoint | Auth required | Description |
|--------|----------|---------------|-------------|
| `POST` | `/api/v1/auth/sign-up` | No | Register via Clerk, sync to DB, return session JWT |
| `POST` | `/api/v1/auth/sign-in` | No | Verify email/password, return session JWT |
| `POST` | `/api/v1/auth/sign-out` | Yes (Bearer) | Revoke current Clerk session |
| `GET` | `/api/v1/auth/me` | Yes (Bearer) | Return authenticated user profile |

Protected routes expect:

```http
Authorization: Bearer <session_token>
```

---

### `POST /api/v1/auth/sign-up`

Creates a Clerk user, upserts a local `users` row, and returns a session JWT.

**Request body (`SignUpRequest`)**

```json
{
  "email": "alice@example.com",
  "password": "SecurePass1!",
  "first_name": "Alice",
  "last_name": "Doe"
}
```

**Success — `201 Created` (`AuthResponse`)**

```json
{
  "user_id": "user_2abc...",
  "email": "alice@example.com",
  "full_name": "Alice Doe",
  "session_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "Bearer"
}
```

**Common errors**

| Status | When |
|--------|------|
| `409 Conflict` | Email already registered in Clerk |
| `400 Bad Request` | Clerk rejected the payload (weak password, validation, etc.) |

---

### `POST /api/v1/auth/sign-in`

Looks up the user by email, verifies the password with Clerk, then mints a session JWT.

**Request body (`SignInRequest`)**

```json
{
  "email": "alice@example.com",
  "password": "SecurePass1!"
}
```

**Success — `200 OK` (`AuthResponse`)**

Same shape as sign-up.

**Common errors**

| Status | When |
|--------|------|
| `401 Unauthorized` | Unknown email or wrong password |

---

### `POST /api/v1/auth/sign-out`

Revokes the Clerk session identified by the JWT’s `sid` claim.

**Headers**

```http
Authorization: Bearer <session_token>
```

**Success — `204 No Content`**

Empty body.

**Common errors**

| Status | When |
|--------|------|
| `401 Unauthorized` | Missing, expired, or invalid token |
| `400 Bad Request` | Session ID missing / revoke failed |

---

### `GET /api/v1/auth/me`

Verifies the Bearer JWT and returns the Clerk user profile.

**Headers**

```http
Authorization: Bearer <session_token>
```

**Success — `200 OK` (`UserProfile`)**

```json
{
  "user_id": "user_2abc...",
  "email": "alice@example.com",
  "full_name": "Alice Doe",
  "created_at": "2024-01-15T00:00:00Z"
}
```

**Common errors**

| Status | Detail (examples) |
|--------|-------------------|
| `401` | `Missing authentication token.` |
| `401` | `Authentication token has expired.` |
| `401` | `Malformed or invalid authentication token.` |

---

## 5. Related project files

| Path | Purpose |
|------|---------|
| `app/core/config.py` | Env settings including `CLERK_*` |
| `app/core/clerk.py` | Shared `clerk_client` |
| `app/core/security.py` | `get_current_user` / `get_authenticated_context` |
| `app/services/auth.py` | Auth business logic |
| `app/db/schemas.py` | Request/response Pydantic models |
| `app/db/models/user.py` | Local `users` SQLModel table |
| `app/db/db.py` | Async engine + session (asyncpg + SSL) |
| `app/api/v1/endpoints/auth.py` | HTTP routes |
| `app/api/v1/router.py` | Mounts auth under `/api/v1` |
| `tests/test_auth.py` | Auth endpoint tests |

---

## 6. Quick smoke checklist

1. Set `CLERK_SECRET_KEY`, `CLERK_PUBLISHABLE_KEY`, and `CLERK_JWT_KEY` in `.env`.
2. Confirm `DATABASE_URL` points at Neon (or local Postgres).
3. Start the server: `fastapi dev .\app\main.py`.
4. Open http://127.0.0.1:8000/docs and exercise **Auth** endpoints.
5. Call `GET /me` with the `session_token` from sign-up/sign-in as a Bearer token.

"""Integration test for auth API routes (in-process ASGI — no live server required)."""

from __future__ import annotations

import asyncio
import json
import sys
import uuid

from httpx import ASGITransport, AsyncClient

from app.main import app

EMAIL = f"auth.test.{uuid.uuid4().hex[:8]}@example.com"
PASSWORD = "SecurePass123!"


async def run_tests() -> list[tuple[str, bool, str]]:
    results: list[tuple[str, bool, str]] = []
    access_token = ""
    refresh_token = ""
    session_id = ""

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/health")
        results.append(("GET /health", r.status_code == 200, str(r.status_code)))

        r = await client.post(
            "/api/v1/auth/signup",
            json={
                "email": EMAIL,
                "password": PASSWORD,
                "first_name": "Auth",
                "last_name": "Tester",
            },
        )
        ok = r.status_code == 201
        if ok:
            data = r.json()
            access_token = data["access_token"]
            refresh_token = data["refresh_token"]
        results.append(("POST /api/v1/auth/signup", ok, f"{r.status_code} {r.text[:300]}"))

        r = await client.post(
            "/api/v1/auth/signup",
            json={
                "email": EMAIL,
                "password": PASSWORD,
                "first_name": "Auth",
                "last_name": "Tester",
            },
        )
        results.append(
            ("POST /api/v1/auth/signup duplicate", r.status_code == 409, str(r.status_code))
        )

        r = await client.post(
            "/api/v1/auth/login",
            json={"email": EMAIL, "password": PASSWORD},
        )
        ok = r.status_code == 200
        if ok:
            data = r.json()
            access_token = data["access_token"]
            refresh_token = data["refresh_token"]
        results.append(("POST /api/v1/auth/login", ok, f"{r.status_code} {r.text[:300]}"))

        r = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        results.append(("GET /api/v1/auth/me", r.status_code == 200, f"{r.status_code} {r.text[:300]}"))

        r = await client.get("/api/v1/auth/me")
        results.append(("GET /api/v1/auth/me no token", r.status_code == 401, str(r.status_code)))

        r = await client.get(
            "/api/v1/auth/sessions/",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        ok = r.status_code == 200
        if ok and r.json():
            session_id = r.json()[0]["id"]
        results.append(
            ("GET /api/v1/auth/sessions/", ok, f"{r.status_code} {r.text[:300]}")
        )

        r = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        ok = r.status_code == 200
        if ok:
            access_token = r.json()["access_token"]
        results.append(("POST /api/v1/auth/refresh", ok, f"{r.status_code} {r.text[:200]}"))

        r = await client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"refresh_token": refresh_token},
        )
        results.append(("POST /api/v1/auth/logout", r.status_code == 204, str(r.status_code)))

        r = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        results.append(
            ("POST /api/v1/auth/refresh after logout", r.status_code == 401, str(r.status_code))
        )

        r = await client.post(
            "/api/v1/auth/login",
            json={"email": EMAIL, "password": PASSWORD},
        )
        if r.status_code == 200:
            access_token = r.json()["access_token"]
            refresh_token = r.json()["refresh_token"]
            r2 = await client.get(
                "/api/v1/auth/sessions/",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if r2.status_code == 200 and r2.json():
                session_id = r2.json()[-1]["id"]
                r3 = await client.delete(
                    f"/api/v1/auth/sessions/{session_id}",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                results.append(
                    ("DELETE /api/v1/auth/sessions/{id}", r3.status_code == 204, str(r3.status_code))
                )
            else:
                results.append(("DELETE /api/v1/auth/sessions/{id}", False, "no sessions"))
        else:
            results.append(("DELETE /api/v1/auth/sessions/{id}", False, "login failed"))

    return results


def main() -> int:
    results = asyncio.run(run_tests())
    print(json.dumps({"email": EMAIL, "results": results}, indent=2))
    failed = [name for name, ok, _ in results if not ok]
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

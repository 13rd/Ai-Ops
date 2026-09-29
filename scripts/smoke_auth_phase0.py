import asyncio
import sys
from typing import Optional

import httpx

from app.db.base import AsyncSessionLocal
from app.models.user import UserRole
from app.schemas.user import UserCreate
from app.services.auth.auth_service import AuthService

SMOKE_USERNAME = "smoke_phase0_user"
SMOKE_PASSWORD = "smoke-test-pw-1234"

async def ensure_smoke_user() -> None:
    async with AsyncSessionLocal() as db:
        existing = await AuthService.get_user_by_username(db, SMOKE_USERNAME)
        if existing:
            return
        await AuthService.create_user(
            db,
            UserCreate(
                email=f"{SMOKE_USERNAME}@example.com",
                username=SMOKE_USERNAME,
                role=UserRole.ADMIN.value,
                password=SMOKE_PASSWORD,
            ),
        )

def _print(label: str, response: httpx.Response, cookies: Optional[httpx.Cookies] = None) -> None:
    print(f"\n=== {label} ===")
    print(f"status: {response.status_code}")
    try:
        print(f"body:   {response.json()}")
    except Exception:
        print(f"body:   {response.text[:300]}")
    if cookies is not None:
        cookie_pairs = [(c.name, "<set>" if c.value else "<empty>") for c in cookies.jar]
        print(f"cookies: {cookie_pairs}")

async def run() -> int:
    from httpx import ASGITransport

    from app.main import app

    await ensure_smoke_user()

    failures: list[str] = []
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        r = await client.post(
            "/api/v1/auth/login",
            json={"username": SMOKE_USERNAME, "password": SMOKE_PASSWORD},
        )
        _print("LOGIN", r, client.cookies)
        if r.status_code != 200 or not r.json().get("success"):
            failures.append("login failed")
        access_after_login = r.json().get("data", {}).get("access_token")
        if not access_after_login:
            failures.append("no access_token in login response")
        cookie_after_login = next(
            (c.value for c in client.cookies.jar if c.name == "refresh_token"), None
        )
        if not cookie_after_login:
            failures.append("login did not set refresh_token cookie")

        r = await client.post("/api/v1/auth/refresh")
        _print("REFRESH (valid cookie)", r, client.cookies)
        if r.status_code != 200 or not r.json().get("data", {}).get("access_token"):
            failures.append("refresh failed")
        cookie_after_refresh = next(
            (c.value for c in client.cookies.jar if c.name == "refresh_token"), None
        )
        if cookie_after_refresh == cookie_after_login:
            failures.append("refresh cookie did not rotate")

        r = await client.post("/api/v1/auth/logout")
        _print("LOGOUT", r, client.cookies)
        if r.status_code != 200:
            failures.append("logout returned non-200")

        r = await client.post("/api/v1/auth/refresh")
        _print("REFRESH (after logout)", r, client.cookies)
        body = r.json()
        if r.status_code != 401 or body.get("success") is not False:
            failures.append("refresh after logout did not return 401")
        if body.get("error", {}).get("code") != "authentication_failed":
            failures.append("refresh after logout: wrong error code")

        r = await client.post("/api/v1/auth/logout")
        _print("LOGOUT (no cookie)", r, client.cookies)
        if r.status_code != 200:
            failures.append("idempotent logout returned non-200")

    print("\n========== SMOKE RESULT ==========")
    if failures:
        for f in failures:
            print(f"  FAIL: {f}")
        return 1
    print("  All checks passed.")
    return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(run()))

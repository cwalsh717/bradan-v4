"""Tests for POST /api/auth/sync — Clerk JWT decode + user upsert.

All external dependencies (DB, JWT secret) are mocked.
Follows existing test patterns: httpx ASGITransport + AsyncClient,
mock get_session via dependency_overrides, try/finally cleanup.
"""

import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import jwt
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.database import get_session
from app.main import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _session_override(mock_db):
    """Return an async generator factory suitable for dependency_overrides."""

    async def _override():
        yield mock_db

    return _override


def _scalar_one_or_none_result(value):
    """Wrap a value so result.scalar_one_or_none() returns it."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _make_test_jwt(claims: dict = None, expired: bool = False) -> str:
    """Create a real HS256 JWT signed with the test CLERK_SECRET_KEY."""
    claims = claims or {}
    now = int(time.time())
    payload = {
        "sub": claims.get("sub", "clerk_user_123"),
        "email": claims.get("email", "test@example.com"),
        "name": claims.get("name", "Test User"),
        "iat": now,
        "exp": now + (-3600 if expired else 3600),
    }
    payload.update(claims)
    return jwt.encode(payload, settings.CLERK_SECRET_KEY, algorithm="HS256")


def _make_mock_user(**overrides):
    """Return a MagicMock that looks like a User ORM instance."""
    defaults = {
        "id": 1,
        "clerk_id": "clerk_user_123",
        "email": "old@example.com",
        "display_name": "Old Name",
        "created_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
        "last_login": datetime(2025, 1, 1, tzinfo=timezone.utc),
    }
    defaults.update(overrides)
    user = MagicMock()
    for k, v in defaults.items():
        setattr(user, k, v)
    return user


# ---------------------------------------------------------------------------
# 1. Valid JWT, user does not exist → creates new user
# ---------------------------------------------------------------------------


async def test_sync_creates_new_user():
    """POST /api/auth/sync with a valid JWT for an unknown clerk_id creates a user."""
    mock_db = AsyncMock()
    # SELECT returns no existing user
    mock_db.execute = AsyncMock(
        return_value=_scalar_one_or_none_result(None),
    )

    # Capture the User object passed to session.add and assign an id
    captured = []

    def capture_add(obj):
        obj.id = 42
        captured.append(obj)

    mock_db.add = MagicMock(side_effect=capture_add)

    app.dependency_overrides[get_session] = _session_override(mock_db)

    try:
        token = _make_test_jwt({"sub": "clerk_new_user", "email": "new@example.com", "name": "New User"})
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post(
                "/api/auth/sync",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["clerk_id"] == "clerk_new_user"
        assert body["email"] == "new@example.com"
        assert body["display_name"] == "New User"
        assert body["id"] == 42

        # Verify session interactions
        assert len(captured) == 1
        mock_db.flush.assert_awaited_once()
        mock_db.commit.assert_awaited_once()
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 2. Valid JWT, user already exists → updates existing user
# ---------------------------------------------------------------------------


async def test_sync_updates_existing_user():
    """POST /api/auth/sync with a valid JWT for an existing user updates fields."""
    existing_user = _make_mock_user(
        id=7,
        clerk_id="clerk_user_123",
        email="old@example.com",
        display_name="Old Name",
    )

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(
        return_value=_scalar_one_or_none_result(existing_user),
    )

    app.dependency_overrides[get_session] = _session_override(mock_db)

    try:
        token = _make_test_jwt({"sub": "clerk_user_123", "email": "updated@example.com", "name": "Updated Name"})
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post(
                "/api/auth/sync",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == 7
        assert body["clerk_id"] == "clerk_user_123"
        assert body["email"] == "updated@example.com"
        assert body["display_name"] == "Updated Name"

        # session.add should NOT have been called (existing user)
        mock_db.add.assert_not_called()
        mock_db.flush.assert_awaited_once()
        mock_db.commit.assert_awaited_once()

        # Verify the existing user object was mutated
        assert existing_user.email == "updated@example.com"
        assert existing_user.display_name == "Updated Name"
        assert existing_user.last_login is not None
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 3. Invalid / garbage token → 401
# ---------------------------------------------------------------------------


async def test_sync_rejects_invalid_token():
    """POST /api/auth/sync with a garbage token returns 401."""
    mock_db = AsyncMock()
    app.dependency_overrides[get_session] = _session_override(mock_db)

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post(
                "/api/auth/sync",
                headers={"Authorization": "Bearer not.a.real.jwt.token"},
            )

        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid or expired token"

        # DB should never be queried for an invalid token
        mock_db.execute.assert_not_awaited()
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 4. Expired JWT → 401
# ---------------------------------------------------------------------------


async def test_sync_rejects_expired_token():
    """POST /api/auth/sync with an expired JWT returns 401."""
    mock_db = AsyncMock()
    app.dependency_overrides[get_session] = _session_override(mock_db)

    try:
        token = _make_test_jwt(expired=True)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post(
                "/api/auth/sync",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid or expired token"

        # DB should never be queried for an expired token
        mock_db.execute.assert_not_awaited()
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 5. Missing Authorization header → 403 (HTTPBearer default)
# ---------------------------------------------------------------------------


async def test_sync_missing_auth_header():
    """POST /api/auth/sync without an Authorization header is rejected."""
    mock_db = AsyncMock()
    app.dependency_overrides[get_session] = _session_override(mock_db)

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post("/api/auth/sync")

        # HTTPBearer rejects missing credentials (401 or 403 depending on version)
        assert resp.status_code in (401, 403)
        mock_db.execute.assert_not_awaited()
    finally:
        app.dependency_overrides.clear()

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_health_returns_200(client):
    resp = await client.get("/health")
    assert resp.status_code == 200


async def test_health_has_required_fields(client):
    resp = await client.get("/health")
    data = resp.json()
    assert "status" in data
    assert "database" in data
    assert "version" in data
    assert "environment" in data


async def test_health_database_connected():
    """Test health reports connected when DB is reachable."""
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock(side_effect=[
        None,  # SELECT 1
        MagicMock(scalar=MagicMock(return_value=20)),  # table count
    ])

    mock_engine_connect = AsyncMock()
    mock_engine_connect.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_engine_connect.__aexit__ = AsyncMock(return_value=False)

    with patch("app.routers.utility.engine") as mock_engine:
        mock_engine.connect.return_value = mock_engine_connect

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get("/health")

    data = resp.json()
    assert data["database"] == "connected"
    assert data["status"] == "healthy"

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.services.fred import FredClient
from app.services.twelvedata import TwelveDataClient


@pytest_asyncio.fixture
async def mock_twelvedata():
    """TwelveDataClient with mocked httpx transport."""
    client = TwelveDataClient(api_key="test_key")
    await client.client.aclose()
    mock_transport = httpx.MockTransport(lambda req: httpx.Response(200, json={}))
    client.client = httpx.AsyncClient(
        base_url="https://api.twelvedata.com", transport=mock_transport
    )
    yield client
    await client.close()


@pytest_asyncio.fixture
async def mock_fred():
    """FredClient with mocked httpx transport."""
    client = FredClient(api_key="test_key")
    await client.client.aclose()
    mock_transport = httpx.MockTransport(lambda req: httpx.Response(200, json={}))
    client.client = httpx.AsyncClient(
        base_url="https://api.stlouisfed.org", transport=mock_transport
    )
    yield client
    await client.close()


def make_twelvedata_transport(response_data, status_code=200):
    """Create a mock transport that returns the given response."""
    def handler(request):
        return httpx.Response(status_code, json=response_data)
    return httpx.MockTransport(handler)


def make_fred_transport(response_data, status_code=200):
    """Create a mock transport that returns the given response."""
    def handler(request):
        return httpx.Response(status_code, json=response_data)
    return httpx.MockTransport(handler)

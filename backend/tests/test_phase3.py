"""Phase 3 test suite: seed, ws_manager, fred_scheduler, dashboard config."""

import json
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.fred_scheduler import FredScheduler
from app.services.seed import DASHBOARD_TICKERS, seed_dashboard_tickers
from app.services.ws_manager import PROFILE_SYMBOL_TTL_S, TwelveDataWSManager


# ======================================================================
# Seed tests
# ======================================================================


async def test_seed_inserts_all_tickers():
    """When no existing tickers in DB, all 27 are inserted via session.add."""
    mock_session = AsyncMock()

    # Simulate empty DB (no existing tickers)
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_result.scalars.return_value = mock_scalars
    mock_session.execute = AsyncMock(return_value=mock_result)

    total = await seed_dashboard_tickers(mock_session)

    assert total == 27
    assert mock_session.add.call_count == 27
    mock_session.commit.assert_awaited_once()


async def test_seed_updates_existing_tickers():
    """Existing tickers are updated in-place, not duplicated via add."""
    mock_session = AsyncMock()

    # Simulate 3 existing tickers (SPY, QQQ, IWM)
    existing_tickers = []
    for symbol in ("SPY", "QQQ", "IWM"):
        t = MagicMock()
        t.symbol = symbol
        existing_tickers.append(t)

    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = existing_tickers
    mock_result.scalars.return_value = mock_scalars
    mock_session.execute = AsyncMock(return_value=mock_result)

    total = await seed_dashboard_tickers(mock_session)

    assert total == 27
    # 27 total minus 3 existing = 24 inserts
    assert mock_session.add.call_count == 24
    mock_session.commit.assert_awaited_once()


async def test_seed_is_idempotent():
    """Calling seed twice with all existing tickers yields same count, zero adds."""
    # Build mock tickers for every seed entry
    existing_tickers = []
    for _cat, symbol, _dn, _ds, _df, _do in DASHBOARD_TICKERS:
        t = MagicMock()
        t.symbol = symbol
        existing_tickers.append(t)

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = existing_tickers
    mock_result.scalars.return_value = mock_scalars
    mock_session.execute = AsyncMock(return_value=mock_result)

    total_first = await seed_dashboard_tickers(mock_session)
    total_second = await seed_dashboard_tickers(mock_session)

    assert total_first == 27
    assert total_second == 27
    # All tickers already exist: no session.add calls
    assert mock_session.add.call_count == 0


async def test_seed_categories_correct():
    """All 8 expected categories are present in DASHBOARD_TICKERS."""
    categories = {t[0] for t in DASHBOARD_TICKERS}
    expected = {
        "equities",
        "rates",
        "credit",
        "currencies",
        "commodities",
        "critical_minerals",
        "crypto",
        "futures",
    }
    assert categories == expected


# ======================================================================
# WS Manager tests
# ======================================================================


async def test_ws_manager_subscribe_sends_correct_payload():
    """subscribe() sends the expected JSON payload to the upstream WS."""
    manager = TwelveDataWSManager("test_key")
    manager._ws = AsyncMock()

    await manager.subscribe(["AAPL", "MSFT"])

    manager._ws.send.assert_awaited_once()
    sent = json.loads(manager._ws.send.call_args[0][0])
    assert sent["action"] == "subscribe"
    assert "AAPL" in sent["params"]["symbols"]
    assert "MSFT" in sent["params"]["symbols"]


async def test_ws_manager_unsubscribe_filters_still_needed():
    """unsubscribe() skips symbols that are still in dashboard_symbols."""
    manager = TwelveDataWSManager("test_key")
    manager._ws = AsyncMock()
    manager.dashboard_symbols = {"AAPL"}

    await manager.unsubscribe(["AAPL"])

    # AAPL is still needed by dashboard -- send should NOT be called
    manager._ws.send.assert_not_awaited()


async def test_ws_manager_handle_price_stores_in_memory():
    """_handle_price() stores the price dict in self.prices keyed by symbol."""
    manager = TwelveDataWSManager("test_key")

    msg = {
        "event": "price",
        "symbol": "AAPL",
        "price": "150.25",
        "timestamp": 1700000000,
        "day_change": "1.50",
        "day_change_percent": "1.01",
    }
    manager._handle_price(msg)

    assert "AAPL" in manager.prices
    assert manager.prices["AAPL"]["price"] == "150.25"
    assert manager.prices["AAPL"]["symbol"] == "AAPL"
    assert manager.prices["AAPL"]["change"] == "1.50"
    assert manager.prices["AAPL"]["percent_change"] == "1.01"


async def test_ws_manager_get_price_returns_cached():
    """get_price() returns the cached price dict for a known symbol."""
    manager = TwelveDataWSManager("test_key")
    manager.prices["TSLA"] = {
        "symbol": "TSLA",
        "price": "200.00",
        "timestamp": 1700000000,
        "change": "5.00",
        "percent_change": "2.56",
    }

    result = manager.get_price("TSLA")
    assert result is not None
    assert result["symbol"] == "TSLA"
    assert result["price"] == "200.00"

    # Unknown symbol returns None
    assert manager.get_price("NOPE") is None


async def test_ws_manager_get_all_prices():
    """get_all_prices() returns a copy of all cached prices."""
    manager = TwelveDataWSManager("test_key")
    manager.prices["AAPL"] = {"symbol": "AAPL", "price": "150.00"}
    manager.prices["MSFT"] = {"symbol": "MSFT", "price": "300.00"}

    result = manager.get_all_prices()
    assert len(result) == 2
    assert "AAPL" in result
    assert "MSFT" in result
    # Verify it is a copy, not the same dict
    assert result is not manager.prices


async def test_ws_manager_register_profile_listener():
    """register_profile_listener() adds to profile_symbols and subscribes."""
    manager = TwelveDataWSManager("test_key")
    manager._ws = AsyncMock()

    await manager.register_profile_listener("GOOG")

    assert "GOOG" in manager.profile_symbols
    # Should have called subscribe since symbol is new
    manager._ws.send.assert_awaited_once()
    sent = json.loads(manager._ws.send.call_args[0][0])
    assert sent["action"] == "subscribe"
    assert "GOOG" in sent["params"]["symbols"]


async def test_ws_manager_heartbeat_updates_timestamp():
    """heartbeat_profile() updates the last_active timestamp."""
    manager = TwelveDataWSManager("test_key")
    old_ts = time.monotonic() - 100
    manager.profile_symbols["AAPL"] = old_ts

    manager.heartbeat_profile("AAPL")

    assert manager.profile_symbols["AAPL"] > old_ts


async def test_ws_manager_cleanup_removes_stale():
    """_cleanup_stale_profiles() removes symbols idle > PROFILE_SYMBOL_TTL_S
    and calls unsubscribe."""
    manager = TwelveDataWSManager("test_key")
    manager._ws = AsyncMock()

    # Set a stale symbol (well past TTL)
    stale_ts = time.monotonic() - PROFILE_SYMBOL_TTL_S - 100
    manager.profile_symbols["OLD"] = stale_ts

    # Set a fresh symbol
    manager.profile_symbols["FRESH"] = time.monotonic()

    await manager._cleanup_stale_profiles()

    # OLD should be removed
    assert "OLD" not in manager.profile_symbols
    # FRESH should remain
    assert "FRESH" in manager.profile_symbols

    # unsubscribe should have been called for OLD
    manager._ws.send.assert_awaited_once()
    sent = json.loads(manager._ws.send.call_args[0][0])
    assert sent["action"] == "unsubscribe"
    assert "OLD" in sent["params"]["symbols"]


# ======================================================================
# FRED Scheduler tests
# ======================================================================


async def test_fred_scheduler_get_value():
    """get_value() returns the cached dict for a known series."""
    mock_client = MagicMock()
    mock_factory = MagicMock()
    scheduler = FredScheduler(client=mock_client, session_factory=mock_factory)

    scheduler.latest_values["DGS10"] = {
        "value": 4.25,
        "date": "2024-01-15",
        "updated_at": datetime.now(timezone.utc),
    }

    result = scheduler.get_value("DGS10")
    assert result is not None
    assert result["value"] == 4.25

    # Unknown series returns None
    assert scheduler.get_value("NOPE") is None


async def test_fred_scheduler_get_all_values():
    """get_all_values() returns a copy of all cached values."""
    mock_client = MagicMock()
    mock_factory = MagicMock()
    scheduler = FredScheduler(client=mock_client, session_factory=mock_factory)

    now = datetime.now(timezone.utc)
    scheduler.latest_values["DGS10"] = {
        "value": 4.25,
        "date": "2024-01-15",
        "updated_at": now,
    }
    scheduler.latest_values["DGS2"] = {
        "value": 3.80,
        "date": "2024-01-15",
        "updated_at": now,
    }

    result = scheduler.get_all_values()
    assert len(result) == 2
    assert "DGS10" in result
    assert "DGS2" in result
    # Verify it is a copy
    assert result is not scheduler.latest_values


async def test_fred_scheduler_compute_spread():
    """_compute_spread() calculates SPREAD_2S10S = DGS10 - DGS2."""
    mock_client = MagicMock()
    mock_factory = MagicMock()
    scheduler = FredScheduler(client=mock_client, session_factory=mock_factory)

    now = datetime.now(timezone.utc)
    scheduler.latest_values["DGS10"] = {
        "value": 4.25,
        "date": "2024-01-15",
        "updated_at": now,
    }
    scheduler.latest_values["DGS2"] = {
        "value": 3.80,
        "date": "2024-01-14",
        "updated_at": now,
    }

    scheduler._compute_spread(now)

    assert "SPREAD_2S10S" in scheduler.latest_values
    spread = scheduler.latest_values["SPREAD_2S10S"]
    assert spread["value"] == round(4.25 - 3.80, 4)
    # Uses the more recent date
    assert spread["date"] == "2024-01-15"


async def test_fred_scheduler_compute_spread_missing_data():
    """_compute_spread() does nothing when DGS2 is missing."""
    mock_client = MagicMock()
    mock_factory = MagicMock()
    scheduler = FredScheduler(client=mock_client, session_factory=mock_factory)

    now = datetime.now(timezone.utc)
    scheduler.latest_values["DGS10"] = {
        "value": 4.25,
        "date": "2024-01-15",
        "updated_at": now,
    }
    # DGS2 is intentionally missing

    scheduler._compute_spread(now)

    assert "SPREAD_2S10S" not in scheduler.latest_values


async def test_fred_scheduler_fetch_and_cache():
    """fetch_and_cache() calls fetch_daily_update and populates the cache."""
    mock_client = MagicMock()

    # Build an async context manager mock for session_factory
    mock_session = AsyncMock()
    mock_factory = MagicMock()
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)
    mock_factory.return_value = mock_ctx

    scheduler = FredScheduler(client=mock_client, session_factory=mock_factory)

    mock_service = AsyncMock()
    mock_service.fetch_daily_update = AsyncMock(
        return_value={"DGS10": 5, "DGS2": 5, "BAMLC0A0CM": 3, "BAMLH0A0HYM2": 2}
    )

    # Return latest values for each series
    async def mock_get_latest(series_id):
        data = {
            "DGS10": {"value": 4.25, "date": "2024-01-15"},
            "DGS2": {"value": 3.80, "date": "2024-01-15"},
            "BAMLC0A0CM": {"value": 1.10, "date": "2024-01-15"},
            "BAMLH0A0HYM2": {"value": 3.50, "date": "2024-01-15"},
        }
        return data.get(series_id)

    mock_service.get_latest_value = AsyncMock(side_effect=mock_get_latest)

    with patch(
        "app.services.fred_scheduler.FredDataService",
        return_value=mock_service,
    ):
        await scheduler.fetch_and_cache()

    mock_service.fetch_daily_update.assert_awaited_once()

    # All 4 series + SPREAD_2S10S should be cached
    assert len(scheduler.latest_values) == 5
    assert "DGS10" in scheduler.latest_values
    assert "DGS2" in scheduler.latest_values
    assert "BAMLC0A0CM" in scheduler.latest_values
    assert "BAMLH0A0HYM2" in scheduler.latest_values
    assert "SPREAD_2S10S" in scheduler.latest_values
    assert scheduler.latest_values["SPREAD_2S10S"]["value"] == round(4.25 - 3.80, 4)


# ======================================================================
# Dashboard config endpoint tests
# ======================================================================


async def test_dashboard_config_returns_grouped_tickers():
    """GET /api/dashboard/config returns tickers grouped by category."""
    from app.database import get_session

    # Build mock ticker rows
    tickers = []
    for i, (cat, sym) in enumerate(
        [("equities", "SPY"), ("equities", "QQQ"), ("rates", "DGS10")]
    ):
        t = MagicMock()
        t.id = i + 1
        t.category = cat
        t.symbol = sym
        t.display_name = f"Test {sym}"
        t.data_source = "twelvedata_ws" if cat == "equities" else "fred_daily"
        t.display_format = "price" if cat == "equities" else "percentage"
        t.display_order = i + 1
        t.is_active = True
        tickers.append(t)

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = tickers
    mock_result.scalars.return_value = mock_scalars
    mock_session.execute = AsyncMock(return_value=mock_result)

    async def mock_session_override():
        yield mock_session

    app.dependency_overrides[get_session] = mock_session_override

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get("/api/dashboard/config")

        assert resp.status_code == 200
        data = resp.json()
        assert "categories" in data

        cat_names = [cat["name"] for cat in data["categories"]]
        assert "equities" in cat_names
        assert "rates" in cat_names

        # equities should have 2 tickers
        equities = next(c for c in data["categories"] if c["name"] == "equities")
        assert len(equities["tickers"]) == 2
    finally:
        app.dependency_overrides.clear()


async def test_dashboard_config_only_active():
    """GET /api/dashboard/config returns only is_active=True tickers
    (the DB query already filters by is_active; verify nothing leaks)."""
    from app.database import get_session

    # Only return active tickers in mock -- simulating the WHERE clause
    active_ticker = MagicMock()
    active_ticker.id = 1
    active_ticker.category = "equities"
    active_ticker.symbol = "SPY"
    active_ticker.display_name = "S&P 500"
    active_ticker.data_source = "twelvedata_ws"
    active_ticker.display_format = "price"
    active_ticker.display_order = 1
    active_ticker.is_active = True

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [active_ticker]
    mock_result.scalars.return_value = mock_scalars
    mock_session.execute = AsyncMock(return_value=mock_result)

    async def mock_session_override():
        yield mock_session

    app.dependency_overrides[get_session] = mock_session_override

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get("/api/dashboard/config")

        assert resp.status_code == 200
        data = resp.json()
        all_symbols = []
        for cat in data["categories"]:
            for t in cat["tickers"]:
                all_symbols.append(t["symbol"])

        assert all_symbols == ["SPY"]
    finally:
        app.dependency_overrides.clear()


# ======================================================================
# Stock profile WS — unit test of register/unregister via manager
# ======================================================================


async def test_stock_profile_ws_registers_and_unregisters():
    """Verify register_profile_listener and unregister_profile_listener
    update the manager state correctly (unit test approach)."""
    manager = TwelveDataWSManager("test_key")
    manager._ws = AsyncMock()

    # Register
    await manager.register_profile_listener("AAPL")
    assert "AAPL" in manager.profile_symbols

    # Unregister (symbol stays in profile_symbols for TTL-based cleanup)
    await manager.unregister_profile_listener("AAPL")
    assert "AAPL" in manager.profile_symbols  # NOT removed immediately

    # Simulate TTL expiry
    manager.profile_symbols["AAPL"] = time.monotonic() - PROFILE_SYMBOL_TTL_S - 10
    await manager._cleanup_stale_profiles()
    assert "AAPL" not in manager.profile_symbols

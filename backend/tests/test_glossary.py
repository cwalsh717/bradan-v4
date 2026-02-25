"""Tests for glossary seed service and GET /api/glossary endpoint.

All external APIs are mocked. Follows existing test patterns from
test_endpoints_phase2.py: mock get_session via dependency_overrides,
exercise endpoints through httpx.ASGITransport + AsyncClient.
"""

from unittest.mock import AsyncMock, MagicMock

from httpx import ASGITransport, AsyncClient

from app.main import app
from app.database import get_session
from app.services.glossary_service import GLOSSARY_ENTRIES, seed_glossary


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_CATEGORIES = {"dcf", "ratios", "profile"}


def _session_override(mock_db):
    """Return an async generator factory suitable for dependency_overrides."""

    async def _override():
        yield mock_db

    return _override


# ---------------------------------------------------------------------------
# 1. seed_glossary is idempotent
# ---------------------------------------------------------------------------


async def test_seed_glossary_idempotent():
    """Calling seed_glossary twice should not raise; it updates existing rows."""
    mock_session = AsyncMock()

    # First call: no existing entries
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = []
    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars_mock
    mock_session.execute = AsyncMock(return_value=result_mock)

    total = await seed_glossary(mock_session)
    assert total == len(GLOSSARY_ENTRIES)
    mock_session.commit.assert_awaited_once()

    # Second call: all entries already exist
    mock_session.reset_mock()
    existing_entries = []
    for term, display, tech_label, tooltip, category in GLOSSARY_ENTRIES:
        entry = MagicMock()
        entry.technical_term = term
        entry.display_label = display
        entry.technical_label = tech_label
        entry.tooltip = tooltip
        entry.category = category
        existing_entries.append(entry)

    scalars_mock2 = MagicMock()
    scalars_mock2.all.return_value = existing_entries
    result_mock2 = MagicMock()
    result_mock2.scalars.return_value = scalars_mock2
    mock_session.execute = AsyncMock(return_value=result_mock2)

    total2 = await seed_glossary(mock_session)
    assert total2 == len(GLOSSARY_ENTRIES)
    mock_session.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# 2. All entries have required fields
# ---------------------------------------------------------------------------


def test_all_entries_have_required_fields():
    """Every glossary entry must have all five required fields populated."""
    for term, display, tech_label, tooltip, category in GLOSSARY_ENTRIES:
        assert term, "Missing technical_term in entry"
        assert display, f"Missing display_label for {term}"
        assert tech_label, f"Missing technical_label for {term}"
        assert tooltip, f"Missing tooltip for {term}"
        assert category, f"Missing category for {term}"


# ---------------------------------------------------------------------------
# 3. Categories are valid
# ---------------------------------------------------------------------------


def test_categories_are_valid():
    """All glossary entries should belong to a known category."""
    for term, _, _, _, category in GLOSSARY_ENTRIES:
        assert category in VALID_CATEGORIES, (
            f"Entry '{term}' has invalid category '{category}'"
        )


# ---------------------------------------------------------------------------
# 4. Minimum entry count per category
# ---------------------------------------------------------------------------


def test_minimum_entry_counts():
    """Verify minimum counts: dcf >= 15, ratios >= 12, profile >= 4."""
    counts = {"dcf": 0, "ratios": 0, "profile": 0}
    for _, _, _, _, category in GLOSSARY_ENTRIES:
        counts[category] = counts.get(category, 0) + 1

    assert counts["dcf"] >= 15, f"Expected >= 15 dcf entries, got {counts['dcf']}"
    assert counts["ratios"] >= 12, (
        f"Expected >= 12 ratios entries, got {counts['ratios']}"
    )
    assert counts["profile"] >= 4, (
        f"Expected >= 4 profile entries, got {counts['profile']}"
    )


# ---------------------------------------------------------------------------
# 5. Total entry count >= 31
# ---------------------------------------------------------------------------


def test_total_entry_count():
    """At least 31 glossary entries should be defined."""
    assert len(GLOSSARY_ENTRIES) >= 31


# ---------------------------------------------------------------------------
# 6. GET /api/glossary returns entries
# ---------------------------------------------------------------------------


async def test_glossary_endpoint_returns_entries():
    """GET /api/glossary should return a list of glossary entries."""
    # Create mock glossary entries
    entry1 = MagicMock()
    entry1.technical_term = "wacc"
    entry1.display_label = "Weighted Average Cost of Capital"
    entry1.technical_label = "WACC"
    entry1.tooltip = "The blended rate a company must earn."
    entry1.category = "dcf"
    entry1.learn_more_url = None

    entry2 = MagicMock()
    entry2.technical_term = "pe_ratio"
    entry2.display_label = "Price-to-Earnings Ratio"
    entry2.technical_label = "P/E"
    entry2.tooltip = "Compares share price to earnings per share."
    entry2.category = "ratios"
    entry2.learn_more_url = None

    scalars_mock = MagicMock()
    scalars_mock.all.return_value = [entry1, entry2]
    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars_mock

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=result_mock)

    app.dependency_overrides[get_session] = _session_override(mock_db)

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get("/api/glossary")

        assert resp.status_code == 200
        body = resp.json()
        assert "data" in body
        data = body["data"]
        assert isinstance(data, list)
        assert len(data) == 2

        # Verify structure of entries
        assert data[0]["technical_term"] == "wacc"
        assert data[0]["display_label"] == "Weighted Average Cost of Capital"
        assert data[0]["technical_label"] == "WACC"
        assert data[0]["tooltip"] is not None
        assert data[0]["category"] == "dcf"
        assert "learn_more_url" in data[0]

        assert data[1]["technical_term"] == "pe_ratio"
        assert data[1]["category"] == "ratios"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 7. GET /api/glossary returns empty list when no entries
# ---------------------------------------------------------------------------


async def test_glossary_endpoint_empty():
    """GET /api/glossary should return an empty list when no entries exist."""
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = []
    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars_mock

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=result_mock)

    app.dependency_overrides[get_session] = _session_override(mock_db)

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get("/api/glossary")

        assert resp.status_code == 200
        body = resp.json()
        assert body["data"] == []
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 8. Unique technical terms
# ---------------------------------------------------------------------------


def test_unique_technical_terms():
    """All technical_term values should be unique across the glossary."""
    terms = [term for term, _, _, _, _ in GLOSSARY_ENTRIES]
    assert len(terms) == len(set(terms)), "Duplicate technical_term found"

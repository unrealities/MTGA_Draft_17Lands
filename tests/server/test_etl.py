import os
import time
import json
import pytest
import responses
import re
from datetime import datetime, timezone

from server.utils import APIClient
from server.main import get_scheduled_events
from server.extract import extract_scryfall_data, extract_scryfall_tags
from server.transform import transform_payload, parse_scryfall_types


@pytest.fixture
def api_client(tmp_path):
    # Instantiate the HTTP client
    client = APIClient()

    # Force the client to use an ephemeral temporary directory for this specific
    # test run, ignoring your real hard drive.
    client._cache_dir = str(tmp_path / ".cache")
    os.makedirs(client._cache_dir, exist_ok=True)

    return client


# ==============================================================================
# 1. CALENDAR-DRIVEN SCHEDULING TESTS
# ==============================================================================


def test_get_scheduled_events(tmp_path, monkeypatch):
    """Verify the calendar correctly filters active vs inactive events based on today's date."""

    # 1. Freeze time to exactly March 15, 2026
    class MockDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 3, 15, tzinfo=timezone.utc)

    monkeypatch.setattr("server.main.datetime", MockDatetime)

    # 2. Create a mock calendar.json
    cal_file = tmp_path / "calendar.json"
    cal_file.write_text(
        json.dumps(
            {
                "events": [
                    # Active (Started past, ends future)
                    {
                        "set_code": "TMNT",
                        "formats": ["PremierDraft"],
                        "start_date": "2026-03-01",
                        "end_date": "2026-03-31",
                    },
                    # Inactive (Starts in future)
                    {
                        "set_code": "BLB",
                        "formats": ["QuickDraft"],
                        "start_date": "2026-04-01",
                        "end_date": "2026-04-10",
                    },
                    # Inactive (Ended in past)
                    {
                        "set_code": "MAT",
                        "formats": ["TradDraft"],
                        "start_date": "2026-02-01",
                        "end_date": "2026-02-28",
                    },
                ]
            }
        )
    )

    active_sets = get_scheduled_events(str(cal_file))

    assert "TMNT" in active_sets
    assert "PremierDraft" in active_sets["TMNT"]["formats"]
    assert "BLB" not in active_sets
    assert "MAT" not in active_sets


# ==============================================================================
# 2. SCRYFALL CACHING ARCHITECTURE TESTS
# ==============================================================================


def test_scryfall_base_cards_permanent_cache(tmp_path, monkeypatch, api_client):
    """Verify that base cards load instantly from disk if the cache exists (0 API calls)."""
    monkeypatch.setattr("server.extract.SCRYFALL_CACHE_DIR", str(tmp_path))

    cache_file = tmp_path / "M10_cards.json"
    cache_file.write_text(json.dumps({"Lightning Bolt": {"name": "Lightning Bolt"}}))

    # We do NOT use @responses.activate here.
    # If the code tries to hit the API, it will raise an error, proving the cache works.
    cards = extract_scryfall_data(api_client, "M10")

    assert "Lightning Bolt" in cards
    assert len(cards) == 1


@responses.activate
def test_scryfall_tags_ttl_cache(tmp_path, monkeypatch, api_client):
    """Verify that tags load from cache if < 7 days old, and fetch from API if > 7 days old."""
    monkeypatch.setattr("server.extract.SCRYFALL_CACHE_DIR", str(tmp_path))

    cache_file = tmp_path / "M10_tags.json"
    cache_file.write_text(json.dumps({"Lightning Bolt": ["removal"]}))

    # --- SCENARIO A: File is 2 days old (Should use cache, skip API) ---
    monkeypatch.setattr("os.path.getmtime", lambda x: time.time() - (86400 * 2))

    tags = extract_scryfall_tags(api_client, "M10")
    assert tags["Lightning Bolt"] == ["removal"]
    assert len(responses.calls) == 0  # Proves no API calls were made

    # --- SCENARIO B: File is 8 days old (Should ignore cache, hit API) ---
    monkeypatch.setattr("os.path.getmtime", lambda x: time.time() - (86400 * 8))

    # Mock Scryfall Search API. Regex matches any tag query URL.
    responses.add(
        responses.GET,
        re.compile("https://api.scryfall.com/cards/search.*"),
        json={"data": [{"name": "New Shock"}], "next_page": None},
        status=200,
    )

    tags = extract_scryfall_tags(api_client, "M10")

    assert "New Shock" in tags
    assert len(responses.calls) > 0  # Proves API was called to refresh tags


def test_scryfall_skips_cube(api_client):
    """Verify that CUBE formats immediately return empty dicts to save processing/API calls."""
    cards = extract_scryfall_data(api_client, "CUBE")
    tags = extract_scryfall_tags(api_client, "CUBE")

    assert cards == {}
    assert tags == {}


# ==============================================================================
# 3. TRANSFORM & BUSINESS LOGIC TESTS
# ==============================================================================


def test_transform_payload_merging():
    """Verifies that Scryfall base data and 17Lands stats merge perfectly into the client payload."""
    scryfall_mock = {
        "Lightning Bolt": {
            "arena_ids": [123],
            "cmc": 1,
            "types": ["Instant"],
            "subtypes": [],
            "colors": ["R"],
            "color_identity": ["R"],
            "rarity": "Uncommon",
            "image": ["http://img"],
            "keywords": [],
            "oracle_text": "Lightning Bolt deals 3 damage to any target.",
            "mana_cost": "{R}",
        }
    }

    seventeenlands_mock = {
        "All Decks": {"Lightning Bolt": {"gihwr": 62.5, "alsa": 2.1, "samples": 5000}},
        "UR": {"Lightning Bolt": {"gihwr": 64.0, "alsa": 2.1, "samples": 1000}},
    }

    tags_mock = {"Lightning Bolt": ["removal", "burn"]}
    color_ratings_mock = {"All Decks": 52.1, "UR": 55.3}

    payload = transform_payload(
        "M10",
        "PremierDraft",
        scryfall_mock,
        seventeenlands_mock,
        tags_mock,
        color_ratings_mock,
        "2019-01-01",
        "2024-05-01",
        5000,
    )

    # Verify Header
    assert payload["meta"]["start_date"] == "2019-01-01"
    assert payload["meta"]["end_date"] == "2024-05-01"
    assert payload["meta"]["game_count"] == 5000

    # Verify Root Card Properties
    card = payload["card_ratings"]["123"]
    assert card["name"] == "Lightning Bolt"
    assert card["types"] == ["Instant"]
    assert card["tags"] == ["removal", "burn"]
    assert card["oracle_text"] == "Lightning Bolt deals 3 damage to any target."

    # Verify Archetype Embedding
    assert card["deck_colors"]["All Decks"]["gihwr"] == 62.5
    assert card["deck_colors"]["UR"]["gihwr"] == 64.0
    assert payload["color_ratings"]["UR"] == 55.3


def test_parse_scryfall_types():
    """Ensure we correctly strip supertypes and split tribal lines."""
    types, subtypes = parse_scryfall_types("Legendary Creature — Human Ninja")
    assert types == ["Creature"]
    assert subtypes == ["Human", "Ninja"]

    types, subtypes = parse_scryfall_types("Artifact — Equipment")
    assert types == ["Artifact"]
    assert subtypes == ["Equipment"]

    # Test Battle format
    types, subtypes = parse_scryfall_types("Battle — Siege")
    assert types == ["Battle"]
    assert subtypes == ["Siege"]


# ==============================================================================
# 4. API CLIENT & RESILIENCE TESTS
# ==============================================================================


@responses.activate
def test_respectful_get_retries_on_429(api_client, monkeypatch):
    """Verify that respectful_get strictly adheres to exponential backoff on HTTP 429."""
    url = "https://example.com/test_429"
    responses.add(responses.GET, url, status=429)
    responses.add(responses.GET, url, status=429)
    responses.add(responses.GET, url, json={"ok": True}, status=200)

    monkeypatch.setattr("time.sleep", lambda x: None)  # Bypass sleep for fast tests
    resp = api_client.respectful_get(url)

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    assert len(responses.calls) == 3


@responses.activate
def test_respectful_get_raises_after_max_retries(api_client, monkeypatch):
    """Verify that respectful_get permanently raises after exhausting maximum attempts."""
    url = "https://example.com/test_max_retries"
    for _ in range(5):
        responses.add(responses.GET, url, status=429)

    monkeypatch.setattr("time.sleep", lambda x: None)

    with pytest.raises(Exception, match="Max retries"):
        api_client.respectful_get(url)


@responses.activate
def test_respectful_get_allow_404(api_client):
    """Verify that allow_404=True smoothly returns the 404 response without crashing."""
    url = "https://example.com/test_404"
    responses.add(responses.GET, url, status=404)

    resp = api_client.respectful_get(url, allow_404=True)
    assert resp.status_code == 404

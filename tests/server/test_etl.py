"""
tests/server/test_etl.py
"""

import pytest
import responses
import json

from server.utils import APIClient
from server.extract import extract_active_events
from server.transform import transform_payload, parse_scryfall_types
from server.config import ARCHETYPES
from server.load import save_dataset, save_manifest


@pytest.fixture
def api_client():
    # Instantiate the HTTP client without making network calls
    return APIClient()


@responses.activate
def test_extract_active_events(api_client, monkeypatch):
    # Mock the 17Lands filter endpoint
    mock_filters = {
        "start_dates": {"OTJ": "2024-04-16T15:00:00Z", "MKM": "2024-02-06T00:00:00Z"},
        "formats_by_expansion": {
            "OTJ": ["PremierDraft", "TradDraft"],
            "MKM": ["PremierDraft"],
        },
    }

    responses.add(
        responses.GET,
        "https://www.17lands.com/data/filters",
        json=mock_filters,
        status=200,
    )

    # Bypass the time.sleep so our tests run instantly
    monkeypatch.setattr("time.sleep", lambda x: None)
    active_sets = extract_active_events(api_client)

    assert "OTJ" in active_sets
    assert "PremierDraft" in active_sets["OTJ"]
    assert "TradDraft" in active_sets["OTJ"]


def test_transform_payload_merging():
    """Verifies that Scryfall base data and 17Lands stats merge perfectly."""

    scryfall_mock = {
        "Lightning Bolt": {
            "arena_id": 123,
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

    # Call the standalone transform function
    payload = transform_payload(
        "M10",
        "PremierDraft",
        scryfall_mock,
        seventeenlands_mock,
        tags_mock,
        color_ratings_mock,
    )

    # Verify the output structure
    assert payload["meta"]["set"] == "M10"
    assert payload["meta"]["game_count"] == 5000

    card = payload["card_ratings"]["123"]
    assert card["name"] == "Lightning Bolt"
    assert card["types"] == ["Instant"]
    assert card["tags"] == ["removal", "burn"]
    assert card["keywords"] == []
    assert card["oracle_text"] == "Lightning Bolt deals 3 damage to any target."
    assert card["color_identity"] == ["R"]

    # Verify Archetype embedding
    assert card["deck_colors"]["All Decks"]["gihwr"] == 62.5
    assert card["deck_colors"]["UR"]["gihwr"] == 64.0

    # Verify real color ratings
    assert payload["color_ratings"]["UR"] == 55.3


def test_parse_scryfall_types():
    """Ensure we correctly strip 'Legendary' and split tribes."""
    type_line = "Legendary Creature — Human Ninja"
    types, subtypes = parse_scryfall_types(type_line)

    assert types == ["Creature"]
    assert subtypes == ["Human", "Ninja"]

    type_line_2 = "Artifact — Equipment"
    types, subtypes = parse_scryfall_types(type_line_2)
    assert types == ["Artifact"]
    assert subtypes == ["Equipment"]


@responses.activate
def test_respectful_get_retries_on_429(api_client, monkeypatch):
    """Verify that respectful_get retries on rate-limit (429) responses."""
    responses.add(
        responses.GET,
        "https://example.com/test",
        status=429,
    )
    responses.add(
        responses.GET,
        "https://example.com/test",
        status=429,
    )
    responses.add(
        responses.GET,
        "https://example.com/test",
        json={"ok": True},
        status=200,
    )

    monkeypatch.setattr("time.sleep", lambda x: None)
    resp = api_client.respectful_get("https://example.com/test")

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    assert len(responses.calls) == 3


@responses.activate
def test_respectful_get_raises_after_max_retries(api_client, monkeypatch):
    """Verify that respectful_get raises after exhausting retries."""
    for _ in range(5):
        responses.add(
            responses.GET,
            "https://example.com/test",
            status=429,
        )

    monkeypatch.setattr("time.sleep", lambda x: None)
    with pytest.raises(Exception, match="Max retries"):
        api_client.respectful_get("https://example.com/test")


@responses.activate
def test_respectful_get_allow_404(api_client):
    """Verify that allow_404=True returns the 404 response without raising."""
    responses.add(
        responses.GET,
        "https://example.com/test",
        status=404,
    )

    resp = api_client.respectful_get("https://example.com/test", allow_404=True)
    assert resp.status_code == 404

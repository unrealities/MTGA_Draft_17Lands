import pytest
from server.transform import transform_payload, parse_scryfall_types


def test_transform_payload_missing_games():
    payload = transform_payload(
        set_code="M10",
        draft_format="PremierDraft",
        scryfall_cards={},
        seventeenlands_data={
            "All Decks": {"Lightning Bolt": {"samples": 50, "gihwr": 60.0}}
        },
        card_tags={},
        color_ratings=None,
        start_date="2020-01-01",
        end_date="2020-02-01",
        total_games=0,
    )
    assert payload["meta"]["game_count"] == 50
    assert "UNKNOWN_LightningBolt" in payload["card_ratings"]


def test_transform_payload_basic_lands():
    scryfall_cards = {
        "Island": {
            "arena_ids": [1],
            "cmc": 0,
            "types": ["Land", "Basic"],
            "color_identity": ["U"],
        }
    }
    payload = transform_payload(
        set_code="M10",
        draft_format="PremierDraft",
        scryfall_cards=scryfall_cards,
        seventeenlands_data={},
        card_tags={},
        color_ratings=None,
        start_date="2020-01-01",
        end_date="2020-02-01",
        total_games=100,
    )
    assert "1" in payload["card_ratings"]
    card = payload["card_ratings"]["1"]
    assert card["name"] == "Island"
    assert card["deck_colors"]["All Decks"]["gihwr"] == 0.0


def test_parse_scryfall_types_edge():
    types, subtypes = parse_scryfall_types(None)
    assert types == []
    assert subtypes == []

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


def test_transform_payload_all_decks_fallback():
    """Verify that if 'All Decks' data exists but archetype data is missing, it creates zeroed templates."""
    from server.transform import transform_payload
    from server import config

    scryfall_cards = {
        "Testing Card": {
            "arena_ids": [999],
            "cmc": 1,
            "types": ["Instant"],
            "color_identity": ["U"],
        }
    }

    # 17Lands only has global stats, no archetype stats
    stats = {"All Decks": {"Testing Card": {"gihwr": 55.0, "alsa": 3.0}}}

    payload = transform_payload(
        "SET", "Draft", scryfall_cards, stats, {}, None, "2024", "2024", 500
    )

    card = payload["card_ratings"]["999"]

    # Assert All Decks exists
    assert card["deck_colors"]["All Decks"]["gihwr"] == 55.0

    # Assert all other config archetypes are initialized safely with 0.0
    for arch in config.ARCHETYPES:
        assert arch in card["deck_colors"]
        if arch != "All Decks":
            assert card["deck_colors"][arch]["gihwr"] == 0.0


def test_transform_payload_linked_face_type():
    """Verify data mappings (types, tags, rarity) fallback properly from Scryfall to 17Lands."""
    from server.transform import transform_payload

    scryfall_cards = {
        "Card A": {"arena_ids": [111], "rarity": "mythic", "image": ["imgA"]}
    }

    stats = {
        "All Decks": {
            "Card A": {"gihwr": 60.0},
            "Card B (No Scryfall Data)": {
                "gihwr": 50.0,
                "rarity": "rare",
                "17lands_images": ["imgB"],
                "arena_id": 222,
            },
        }
    }

    payload = transform_payload(
        "SET", "Draft", scryfall_cards, stats, {}, None, "2024", "2024", 500
    )

    card_a = payload["card_ratings"]["111"]
    assert card_a["rarity"] == "mythic"  # Took from scryfall
    assert card_a["image"] == ["imgA"]

    card_b = payload["card_ratings"]["222"]
    assert card_b["rarity"] == "rare"  # Fallback to 17Lands stat rarity
    assert card_b["image"] == ["imgB"]  # Fallback to 17Lands image

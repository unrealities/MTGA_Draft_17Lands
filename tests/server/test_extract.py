import pytest
from unittest.mock import MagicMock, patch
from server.extract import (
    extract_17lands_data,
    extract_color_ratings,
    extract_basic_lands,
)
from server import config


@pytest.fixture
def mock_client():
    return MagicMock()


def test_extract_17lands_data(mock_client):
    """Verifies that raw 17Lands data is parsed into strict percentage floats and captures image URLs."""

    mock_response = MagicMock()
    mock_response.json.return_value = [
        {
            "name": "Lightning Bolt",
            "mtga_id": 12345,
            "ever_drawn_win_rate": 0.6254,
            "opening_hand_win_rate": 0.591,
            "win_rate": 0.58,
            "drawn_improvement_win_rate": 0.045,
            "avg_seen": 2.1,
            "avg_pick": 2.0,
            "ever_drawn_game_count": 5000,
            "url": "/static/images/cards/bolt.jpg",
        }
    ]
    mock_client.respectful_get.return_value = mock_response

    # Act
    data = extract_17lands_data(
        client=mock_client,
        set_code="M10",
        draft_format="PremierDraft",
        valid_archetypes=["All Decks", "UR"],
        user_group="All",
        start_date="2020-01-01",
        end_date="2024-01-01",
    )

    # Assert
    assert "All Decks" in data
    assert "Lightning Bolt" in data["All Decks"]

    card_stats = data["All Decks"]["Lightning Bolt"]
    assert card_stats["arena_id"] == 12345
    assert card_stats["gihwr"] == 62.54  # 0.6254 * 100
    assert card_stats["ohwr"] == 59.1  # 0.591 * 100
    assert card_stats["iwd"] == 4.5  # 0.045 * 100
    assert card_stats["samples"] == 5000
    assert "17lands_images" in card_stats
    assert (
        card_stats["17lands_images"][0]
        == "https://www.17lands.com/static/images/cards/bolt.jpg"
    )


def test_extract_color_ratings(mock_client):
    """Verifies that color ratings normalize color strings and filter out low sample sizes."""

    # Temporarily lower threshold for easy testing
    config.MIN_GAMES_THRESHOLD = 500

    mock_response = MagicMock()
    mock_response.json.return_value = [
        {"is_summary": True, "color_name": "All Decks", "games": 50000},
        {"short_name": "GW", "games": 1000, "wins": 550},  # Valid, but backwards name
        {"short_name": "UR", "games": 100, "wins": 50},  # Below threshold (100 < 500)
    ]
    mock_client.respectful_get.return_value = mock_response

    ratings, games_played, total_games = extract_color_ratings(
        mock_client, "M10", "PremierDraft", "All", "2020-01-01", "2024-01-01"
    )

    # Assertions
    assert total_games == 50000
    assert "WG" in ratings  # Normalized from GW -> WG
    assert ratings["WG"] == 55.0  # (550/1000) * 100
    assert "UR" not in ratings  # Excluded due to low game count


@patch("server.extract.os.path.exists", return_value=False)
@patch("server.extract.open")
def test_extract_basic_lands_api_call(mock_open, mock_exists, mock_client):
    """Verifies Scryfall fallback for MTG Arena Basic Lands."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": [
            {
                "name": "Island",
                "arena_id": 999,
                "type_line": "Basic Land — Island",
                "colors": [],
                "mana_cost": "",
            },
            {"name": "Random Card", "arena_id": 123},  # Should be ignored
        ],
        "next_page": None,
    }
    mock_client.respectful_get.return_value = mock_response

    lands = extract_basic_lands(mock_client)

    assert "Island" in lands
    assert lands["Island"]["arena_ids"] == [999]
    assert "Random Card" not in lands


def test_extract_scryfall_data_dfc_mapping(mock_client):
    """Verifies that DFCs map both their full name and front name to the card data."""
    from server.extract import extract_scryfall_data

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": [
            {
                "name": "Okiba Reckoner Raid // Nezumi Road Captain",
                "arena_id": 79544,
                "cmc": 1.0,
                "type_line": "Enchantment — Saga // Enchantment Creature — Rat Rogue",
                "mana_cost": "{B}",
            }
        ],
        "next_page": None,
    }
    mock_client.respectful_get.return_value = mock_response

    # Act
    cards = extract_scryfall_data(mock_client, "NEO")

    # Assert
    assert "Okiba Reckoner Raid // Nezumi Road Captain" in cards
    assert "Okiba Reckoner Raid" in cards

    # Both keys should point to the exact same mapped data
    assert cards["Okiba Reckoner Raid"]["arena_ids"] == [79544]
    assert cards["Okiba Reckoner Raid"]["cmc"] == 1
    assert "Creature" in cards["Okiba Reckoner Raid"]["types"]


def test_extract_scryfall_adventure_and_supertypes(mock_client):
    """Verifies that Adventures alias both faces and preserve Super Types."""
    from server.extract import extract_scryfall_data

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": [
            {
                "name": "Brazen Borrower // Petty Theft",
                "arena_id": 70186,
                "cmc": 3.0,
                "type_line": "Legendary Creature — Faerie Rogue // Instant — Adventure",
                "mana_cost": "{1}{U}{U}",
            }
        ],
        "next_page": None,
    }
    mock_client.respectful_get.return_value = mock_response

    # Act
    cards = extract_scryfall_data(mock_client, "ELD")

    # Assert aliasing
    assert "Brazen Borrower // Petty Theft" in cards
    assert "Brazen Borrower" in cards
    assert "Petty Theft" in cards  # The Adventure half is perfectly searchable

    # Assert Super Types are preserved
    primary_card = cards["Brazen Borrower"]
    assert "Creature" in primary_card["types"]
    assert "Instant" in primary_card["types"]
    assert "Adventure" in primary_card["subtypes"]

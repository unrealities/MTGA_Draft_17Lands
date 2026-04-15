import pytest
import json
import os
from unittest.mock import patch, mock_open, MagicMock
from src.seventeenlands import Seventeenlands
from src import constants

# --- Fixtures ---


@pytest.fixture
def mock_session():
    """Creates a mock session with a pre-configured response."""
    session = MagicMock()
    response = MagicMock()
    # Default to raising HTTPError for bad status codes
    response.raise_for_status = MagicMock()
    session.get.return_value = response
    return session, response


@pytest.fixture
def seventeenlands(mock_session):
    """Fixture to create a Seventeenlands instance with a mocked session."""
    session, _ = mock_session
    sl = Seventeenlands()
    sl.session = session
    return sl


# --- Test Cases ---


def test_process_card_ratings(seventeenlands):
    """
    Tests the processing of raw JSON data from the 17Lands API into the internal structure.
    """
    # Arrange: Mock 17Lands API response
    mock_api_data = [
        {
            "name": "Sol Ring",
            "url": "/static/images/cards/s_123.jpg",
            "ever_drawn_win_rate": 0.65,
            "avg_seen": 1.1,
            "drawn_improvement_win_rate": 0.1,
            "drawn_game_count": 1000,
        },
        {
            "name": "Island",
            "url": "https://c1.scryfall.com/island.jpg",
            "ever_drawn_win_rate": None,  # Test null value
            "avg_seen": 9.5,
            "drawn_improvement_win_rate": -0.05,
            "drawn_game_count": 500,
        },
    ]
    color = "All Decks"
    card_data = {}

    # Act
    seventeenlands.process_card_ratings(color, mock_api_data, card_data)

    # Assert
    assert "Sol Ring" in card_data
    assert "Island" in card_data

    sol_ring_data = card_data["Sol Ring"]
    # Verify image URL expansion logic
    assert sol_ring_data[constants.DATA_SECTION_IMAGES] == [
        "https://www.17lands.com/static/images/cards/s_123.jpg"
    ]

    # Check that ratings were appended correctly
    # Structure: [{'All Decks': {...}}]
    sol_ring_ratings = sol_ring_data[constants.DATA_SECTION_RATINGS][0][color]
    assert (
        sol_ring_ratings[constants.DATA_FIELD_GIHWR] == 65.0
    )  # Check percentage conversion
    assert sol_ring_ratings[constants.DATA_FIELD_ALSA] == 1.1
    assert (
        sol_ring_ratings[constants.DATA_FIELD_IWD] == 10.0
    )  # Check percentage conversion
    assert sol_ring_ratings[constants.DATA_FIELD_NGD] == 1000

    island_ratings = card_data["Island"][constants.DATA_SECTION_RATINGS][0][color]
    assert island_ratings[constants.DATA_FIELD_GIHWR] == 0.0  # Check null handling
    assert island_ratings[constants.DATA_FIELD_IWD] == -5.0  # Check negative percentage


def test_build_card_ratings_url(seventeenlands):
    """
    Tests the URL construction for fetching card ratings.
    """
    # Arrange
    set_code = "TLA"
    draft = "PremierDraft"
    start_date = "2023-01-01"
    end_date = "2025-11-28"
    user_group = constants.LIMITED_USER_GROUP_ALL
    color = constants.FILTER_OPTION_ALL_DECKS

    # Act
    url = seventeenlands.build_card_ratings_url(
        set_code, draft, start_date, end_date, user_group, color
    )

    # Assert
    expected_url = (
        "https://www.17lands.com/card_ratings/data?expansion=TLA"
        "&format=PremierDraft&start_date=2023-01-01&end_date=2025-11-28"
    )
    assert url == expected_url


def test_download_card_ratings(mock_session, seventeenlands):
    """
    Tests the download_card_ratings function to ensure it fetches and processes data correctly.
    """
    session, response = mock_session
    response.json.return_value = [
        {
            "name": "Test Card",
            "url": "/static/images/cards/test_card.jpg",
            "ever_drawn_win_rate": 0.6,
            "avg_seen": 2.5,
            "drawn_improvement_win_rate": 0.05,
            "drawn_game_count": 1000,
        }
    ]

    set_code = "TLA"
    draft = "PremierDraft"
    start_date = "2023-01-01"
    end_date = "2025-11-28"
    user_group = constants.LIMITED_USER_GROUP_ALL
    color = constants.FILTER_OPTION_ALL_DECKS
    card_data = {}

    # Act
    seventeenlands.download_card_ratings(
        set_code, color, draft, start_date, end_date, user_group, card_data
    )

    # Assert
    assert "Test Card" in card_data
    assert card_data["Test Card"][constants.DATA_SECTION_IMAGES] == [
        "https://www.17lands.com/static/images/cards/test_card.jpg"
    ]
    assert len(card_data["Test Card"][constants.DATA_SECTION_RATINGS]) == 1
    session.get.assert_called_once()


def test_download_color_ratings(mock_session, seventeenlands):
    """
    Tests the download_color_ratings function to ensure it fetches and processes color ratings correctly.
    """
    session, response = mock_session
    response.json.return_value = [
        {
            "short_name": "W",
            "is_summary": False,
            "games": 6000,
            "wins": 3000,
        },
        {
            "color_name": "All Decks",
            "is_summary": True,
            "games": 10000,
        },
    ]

    set_code = "TLA"
    draft = "PremierDraft"
    start_date = "2023-01-01"
    end_date = "2025-11-28"
    user_group = constants.LIMITED_USER_GROUP_ALL

    # Act
    color_ratings, game_count = seventeenlands.download_color_ratings(
        set_code, draft, start_date, end_date, user_group
    )

    # Assert
    assert color_ratings["W"] == 50.0  # 3000 wins out of 6000 games
    assert game_count == 10000
    session.get.assert_called_once()


def test_seventeenlands_color_ratings_normalization(mock_session, seventeenlands):
    """
    Verify that download_color_ratings normalizes keys from the API response.
    If the API returns "GW" but the app expects "WG", this method should handle it.
    """
    session, response = mock_session
    # Mock API response with non-standard order ("GW" instead of "WG")
    response.json.return_value = [
        {"short_name": "GW", "is_summary": False, "games": 6000, "wins": 3000},
        {"color_name": "All Decks", "is_summary": True, "games": 10000},
    ]

    # We pass a filter that includes the *Normalized* key "WG"
    # The function should be able to map "GW" from API to "WG"
    ratings, game_count = seventeenlands.download_color_ratings(
        "SET", "Draft", "Start", "End", "User", color_filter=["WG"]
    )

    # Check that the key in the returned dictionary is normalized to "WG"
    assert "WG" in ratings
    assert ratings["WG"] == 50.0
    assert "GW" not in ratings  # Should not contain the raw key if it was normalized


def test_process_color_ratings_fallback_logic(seventeenlands):
    """
    Verify that _process_color_ratings handles entries missing 'short_name'
    by parsing 'color_name' (e.g. "(UB)") as a fallback.
    """
    # Mock data where 'short_name' is missing (older API style or edge case)
    mock_api_data = [
        {
            "color_name": "Dimir (UB)",
            # "short_name": "UB", <--- MISSING
            "is_summary": False,
            "games": 6000,
            "wins": 3000,
        },
        {
            "color_name": "Simic (GU)",  # Non-standard order in name
            "short_name": "",  # Empty string
            "is_summary": False,
            "games": 10000,
            "wins": 6000,
        },
    ]

    ratings, game_count = seventeenlands._process_color_ratings(mock_api_data, None)

    # "UB" extracted from "Dimir (UB)"
    assert "UB" in ratings
    assert ratings["UB"] == 50.0

    # "GU" extracted from "Simic (GU)" and normalized to "UG"
    assert "UG" in ratings
    assert ratings["UG"] == 60.0


def test_get_draft_record_success(mock_session, seventeenlands):
    """Verify that a valid 17Lands draft record is retrieved and parsed."""
    session, response = mock_session
    response.status_code = 200
    response.json.return_value = {"wins": 7, "losses": 2}

    # Act
    record = seventeenlands.get_draft_record("draft-uuid-1234")

    # Assert
    assert record is not None
    assert record["wins"] == 7
    assert record["url"] == "https://www.17lands.com/draft/draftuuid1234"

    # Verify UUID formatting (hyphens stripped)
    session.get.assert_called_once()
    called_url = session.get.call_args[0][0]
    assert "draftuuid1234" in called_url


def test_get_draft_record_not_found(mock_session, seventeenlands):
    """Verify graceful handling when 17Lands doesn't track the draft."""
    session, response = mock_session
    response.status_code = 200
    response.json.return_value = {}  # Missing 'wins' key

    record = seventeenlands.get_draft_record("draft-uuid-1234")
    assert record is None


@patch("src.seventeenlands.is_cache_stale")
def test_fetch_archetype_with_cache_hit(mock_stale, seventeenlands, tmp_path):
    """Verify that a valid cache completely bypasses the network call."""
    mock_stale.return_value = False

    # Override CACHE_DIR to our tmp_path
    seventeenlands.CACHE_DIR = str(tmp_path)
    cache_path = tmp_path / "otj_premierdraft_2024-01-01_2024-02-01_all_all.json"
    cache_path.write_text(json.dumps([{"name": "Cached Card"}]))

    # Act
    data, from_cache = seventeenlands._fetch_archetype_with_cache(
        "OTJ", "PremierDraft", "2024-01-01", "2024-02-01", "All", "All"
    )

    # Assert
    assert from_cache is True
    assert data[0]["name"] == "Cached Card"
    assert seventeenlands.session.get.call_count == 0  # No network hit!


@patch("src.seventeenlands.is_cache_stale")
def test_fetch_archetype_with_cache_miss_writes_to_disk(
    mock_stale, mock_session, seventeenlands, tmp_path
):
    """Verify that a cache miss hits the network and safely writes a new cache file."""
    mock_stale.return_value = True
    session, response = mock_session
    response.json.return_value = [{"name": "Network Card"}]

    seventeenlands.CACHE_DIR = str(tmp_path)

    # Act
    data, from_cache = seventeenlands._fetch_archetype_with_cache(
        "OTJ", "PremierDraft", "2024-01-01", "2024-02-01", "All", "All"
    )

    # Assert
    assert from_cache is False
    assert data[0]["name"] == "Network Card"
    assert session.get.call_count == 1

    # Verify the cache file was actually created by the method
    cache_path = tmp_path / "otj_premierdraft_2024-01-01_2024-02-01_all_all.json"
    assert cache_path.exists()

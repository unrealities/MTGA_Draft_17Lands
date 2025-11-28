import pytest
from unittest.mock import patch, MagicMock
from src.seventeenlands import Seventeenlands
from src import constants

# --- Fixtures ---

@pytest.fixture
def seventeenlands():
    """Fixture to create a Seventeenlands instance for testing."""
    return Seventeenlands()

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
            "ever_drawn_win_rate": None, # Test null value
            "avg_seen": 9.5,
            "drawn_improvement_win_rate": -0.05,
            "drawn_game_count": 500,
        }
    ]
    color = "All Decks"
    card_data = {}

    # Act
    seventeenlands.process_card_ratings(color, mock_api_data, card_data)
    
    # Assert
    assert "Sol Ring" in card_data
    assert "Island" in card_data
    
    sol_ring_data = card_data["Sol Ring"]
    assert sol_ring_data[constants.DATA_SECTION_IMAGES] == ["https://www.17lands.com/static/images/cards/s_123.jpg"]
    
    sol_ring_ratings = sol_ring_data[constants.DATA_SECTION_RATINGS][0][color]
    assert sol_ring_ratings[constants.DATA_FIELD_GIHWR] == 65.0  # Check percentage conversion
    assert sol_ring_ratings[constants.DATA_FIELD_ALSA] == 1.1
    assert sol_ring_ratings[constants.DATA_FIELD_IWD] == 10.0 # Check percentage conversion
    assert sol_ring_ratings[constants.DATA_FIELD_NGD] == 1000

    island_ratings = card_data["Island"][constants.DATA_SECTION_RATINGS][0][color]
    assert island_ratings[constants.DATA_FIELD_GIHWR] == 0.0  # Check null handling
    assert island_ratings[constants.DATA_FIELD_IWD] == -5.0 # Check negative percentage

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
    url = seventeenlands.build_card_ratings_url(set_code, draft, start_date, end_date, user_group, color)

    # Assert
    expected_url = (
        "https://www.17lands.com/card_ratings/data?expansion=TLA"
        "&format=PremierDraft&start_date=2023-01-01&end_date=2025-11-28"
    )
    assert url == expected_url


@patch("src.seventeenlands.requests.get")
def test_download_card_ratings(mock_get, seventeenlands):
    """
    Tests the download_card_ratings function to ensure it fetches and processes data correctly.
    """
    # Arrange
    mock_response = MagicMock()
    mock_response.json.return_value = [
        {
            "name": "Test Card",
            "url": "/static/images/cards/test_card.jpg",
            "ever_drawn_win_rate": 0.6,
            "avg_seen": 2.5,
            "drawn_improvement_win_rate": 0.05,
            "drawn_game_count": 1000,
        }
    ]
    mock_get.return_value = mock_response

    set_code = "TLA"
    draft = "PremierDraft"
    start_date = "2023-01-01"
    end_date = "2025-11-28"
    user_group = constants.LIMITED_USER_GROUP_ALL
    color = constants.FILTER_OPTION_ALL_DECKS
    card_data = {}

    # Act
    seventeenlands.download_card_ratings(set_code, color, draft, start_date, end_date, user_group, card_data)

    # Assert
    assert "Test Card" in card_data
    assert card_data["Test Card"][constants.DATA_SECTION_IMAGES] == ["https://www.17lands.com/static/images/cards/test_card.jpg"]
    assert len(card_data["Test Card"][constants.DATA_SECTION_RATINGS]) == 1
    mock_get.assert_called_once()


@patch("src.seventeenlands.requests.get")
def test_download_color_ratings(mock_get, seventeenlands):
    """
    Tests the download_color_ratings function to ensure it fetches and processes color ratings correctly.
    """
    # Arrange
    mock_response = MagicMock()
    mock_response.json.return_value = [
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
        }
    ]
    mock_get.return_value = mock_response

    set_code = "TLA"
    draft = "PremierDraft"
    start_date = "2023-01-01"
    end_date = "2025-11-28"
    user_group = constants.LIMITED_USER_GROUP_ALL

    # Act
    color_ratings, game_count = seventeenlands.download_color_ratings(set_code, draft, start_date, end_date, user_group)

    # Assert
    assert color_ratings["W"] == 50.0  # 3000 wins out of 6000 games
    assert game_count == 10000
    mock_get.assert_called_once()
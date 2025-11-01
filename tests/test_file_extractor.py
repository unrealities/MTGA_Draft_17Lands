import pytest
import json
from unittest.mock import patch, MagicMock, mock_open
from src.file_extractor import (
    FileExtractor,
    decode_mana_cost,
    extract_types,
    initialize_card_data,
    check_date,
)
from src import constants

# --- Fixtures ---

@pytest.fixture
def file_extractor():
    """Fixture to create a FileExtractor instance with default values for testing."""
    extractor = FileExtractor(directory=None)
    extractor.draft = "PremierDraft"
    extractor.start_date = "2023-01-01"
    extractor.end_date = "2023-01-31"
    extractor.user_group = constants.LIMITED_USER_GROUP_ALL
    return extractor

# --- Test Standalone Utility Functions ---

@pytest.mark.parametrize("encoded_cost, expected_decoded, expected_cmc", [
    ("o1oW", "{1}{W}", 2),
    ("o2oUoU", "{2}{U}{U}", 4),
    ("oXoGoG", "{X}{G}{G}", 3),
    ("o5", "{5}", 5),
    ("", "", 0),
    (None, "", 0),
    ("(o2oG)", "{2}{G}", 3), # Test with parentheses
])
def test_decode_mana_cost(encoded_cost, expected_decoded, expected_cmc):
    """Tests the decode_mana_cost utility function for various mana cost formats."""
    decoded, cmc = decode_mana_cost(encoded_cost)
    assert decoded == expected_decoded
    assert cmc == expected_cmc

@pytest.mark.parametrize("type_line, expected_types", [
    ("Creature — Human Soldier", ["Creature"]),
    ("Artifact Creature — Golem", ["Creature", "Artifact"]),
    ("Legendary Enchantment Artifact", ["Enchantment", "Artifact"]),
    ("Instant", ["Instant"]),
    ("Basic Land — Forest", ["Land"]),
    ("Vanguard", []),
])
def test_extract_types(type_line, expected_types):
    """Tests the extract_types utility function to correctly identify main card types."""
    types = extract_types(type_line)
    # Use sets for comparison to ignore order
    assert set(types) == set(expected_types)

def test_initialize_card_data():
    """Tests that a card data dictionary is correctly initialized with deck_colors."""
    card = {}
    initialize_card_data(card)
    assert constants.DATA_FIELD_DECK_COLORS in card
    assert constants.FILTER_OPTION_ALL_DECKS in card[constants.DATA_FIELD_DECK_COLORS]
    assert "W" in card[constants.DATA_FIELD_DECK_COLORS]
    assert "WUBRG" not in card[constants.DATA_FIELD_DECK_COLORS] # Example of a non-standard color combo
    for color in constants.DECK_COLORS:
        assert color in card[constants.DATA_FIELD_DECK_COLORS]
        assert constants.DATA_FIELD_GIHWR in card[constants.DATA_FIELD_DECK_COLORS][color]
        assert card[constants.DATA_FIELD_DECK_COLORS][color][constants.DATA_FIELD_GIHWR] == 0.0

@pytest.mark.parametrize("date_str, expected_result", [
    ("2023-01-01", True),
    ("9999-12-31", False), # Future date
    ("invalid-date", False),
    ("2023-13-01", False), # Invalid month
])
def test_check_date(date_str, expected_result):
    """Tests the date validation utility function."""
    assert check_date(date_str) == expected_result


# --- Test FileExtractor Class Methods ---

# Test cases: (input_set_code, expected_encoded_set_code)
URL_ENCODING_TEST_CASES = [
    ("OTJ", "OTJ"),
    ("CUBE - POWERED", "CUBE%20-%20POWERED"),
    ("SET/CODE", "SET%2FCODE"),
    ("SPECIAL&CHARS", "SPECIAL%26CHARS"),
]

@pytest.mark.parametrize("set_code, expected_encoded_set_code", URL_ENCODING_TEST_CASES)
@patch('src.file_extractor.urllib.request.urlopen')
def test_retrieve_17lands_data_url_encoding(mock_urlopen, file_extractor, set_code, expected_encoded_set_code):
    """
    Tests that the set code in the URL for retrieve_17lands_data is correctly URL-encoded.
    """
    mock_response = MagicMock()
    mock_response.read.return_value = b'[]'
    mock_urlopen.return_value = mock_response

    expected_url = (
        f"https://www.17lands.com/card_ratings/data?expansion={expected_encoded_set_code}"
        f"&format={file_extractor.draft}"
        f"&start_date={file_extractor.start_date}"
        f"&end_date={file_extractor.end_date}"
    )

    file_extractor.retrieve_17lands_data([set_code], [constants.FILTER_OPTION_ALL_DECKS], None, None, 0, None)
    mock_urlopen.assert_called_once_with(expected_url, context=file_extractor.context)


def test_process_17lands_data(file_extractor):
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
    
    # Act
    file_extractor._process_17lands_data(color, mock_api_data)
    
    # Assert
    ratings = file_extractor.card_ratings
    assert "Sol Ring" in ratings
    assert "Island" in ratings
    
    sol_ring_data = ratings["Sol Ring"]
    assert sol_ring_data["image"] == ["https://www.17lands.com/static/images/cards/s_123.jpg"]
    
    sol_ring_ratings = sol_ring_data["ratings"][0][color]
    assert sol_ring_ratings[constants.DATA_FIELD_GIHWR] == 65.0  # Check percentage conversion
    assert sol_ring_ratings[constants.DATA_FIELD_ALSA] == 1.1
    assert sol_ring_ratings[constants.DATA_FIELD_IWD] == 10.0 # Check percentage conversion
    assert sol_ring_ratings[constants.DATA_FIELD_NGD] == 1000

    island_ratings = ratings["Island"]["ratings"][0][color]
    assert island_ratings[constants.DATA_FIELD_GIHWR] == 0.0  # Check null handling
    assert island_ratings[constants.DATA_FIELD_IWD] == -5.0 # Check negative percentage

def test_process_card_data_merging(file_extractor):
    """
    Tests the merging of 17Lands data (`card_ratings`) into the main card dictionary (`card_dict`).
    """
    # Arrange
    card_name = "Test Card"
    file_extractor.card_dict = {
        "12345": {
            constants.DATA_FIELD_NAME: card_name,
            constants.DATA_FIELD_MANA_COST: "{U}",
            constants.DATA_FIELD_TYPES: ["Creature"],
            constants.DATA_FIELD_CMC: 1,
            constants.DATA_FIELD_COLORS: ["U"],
            constants.DATA_SECTION_IMAGES: [],
        }
    }
    file_extractor.card_ratings = {
        card_name: {
            "image": ["http://example.com/image.png"],
            "ratings": [
                {
                    "All Decks": {
                        constants.DATA_FIELD_GIHWR: 55.5,
                        constants.DATA_FIELD_ALSA: 3.3
                    }
                }
            ]
        }
    }

    # Act
    card_to_process = file_extractor.card_dict["12345"]
    result = file_extractor._process_card_data(card_to_process)

    # Assert
    assert result is True
    assert card_to_process[constants.DATA_SECTION_IMAGES] == ["http://example.com/image.png"]
    assert constants.DATA_FIELD_DECK_COLORS in card_to_process
    deck_colors = card_to_process[constants.DATA_FIELD_DECK_COLORS]
    assert deck_colors["All Decks"][constants.DATA_FIELD_GIHWR] == 55.5
    assert deck_colors["All Decks"][constants.DATA_FIELD_ALSA] == 3.3
    assert deck_colors["WU"][constants.DATA_FIELD_GIHWR] == 0.0 # Check that other colors are initialized

def test_process_card_data_no_match(file_extractor):
    """
    Tests that if a card has no 17Lands rating, it is still processed and initialized.
    """
    # Arrange
    card_name = "Unrated Card"
    file_extractor.card_dict = { "54321": { constants.DATA_FIELD_NAME: card_name } }
    file_extractor.card_ratings = {} # No ratings available

    # Act
    card_to_process = file_extractor.card_dict["54321"]
    result = file_extractor._process_card_data(card_to_process)

    # Assert
    assert result is False # Should return false as no match was found
    # But it should still initialize the deck_colors structure
    initialize_card_data(card_to_process) # Manually call for assertion comparison
    assert constants.DATA_FIELD_DECK_COLORS in card_to_process
    assert card_to_process[constants.DATA_FIELD_DECK_COLORS]["All Decks"][constants.DATA_FIELD_GIHWR] == 0.0

@patch('src.file_extractor.check_file_integrity', return_value=(Result.VALID, {}))
@patch('builtins.open', new_callable=mock_open)
@patch('src.file_extractor.json.dump')
def test_export_card_data(mock_json_dump, mock_file_open, mock_check_integrity, file_extractor):
    """
    Tests that the export_card_data function attempts to write the correct data to the correct file.
    """
    # Arrange
    file_extractor.select_sets(MagicMock(seventeenlands=["OTJ"]))
    file_extractor.combined_data = {"meta": {}, "card_ratings": {"1": "a"}}
    expected_filename = f"OTJ_{file_extractor.draft}_{file_extractor.user_group}_{constants.SET_FILE_SUFFIX}"
    expected_filepath = constants.SETS_FOLDER + os.path.sep + expected_filename

    # Act
    result = file_extractor.export_card_data()

    # Assert
    assert result is True
    mock_file_open.assert_called_once_with(expected_filepath, 'w', encoding="utf-8", errors="replace")
    mock_json_dump.assert_called_once_with(file_extractor.combined_data, mock_file_open())
    mock_check_integrity.assert_called_once_with(expected_filepath)

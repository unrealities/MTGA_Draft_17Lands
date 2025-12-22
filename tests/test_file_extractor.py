import pytest
import json
import os
from unittest.mock import patch, MagicMock, mock_open
from src.file_extractor import (
    FileExtractor,
    decode_mana_cost,
    extract_types,
    initialize_card_data,
    check_date,
)
from src import constants
from src.utils import Result, normalize_color_string
from src.constants import (
    COLOR_WIN_RATE_GAME_COUNT_THRESHOLD_DEFAULT,
    DECK_COLORS,
)


@pytest.mark.parametrize(
    "encoded_cost, expected_decoded, expected_cmc",
    [
        ("o1oW", "{1}{W}", 2),
        ("o2oUoU", "{2}{U}{U}", 4),
        ("oXoGoG", "{X}{G}{G}", 3),
        ("o5", "{5}", 5),
        ("", "", 0),
        (None, "", 0),
        ("(o2oG)", "{2}{G}", 3),  # Test with parentheses
    ],
)
def test_decode_mana_cost(encoded_cost, expected_decoded, expected_cmc):
    """Tests the decode_mana_cost utility function for various mana cost formats."""
    decoded, cmc = decode_mana_cost(encoded_cost)
    assert decoded == expected_decoded
    assert cmc == expected_cmc


@pytest.mark.parametrize(
    "type_line, expected_types",
    [
        ("Creature — Human Soldier", ["Creature"]),
        ("Artifact Creature — Golem", ["Creature", "Artifact"]),
        ("Legendary Enchantment Artifact", ["Enchantment", "Artifact"]),
        ("Instant", ["Instant"]),
        ("Basic Land — Forest", ["Land"]),
        ("Vanguard", []),
    ],
)
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
    assert "WUBRG" in card[constants.DATA_FIELD_DECK_COLORS]
    for color in constants.DECK_COLORS:
        assert color in card[constants.DATA_FIELD_DECK_COLORS]
        assert (
            constants.DATA_FIELD_GIHWR in card[constants.DATA_FIELD_DECK_COLORS][color]
        )
        assert (
            card[constants.DATA_FIELD_DECK_COLORS][color][constants.DATA_FIELD_GIHWR]
            == 0.0
        )


@pytest.mark.parametrize(
    "date_str, expected_result",
    [
        ("2023-01-01", True),
        ("9999-12-31", False),  # Future date
        ("invalid-date", False),
        ("2023-13-01", False),  # Invalid month
    ],
)
def test_check_date(date_str, expected_result):
    """Tests the date validation utility function."""
    assert check_date(date_str) == expected_result


def test_initialize_card_data_keys_normalized():
    """
    Verify that initialize_card_data creates keys that match the normalized format.
    This prevents the 'missing W' bug from reappearing.
    """
    card_data = {}
    initialize_card_data(card_data)

    deck_colors_keys = card_data[constants.DATA_FIELD_DECK_COLORS].keys()

    for color in DECK_COLORS:
        # The keys in the initialized data must match the normalized version of the constants
        normalized_color = normalize_color_string(color)
        assert normalized_color in deck_colors_keys


@pytest.fixture
def file_extractor():
    """Fixture to create a FileExtractor instance with default values for testing."""
    # Mock UI dependencies for the constructor
    mock_progress = MagicMock()
    mock_status = MagicMock()
    mock_ui = MagicMock()

    extractor = FileExtractor(
        directory=None, progress=mock_progress, status=mock_status, ui=mock_ui
    )

    # Set default attributes usually set by UI interaction
    extractor.draft = "PremierDraft"
    extractor.start_date = "2023-01-01"
    extractor.end_date = "2023-01-31"
    extractor.user_group = constants.LIMITED_USER_GROUP_ALL

    return extractor


@patch("src.file_extractor.Seventeenlands")
def test_retrieve_17lands_color_ratings_passes_threshold(
    mock_seventeenlands_cls, file_extractor
):
    """
    Verify that FileExtractor passes its configured threshold to the Seventeenlands client.
    """
    mock_sl_instance = mock_seventeenlands_cls.return_value
    mock_sl_instance.download_color_ratings.return_value = ({}, 0)

    # Setup extractor with a custom threshold
    custom_threshold = 1234
    file_extractor.threshold = custom_threshold

    # Mock necessary attributes
    file_extractor.selected_sets = MagicMock()
    file_extractor.selected_sets.seventeenlands = ["SET"]

    # Run
    file_extractor.retrieve_17lands_color_ratings()

    # Verify call
    mock_sl_instance.download_color_ratings.assert_called_once()
    call_kwargs = mock_sl_instance.download_color_ratings.call_args.kwargs
    assert call_kwargs["threshold"] == custom_threshold


def test_file_extractor_default_threshold():
    """Verify FileExtractor defaults to the constant if no threshold is provided."""
    extractor = FileExtractor(None, None, None, None)
    assert extractor.threshold == COLOR_WIN_RATE_GAME_COUNT_THRESHOLD_DEFAULT

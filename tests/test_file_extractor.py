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
from src.utils import Result

# --- Fixtures ---

# --- Test Standalone Utility Functions ---


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


# --- Test FileExtractor Class Methods ---

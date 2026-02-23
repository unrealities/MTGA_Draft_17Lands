"""
tests/test_deck_builder.py
High-impact test targeting the V4 Deck Suggester and Holistic Scoring engine.
"""

import pytest
from unittest.mock import MagicMock
from src.card_logic import suggest_deck, calculate_dynamic_mana_base, count_fixing
from src.configuration import Configuration


@pytest.fixture
def mock_metrics():
    metrics = MagicMock()
    # Mocking the global average to 55.0% and Standard Deviation to 3.0
    metrics.get_metrics.return_value = (55.0, 3.0)
    return metrics


@pytest.fixture
def sample_pool():
    pool = []
    # 1. Add 15 solid On-Color (Green/Red) Spells
    for i in range(15):
        pool.append(
            {
                "name": f"Gruul Beater {i}",
                "types": ["Creature"],
                "colors": ["R", "G"],
                "cmc": 4,
                "mana_cost": "{2}{R}{G}",
                "deck_colors": {"All Decks": {"gihwr": 59.0}},
            }
        )
    # 2. Add 1 Off-Color Elite Bomb (Blue) for the Splash builder to find
    pool.append(
        {
            "name": "Dream Trawler",
            "types": ["Creature"],
            "colors": ["U"],
            "cmc": 6,
            "mana_cost": "{4}{U}{U}",
            "deck_colors": {"All Decks": {"gihwr": 65.0}},  # Very high win rate
        }
    )
    # 3. Add 10 low-CMC Aggro cards for the Tempo builder
    # By providing 25 total spells, the Tempo and Consistent
    # builders will pick different cards, preventing them from being
    # identical and filtered out as duplicates!
    for i in range(10):
        pool.append(
            {
                "name": f"Goblin {i}",
                "types": ["Creature"],
                "colors": ["R"],
                "cmc": 1,
                "mana_cost": "{R}",
                "deck_colors": {"All Decks": {"gihwr": 56.0}},
            }
        )
    # 4. Add Fixing to satisfy the Alien Gold/Splash protection
    pool.append(
        {
            "name": "Evolving Wilds",
            "types": ["Land"],
            "colors": [],
            "text": "search your library for a basic land",
            "deck_colors": {"All Decks": {"gihwr": 52.0}},
        }
    )
    return pool


def test_full_deck_suggestion_pipeline(sample_pool, mock_metrics):
    """
    Passes a simulated draft pool into the engine to trigger the creation of
    Consistency, Greedy, and Tempo deck variants.
    """
    config = Configuration()

    # Run the massive function
    results = suggest_deck(sample_pool, mock_metrics, config, event_type="PremierDraft")

    # Assertions
    assert len(results) > 0, "Deck builder failed to generate any archetypes."

    labels = list(results.keys())

    # Ensure it generated different variants
    assert any(
        "Consistent" in label for label in labels
    ), "Failed to build Consistency variant"
    assert any("Tempo" in label for label in labels), "Failed to build Tempo variant"

    # Check that holistic scoring populated properly
    first_deck = results[labels[0]]
    assert first_deck["rating"] > 0.0
    assert first_deck["record"] != ""  # E.g., "7-x (Trophy!)"

    # Check that Frank Karsten Mana Base logic added Basic Lands to reach 40 cards
    total_cards = sum(card.get("count", 1) for card in first_deck["deck_cards"])
    assert total_cards == 40


def test_dynamic_mana_base_math():
    """Verify the proportional land allocation guarantees minimums."""
    # Simulate a deck heavily skewed to Red, with a light Green splash
    spells = [{"mana_cost": "{R}"} for _ in range(15)] + [
        {"mana_cost": "{G}"} for _ in range(2)
    ]

    lands = calculate_dynamic_mana_base(spells, ["R", "G"], forced_count=17)

    # Count the generated basic lands
    forests = sum(1 for c in lands if c["name"] == "Forest")
    mountains = sum(1 for c in lands if c["name"] == "Mountain")

    assert len(lands) == 17
    assert forests >= 3, "Light splash should have a hard floor of 3 sources"
    assert mountains >= 6, "Primary color should have a hard floor of 6 sources"


def test_mana_source_analyzer():
    """Verify the fixing counter correctly identifies fetch lands and duals."""
    pool = [
        {"name": "Forest", "types": ["Land", "Basic"]},  # Should be ignored
        {"name": "Jungle Hollow", "types": ["Land"], "colors": ["B", "G"]},  # Dual
        {
            "name": "Unknown Shores",
            "types": ["Land"],
            "text": "add one mana of any color",
        },  # Any
    ]

    fixing = count_fixing(pool)

    # Jungle Hollow + Unknown Shores = 2 Green, 2 Black, 1 everything else
    assert fixing["G"] == 2
    assert fixing["B"] == 2
    assert fixing["R"] == 1

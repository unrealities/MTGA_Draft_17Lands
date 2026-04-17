import pytest
from unittest.mock import patch, MagicMock
from src.card_logic import optimize_deck


@pytest.fixture
def base_deck_and_sb():
    # Create a perfectly legal 40 card deck: 17 Lands, 23 Spells
    base_deck = [
        {"name": f"Forest {i}", "types": ["Land", "Basic"], "count": 1, "colors": ["G"]}
        for i in range(17)
    ]
    base_deck += [
        {
            "name": f"Bear {i}",
            "types": ["Creature"],
            "count": 1,
            "mana_cost": "{1}{G}",
            "cmc": 2,
            "deck_colors": {"All Decks": {"gihwr": 55.0}},
        }
        for i in range(22)
    ]

    # Add one clunky 7-drop spell to the main deck
    base_deck.append(
        {
            "name": "Clunky Behemoth",
            "types": ["Creature"],
            "count": 1,
            "mana_cost": "{6}{G}",
            "cmc": 7,
            "deck_colors": {"All Decks": {"gihwr": 51.0}},
        }
    )

    # Sideboard containing a premium, cheap spell
    base_sb = [
        {
            "name": "Premium 2-Drop",
            "types": ["Creature"],
            "count": 1,
            "mana_cost": "{1}{G}",
            "cmc": 2,
            "deck_colors": {"All Decks": {"gihwr": 60.0}},
        }
    ]

    return base_deck, base_sb


def mock_simulator_results(deck, iterations):
    """
    Returns a mocked stats dictionary. We artificially boost the score if the
    'Premium 2-Drop' is in the deck to force the optimizer to select that permutation.
    """
    deck_names = [c["name"] for c in deck]
    is_optimal = "Premium 2-Drop" in deck_names

    return {
        "cast_t2": 60 if is_optimal else 40,
        "cast_t3": 60 if is_optimal else 40,
        "cast_t4": 60 if is_optimal else 40,
        "curve_out": 20 if is_optimal else 10,
        "mulligans": 5,
        "screw_t3": 10,
        "screw_t4": 10,
        "color_screw_t3": 5,
        "flood_t5": 10,
        "avg_hand_size": 6.8,
    }


@patch("src.card_logic.simulate_deck", side_effect=mock_simulator_results)
def test_optimize_deck_swaps_clunky_card_for_cheap_premium(mock_sim, base_deck_and_sb):
    """
    Verifies that the optimizer builds the permutations, simulates them,
    and successfully swaps out the high-CMC card for the efficient sideboard card.
    """
    base_deck, base_sb = base_deck_and_sb

    final_deck, final_sb, final_stats, opt_note = optimize_deck(
        base_deck=base_deck, base_sb=base_sb, archetype_key="G", colors=["G"]
    )

    final_names = [c["name"] for c in final_deck]
    sb_names = [c["name"] for c in final_sb]

    # Assertions
    assert len(final_deck) == 40, "Optimized deck must remain exactly 40 cards."
    assert (
        "Premium 2-Drop" in final_names
    ), "Optimizer failed to include the premium sideboard card."
    assert (
        "Clunky Behemoth" not in final_names
    ), "Optimizer failed to cut the clunky high-CMC card."
    assert "Clunky Behemoth" in sb_names, "Cut card was not moved to the sideboard."
    assert (
        "Curve Lower" in opt_note
    ), "Optimization note did not correctly identify the action taken."

    # Verify that the simulator was called multiple times (once per permutation + final run)
    assert mock_sim.call_count > 2


def test_optimize_deck_rejects_invalid_deck_sizes():
    """Verify the optimizer instantly bails if given an illegal deck size."""
    # Pass a deck with only 10 cards
    deck = [{"name": "Card", "count": 10}]
    final_deck, final_sb, final_stats, opt_note = optimize_deck(
        deck, [], "All Decks", ["W"]
    )

    assert final_stats is None
    assert final_deck == deck

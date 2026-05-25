"""
tests/test_mana_base.py
Challenges the status quo of Mana Base generation and Monte Carlo simulations.
"""

import pytest
from src.card_logic import build_variant_greedy, simulate_deck
from unittest.mock import MagicMock


@pytest.fixture
def mock_metrics():
    metrics = MagicMock()
    metrics.get_metrics.return_value = (55.0, 3.0)
    return metrics


def test_greedy_double_pip_bomb_splash(mock_metrics):
    """
    Simulates a WB deck attempting to splash a 3UU Bomb.
    Without fixing, the builder should reject it.
    With heavy fixing (Treasures/Duals), the builder should allow it and the MC should pass.
    """
    # Base WB Pool
    pool = [
        {
            "name": f"White 2-Drop {i}",
            "types": ["Creature"],
            "colors": ["W"],
            "cmc": 2,
            "mana_cost": "{1}{W}",
            "deck_colors": {"All Decks": {"gihwr": 57.0}},
        }
        for i in range(10)
    ] + [
        {
            "name": f"Black 3-Drop {i}",
            "types": ["Creature"],
            "colors": ["B"],
            "cmc": 3,
            "mana_cost": "{2}{B}",
            "deck_colors": {"All Decks": {"gihwr": 57.0}},
        }
        for i in range(10)
    ]

    # The 3UU Bomb (Huge Z-Score)
    pool.append(
        {
            "name": "Dream Trawler Level Bomb",
            "types": ["Creature"],
            "colors": ["U"],
            "cmc": 6,
            "mana_cost": "{4}{U}{U}",
            "deck_colors": {"All Decks": {"gihwr": 68.0}},
        }
    )

    # SCENARIO 1: No Fixing. The builder should REJECT the double-pip splash.
    greedy_deck_nofix, splash_color_nofix = build_variant_greedy(
        pool, ["W", "B"], mock_metrics
    )
    assert splash_color_nofix != "U", "Should reject 3UU splash without fixing."

    # SCENARIO 2: Abundant Fixing. Add 3 duals and a treasure maker.
    pool.extend(
        [
            {
                "name": "WB Dual",
                "types": ["Land"],
                "colors": ["W", "B"],
                "deck_colors": {"All Decks": {"gihwr": 54.0}},
            },
            {
                "name": "WU Dual",
                "types": ["Land"],
                "colors": ["W", "U"],
                "deck_colors": {"All Decks": {"gihwr": 54.0}},
            },
            {
                "name": "BU Dual",
                "types": ["Land"],
                "colors": ["B", "U"],
                "deck_colors": {"All Decks": {"gihwr": 54.0}},
            },
            {
                "name": "Treasure Dork",
                "types": ["Creature"],
                "colors": ["W"],
                "cmc": 2,
                "mana_cost": "{1}{W}",
                "tags": ["fixing_ramp"],
                "oracle_text": "Create a treasure",
                "deck_colors": {"All Decks": {"gihwr": 55.0}},
            },
        ]
    )

    greedy_deck_fix, splash_color_fix = build_variant_greedy(
        pool, ["W", "B"], mock_metrics
    )

    assert splash_color_fix == "U", (
        "Should actively embrace the 3UU bomb when fixing is heavy."
    )

    # Verify the Monte Carlo actually accepts the treasure dork as a valid mana source
    stats = simulate_deck(greedy_deck_fix, iterations=500)

    # Because we have duals and treasure dorks, our cast_t2 and cast_t3 rates for the core WB deck should remain relatively high despite the U splash!
    assert stats["cast_t2"] > 40.0, (
        "Core WB velocity destroyed by splash! Auto-Lands allocated basics poorly."
    )

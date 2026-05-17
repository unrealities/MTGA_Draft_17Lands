"""
tests/test_simulator.py
Unit tests for the Numba-optimized Monte Carlo Simulator.
Verifies bitwise mana logic, mulligan algorithms, and castability metrics.
"""

import pytest
import numpy as np
import src.card_logic
from src.advisor.simulator import simulate_deck, _parse_deck_to_arrays

# --- HELPER FACTORY ---


def make_card(
    name, count=1, cmc=0, types=None, mana_cost="", colors=None, text="", tags=None
):
    """Helper to generate a dictionary matching the app's internal Card schema."""
    return {
        "name": name,
        "count": count,
        "cmc": cmc,
        "types": types or [],
        "mana_cost": mana_cost,
        "colors": colors or [],
        "oracle_text": text,
        "tags": tags or [],
    }


# --- TESTS ---


def test_simulator_invalid_deck_size():
    """Verify the simulator immediately rejects decks with fewer than 40 cards."""
    # Create a 39 card deck
    deck = [make_card("Mountain", count=39, types=["Land"])]

    # Should safely return None instead of throwing index bounds errors in NumPy
    result = simulate_deck(deck)
    assert result is None


def test_parsing_bitmasks_and_flags():
    """Verify that Python dictionaries are correctly translated to Numba-safe NumPy bitmasks."""
    deck = [
        # 1. Standard Land (Red = 8)
        make_card("Mountain", count=1, types=["Land"], colors=["R"]),
        # 2. Dual Land (Blue/Black = 2 | 4 = 6)
        make_card("Watery Grave", count=1, types=["Land"], colors=["U", "B"]),
        # 3. Any Color Land (WUBRG = 31)
        make_card(
            "Unknown Shores", count=1, types=["Land"], text="add one mana of any color"
        ),
        # 4. Ramp Artifact (Any Color)
        make_card("Manalith", count=1, types=["Artifact"], tags=["fixing_ramp"]),
        # 5. Removal Spell
        make_card(
            "Murder",
            count=1,
            cmc=3,
            types=["Instant"],
            mana_cost="{1}{B}{B}",
            tags=["removal"],
        ),
        # 6. Hybrid/Split Mana Spell (Should pick first valid -> Blue = 2)
        make_card(
            "Hybrid Spell", count=1, cmc=2, types=["Sorcery"], mana_cost="{U/R}{U/R}"
        ),
    ]
    # Pad to 40 to pass the size check
    deck.append(make_card("Filler", count=34, types=["Creature"]))

    arrays = _parse_deck_to_arrays(deck)
    assert arrays is not None
    is_land, is_ramp, is_removal, cmcs, mana_produced, primary_req = arrays

    # Verify Booleans
    assert is_land[0] == True  # Mountain
    assert is_land[3] == False  # Manalith is an artifact
    assert is_ramp[3] == True  # Manalith is ramp
    assert is_removal[4] == True  # Murder

    # Verify Mana Produced Bitmasks
    assert mana_produced[0] == 8  # Red
    assert mana_produced[1] == 6  # Blue (2) | Black (4)
    assert mana_produced[2] == 31  # Any color -> 1|2|4|8|16 = 31
    assert mana_produced[3] == 31  # Ramp any color -> 31

    # Verify Primary Requirement Bitmasks
    # Murder requires Black (4)
    assert primary_req[4] == 4
    # Hybrid Spell picks the first valid pip from '{U/R}' which is 'U' (2)
    assert primary_req[5] == 2


def test_mulligan_0_lands():
    """A deck with 0 lands should trigger a mulligan 100% of the time."""
    deck = [make_card("Goblin", count=40, cmc=1, types=["Creature"], mana_cost="{R}")]

    # Numba JIT compiling happens here; it will run very fast
    stats = simulate_deck(deck, iterations=1000)

    assert stats["mulligans"] == 100.0
    assert stats["screw_t3"] == 100.0  # Can't play 3 lands by turn 3
    assert stats["cast_t2"] == 0.0


def test_mulligan_40_lands():
    """A deck with 40 lands should also trigger a mulligan 100% of the time (Flood protection)."""
    deck = [make_card("Mountain", count=40, types=["Land"], colors=["R"])]

    stats = simulate_deck(deck, iterations=1000)

    assert stats["mulligans"] == 100.0
    assert stats["flood_t5"] == 100.0  # Will definitely have >= 6 lands by turn 5
    assert stats["screw_t3"] == 0.0
    assert stats["cast_t2"] == 0.0


def test_perfect_mono_red_aggro():
    """A perfectly balanced mono-color deck should have 0% color screw and high cast rates."""
    deck = [
        make_card("Mountain", count=17, types=["Land"], colors=["R"]),
        make_card(
            "Red 2-Drop", count=15, cmc=2, types=["Creature"], mana_cost="{1}{R}"
        ),
        make_card("Red 3-Drop", count=8, cmc=3, types=["Creature"], mana_cost="{2}{R}"),
    ]

    stats = simulate_deck(deck, iterations=2000)

    # With 17 lands and mono-red, color screw on Turn 3 should be mathematically impossible
    assert stats["color_screw_t3"] == 0.0

    # Cast rates should be extremely healthy
    assert stats["cast_t2"] > 50.0
    assert stats["cast_t3"] > 50.0


def test_uncastable_deck_color_screw():
    """A deck with lands that don't match the spells should flag massive color screw."""
    deck = [
        make_card("Forest", count=17, types=["Land"], colors=["G"]),
        make_card(
            "Blue 3-Drop", count=23, cmc=3, types=["Creature"], mana_cost="{1}{U}{U}"
        ),
    ]

    stats = simulate_deck(deck, iterations=2000)

    # We have zero blue sources. We can NEVER cast our spells.
    assert stats["cast_t3"] == 0.0

    # Color screw triggers when you have enough total lands (3), a 3-drop in hand, but lack the right colors
    assert stats["color_screw_t3"] > 50.0


def test_any_color_ramp_fixing():
    """Verify that 'Any Color' lands and ramp artifacts satisfy strict color requirements."""
    deck = [
        # Only 5 actual blue sources
        make_card("Island", count=5, types=["Land"], colors=["U"]),
        # 12 "Any Color" sources
        make_card(
            "Unknown Shores", count=12, types=["Land"], text="add one mana of any color"
        ),
        # Spells demanding intense blue
        make_card(
            "Archmage Charm", count=23, cmc=3, types=["Instant"], mana_cost="{U}{U}{U}"
        ),
    ]

    stats = simulate_deck(deck, iterations=2000)

    # Even though we only have 5 islands, the 'Unknown Shores' provides bitmask 31 (WUBRG).
    # This should allow us to cast UUU semi-regularly, preventing 100% color screw.
    assert stats["cast_t3"] > 10.0
    # It won't be perfect, but it definitely shouldn't be 0
    assert stats["color_screw_t3"] < 100.0


def test_removal_tracking():
    """Verify the simulator correctly tracks if we hold interaction by Turn 4."""
    deck = [
        make_card("Swamp", count=17, types=["Land"], colors=["B"]),
        make_card("Murder", count=23, cmc=3, types=["Instant"], tags=["removal"]),
    ]

    stats = simulate_deck(deck, iterations=1000)

    # If 23 of our cards are removal, the odds of seeing one by turn 4 are ~100%
    assert stats["removal_t4"] > 95.0

"""
tests/test_simulator.py
Unit tests for the Numba-optimized Monte Carlo Simulator.
Verifies bitwise mana logic, mulligan algorithms, and castability metrics.
"""

import pytest
from src.advisor.simulator import (
    simulate_deck,
    _parse_deck_to_arrays,
    parse_mana_cost,
    MAX_PIPS,
)

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


@pytest.mark.parametrize("text, colors, expected", [
    ("{T}: Add {G}.", ["G"], 16),
    ("Add one mana of any color", [], 31),
    ("Add one mana of any one color", [], 31),
    ("Add {R} or {G}", [], 24),
    ("{U}, {T}: Add {W}{W}.", [], 1),
    ("Add {C}.", ["U"], 0),
    ("", ["G"], 16),
])
def test_ramp_produced_colors_follow_rules_text(text, colors, expected):
    deck = [
        make_card("Ramp", tags=["fixing_ramp"], text=text, colors=colors),
        make_card("Filler", count=39),
    ]
    arrays = _parse_deck_to_arrays(deck)
    assert arrays.is_ramp[0]
    assert arrays.mana_produced[0] == expected


def test_green_dork_cannot_fix_blue_spells():
    deck = [
        make_card("Forest", count=17, types=["Land"], colors=["G"]),
        make_card("Green Dork", cmc=1, mana_cost="{G}", types=["Creature"],
                  colors=["G"], tags=["fixing_ramp"], text="{T}: Add {G}."),
        make_card("Blue Spell", count=22, cmc=4, mana_cost="{3}{U}", types=["Creature"]),
    ]
    assert simulate_deck(deck, iterations=2000)["cast_t4"] == 0.0


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
        make_card(
            "Manalith", count=1, types=["Artifact"], tags=["fixing_ramp"],
            text="{T}: Add one mana of any color.",
        ),
        # 5. Removal Spell
        make_card(
            "Murder",
            count=1,
            cmc=3,
            types=["Instant"],
            mana_cost="{1}{B}{B}",
            tags=["removal"],
        ),
        # 6. Hybrid Mana Spell (each pip accepts either color -> U|R = 2|8 = 10)
        make_card(
            "Hybrid Spell", count=1, cmc=2, types=["Sorcery"], mana_cost="{U/R}{U/R}"
        ),
    ]
    # Pad to 40 to pass the size check
    deck.append(make_card("Filler", count=34, types=["Creature"]))

    arrays = _parse_deck_to_arrays(deck)
    assert arrays is not None

    # Verify Booleans
    assert arrays.is_land[0]  # Mountain
    assert not arrays.is_land[3]  # Manalith is an artifact
    assert arrays.is_ramp[3]  # Manalith is ramp
    assert arrays.is_removal[4]  # Murder

    # Verify Mana Produced Bitmasks
    assert arrays.mana_produced[0] == 8  # Red
    assert arrays.mana_produced[1] == 6  # Blue (2) | Black (4)
    assert arrays.mana_produced[2] == 31  # Any color -> 1|2|4|8|16 = 31
    assert arrays.mana_produced[3] == 31  # Ramp any color -> 31

    # Verify pip requirements: one entry per colored pip, plus generic count
    # Murder {1}{B}{B}: two separate Black (4) pips and one generic
    assert arrays.pip_count[4] == 2
    assert list(arrays.pips[4, :2]) == [4, 4]
    assert arrays.generic[4] == 1
    assert arrays.costs[4] == 3
    # Hybrid Spell keeps BOTH options of each '{U/R}' pip: U (2) | R (8) = 10
    assert arrays.pip_count[5] == 2
    assert list(arrays.pips[5, :2]) == [10, 10]
    assert arrays.generic[5] == 0
    # Fixed-width layout for the numba kernel
    assert arrays.pips.shape == (40, MAX_PIPS)


@pytest.mark.parametrize(
    "cost,cmc,expected",
    [
        ("{1}{B}{B}", 3, ([4, 4], 1)),
        ("{G/U}", 1, ([18], 0)),
        ("{G/P}", 1, ([16], 0)),
        ("{2/W}{2/W}", 4, ([], 4)),
        ("{X}{R}{R}", 2, ([8, 8], 0)),
        ("{C}{C}", 2, ([], 2)),
        ("{10}", 10, ([], 10)),
        ("{1}{R} // {3}{U}{U}", 7, ([8], 1)),
        ("", 3, ([], 3)),
        (None, 0, ([], 0)),
    ],
)
def test_parse_mana_cost(cost, cmc, expected):
    """Printed costs become a list of colored pip masks plus a generic count."""
    assert parse_mana_cost(cost, cmc) == expected


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


# --- REGRESSION TESTS: issue #203 (castability used bitmask OR of colors) ---


def test_single_source_cannot_pay_double_pip():
    """One Swamp must not satisfy {B}{B}: each pip needs its own source."""
    deck = [
        make_card("Swamp", count=1, types=["Land"], colors=["B"]),
        make_card("Island", count=16, types=["Land"], colors=["U"]),
        make_card("Murder", count=23, cmc=3, types=["Instant"], mana_cost="{1}{B}{B}"),
    ]

    stats = simulate_deck(deck, iterations=1000)

    assert stats["cast_t3"] == 0.0


def test_two_sources_can_pay_double_pip():
    """With plenty of Black sources {1}{B}{B} must be castable on turn 3."""
    deck = [
        make_card("Swamp", count=9, types=["Land"], colors=["B"]),
        make_card("Island", count=8, types=["Land"], colors=["U"]),
        make_card("Murder", count=23, cmc=3, types=["Instant"], mana_cost="{1}{B}{B}"),
    ]

    stats = simulate_deck(deck, iterations=2000)

    assert stats["cast_t3"] > 30.0


def test_dual_land_is_a_single_source():
    """A U/B dual can pay one pip, not two: {B}{B} with only the dual making B
    is never castable, while {U}{B} (dual for B, Island for U) is."""
    lands = [
        make_card("Watery Grave", count=1, types=["Land"], colors=["U", "B"]),
        make_card("Island", count=16, types=["Land"], colors=["U"]),
    ]
    double_black = lands + [
        make_card("Pip Hog", count=23, cmc=2, types=["Creature"], mana_cost="{B}{B}")
    ]
    gold = lands + [
        make_card("Dimir Bear", count=23, cmc=2, types=["Creature"], mana_cost="{U}{B}")
    ]

    assert simulate_deck(double_black, iterations=1000)["cast_t2"] == 0.0
    assert simulate_deck(gold, iterations=2000)["cast_t2"] > 0.0


def test_hybrid_pip_accepts_either_color():
    """{G/U} must be payable with an Island (previously only G was accepted)."""
    deck = [
        make_card("Island", count=17, types=["Land"], colors=["U"]),
        make_card(
            "Hybrid Bear", count=23, cmc=2, types=["Creature"], mana_cost="{1}{G/U}"
        ),
    ]

    stats = simulate_deck(deck, iterations=2000)

    assert stats["cast_t2"] > 50.0


def test_uncastable_fixer_does_not_provide_mana():
    """A mana rock only fixes if it could actually be cast. {R}{R} rocks in a
    deck of Islands never resolve, so the red 2-drops are never castable."""
    deck = [
        make_card("Island", count=17, types=["Land"], colors=["U"]),
        make_card(
            "Red Rock",
            count=3,
            cmc=2,
            types=["Artifact"],
            mana_cost="{R}{R}",
            text="{T}: Add one mana of any color.",
        ),
        make_card("Red Bear", count=20, cmc=2, types=["Creature"], mana_cost="{1}{R}"),
    ]

    stats = simulate_deck(deck, iterations=1000)

    assert stats["cast_t2"] == 0.0


def _rock_deck(rock_cost, rock_cmc, spell_cost, spell_cmc):
    return [
        make_card("Island", count=17, types=["Land"], colors=["U"]),
        make_card(
            "Mind Stone",
            count=3,
            cmc=rock_cmc,
            types=["Artifact"],
            mana_cost=rock_cost,
            text="{T}: Add one mana of any color.",
        ),
        # Red spells: only castable with the rock's mana
        make_card(
            "Red Spell",
            count=20,
            cmc=spell_cmc,
            types=["Creature"],
            mana_cost=spell_cost,
        ),
    ]


def test_expensive_ramp_does_not_fix_early_turns():
    """A 3-mana rock can't be cast before turn 3, so it can't supply red for a
    turn-2 play (previously ramp of any mana value counted on turn 2)."""
    stats = simulate_deck(_rock_deck("{3}", 3, "{1}{R}", 2), iterations=1000)

    assert stats["cast_t2"] == 0.0


def test_castable_ramp_fixes_later_turns():
    """A 2-mana rock cast on turn 2 supplies red for the turn-3 play."""
    stats = simulate_deck(_rock_deck("{2}", 2, "{2}{R}", 3), iterations=2000)

    assert stats["cast_t3"] > 20.0


def test_castability_uses_printed_cost_not_landcycling():
    """A {5}{U} landcycler is a 6-drop for castability, not a 2-drop."""
    deck = [
        make_card("Island", count=17, types=["Land"], colors=["U"]),
        make_card(
            "Big Cycler",
            count=23,
            cmc=6,
            types=["Creature"],
            mana_cost="{5}{U}",
            text="Islandcycling {2}",
        ),
    ]

    stats = simulate_deck(deck, iterations=1000)

    assert stats["cast_t2"] == 0.0
    assert stats["cast_t3"] == 0.0
    assert stats["cast_t4"] == 0.0

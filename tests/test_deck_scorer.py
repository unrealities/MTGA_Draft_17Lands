"""
tests/test_deck_scorer.py
Unit tests for the Holistic Deck Evaluator.
Verifies pool grading, tribal synergy detection, and curve penalties.
"""

import pytest
from unittest.mock import MagicMock
import src.card_logic

from src.advisor.deck_scorer import (
    get_card_rating,
    identify_top_pairs,
    calculate_holistic_score,
    estimate_record,
    TIER_TO_GIHWR,
)

# --- FIXTURES & HELPERS ---


@pytest.fixture
def mock_metrics():
    metrics = MagicMock()
    # Mocking format average to 55.0% WR, 4.0 Standard Deviation
    metrics.get_metrics.return_value = (55.0, 4.0)
    return metrics


def make_card(
    name, count=1, types=None, colors=None, cmc=2, tags=None, text="", gihwr=55.0
):
    return {
        "name": name,
        "count": count,
        "types": types or ["Creature"],
        "colors": colors or [],
        "cmc": cmc,
        "tags": tags or [],
        "oracle_text": text,
        "deck_colors": {"All Decks": {"gihwr": gihwr}},
    }


# --- TESTS ---


def test_get_card_rating_tier_fallback(mock_metrics):
    """Verify that if 17Lands data is poor, it correctly maps and falls back to Tier List grades."""
    # A card with terrible 17Lands data
    card = make_card("New Card", gihwr=0.0)

    # Mock Tier Data containing an A+ grade
    mock_tier = MagicMock()
    mock_tier.ratings = {"New Card": MagicMock(rating="A+")}
    tier_data = {"Pro_List": mock_tier}

    rating = get_card_rating(
        card, colors=["W"], metrics=mock_metrics, tier_data=tier_data
    )

    # A+ maps to 68.0 in TIER_TO_GIHWR
    assert rating == 68.0


def test_get_card_rating_no_data_in_established_set_is_unplayable(mock_metrics):
    """A card with no win-rate data in a set that otherwise HAS data (mean > 0)
    is one nobody plays (e.g. Worlds Within Worlds) — it must not be scored
    generously from a metadata heuristic."""
    # mock_metrics reports a 55.0 mean, i.e. the set has data.
    card = make_card("Worlds Within Worlds", colors=["G", "U"], cmc=7, gihwr=0.0)

    rating = get_card_rating(card, colors=["G", "U"], metrics=mock_metrics)

    assert rating == 0.0, f"Dataless card scored {rating}; should be unplayable."


def test_get_card_rating_no_data_day1_uses_heuristic():
    """On Day 1 (no metrics / set mean == 0) a dataless card should still get a
    heuristic score so the offline evaluator works."""
    card = make_card("Fresh Uncommon", colors=["G"], cmc=2, gihwr=0.0)

    # No metrics at all => Day 1 fallback.
    rating = get_card_rating(card, colors=["G"], metrics=None)

    assert rating > 0.0


def test_get_card_rating_no_data_zero_mean_metrics_uses_heuristic():
    """A metrics object that reports a 0.0 mean (brand-new set) also counts as
    Day 1 and must not brand every card unplayable."""
    day1_metrics = MagicMock()
    day1_metrics.get_metrics.return_value = (0.0, 0.0)
    card = make_card("Fresh Uncommon", colors=["G"], cmc=2, gihwr=0.0)

    rating = get_card_rating(card, colors=["G"], metrics=day1_metrics)

    assert rating > 0.0


def test_get_card_rating_archetype_only_data_is_kept(mock_metrics):
    """A card with real archetype data but no All-Decks number must still be
    rated on its archetype data, not treated as unplayable."""
    card = make_card("Niche Payoff", colors=["U"], gihwr=0.0)
    # Dataset keys are WUBRG-ordered: Simic is "UG", never "GU".
    card["deck_colors"]["UG"] = {"gihwr": 60.0}

    rating = get_card_rating(card, colors=["G", "U"], metrics=mock_metrics)

    assert rating == pytest.approx(60.0)


# Every two-color archetype key exactly as the dataset loader stores it
# (normalize_color_string -> WUBRG order). Alphabetical sorting only matches
# "BR" and "BG", which silently dropped archetype data for the other 8 pairs.
WUBRG_PAIRS = ["WU", "WB", "WR", "WG", "UB", "UR", "UG", "BR", "BG", "RG"]


@pytest.mark.parametrize("pair", WUBRG_PAIRS)
@pytest.mark.parametrize("reverse", [False, True], ids=["wubrg", "reversed"])
def test_get_card_rating_uses_wubrg_archetype_key(pair, reverse):
    """Archetype GIH WR must be found for every color pair regardless of the
    order the colors are passed in (issue #203)."""
    colors = list(pair)[::-1] if reverse else list(pair)
    card = {"deck_colors": {"All Decks": {"gihwr": 0}, pair: {"gihwr": 60.0}}}

    assert get_card_rating(card, colors) == pytest.approx(60.0)


@pytest.mark.parametrize("pair", WUBRG_PAIRS)
def test_get_card_rating_blends_archetype_with_all_decks(pair):
    """With both numbers present the archetype rating is blended 70/30."""
    card = {"deck_colors": {"All Decks": {"gihwr": 50.0}, pair: {"gihwr": 60.0}}}

    assert get_card_rating(card, list(pair)[::-1]) == pytest.approx(57.0)


def test_get_card_rating_three_colors_uses_first_two_in_wubrg_order():
    """Only the first two (primary) colors form the archetype key."""
    card = {"deck_colors": {"All Decks": {"gihwr": 0}, "UG": {"gihwr": 61.0}}}

    assert get_card_rating(card, ["G", "U", "W"]) == pytest.approx(61.0)


def test_holistic_score_uses_wubrg_archetype_key(mock_metrics):
    """calculate_holistic_score must read the archetype win rate for the
    deck's pair (here Dimir: data stored under "UB", deck colors ["B", "U"])."""

    def build(arch_key):
        spell = make_card("Dimir Spell", count=23, colors=["U", "B"], gihwr=55.0)
        spell["deck_colors"][arch_key] = {"gihwr": 65.0}
        return [make_card("Land", count=17, types=["Land"]), spell]

    with_arch, _ = calculate_holistic_score(
        build("UB"), colors=["B", "U"], pool_size=45, metrics=mock_metrics
    )
    # A key that does not exist in real datasets must be ignored.
    without_arch, _ = calculate_holistic_score(
        build("BU"), colors=["B", "U"], pool_size=45, metrics=mock_metrics
    )

    assert with_arch > without_arch


def test_identify_top_pairs(mock_metrics):
    """Verify it successfully isolates the highest-performing 2-color pair in a messy pool."""
    pool = [
        make_card("White Bomb", colors=["W"], gihwr=65.0),
        make_card("White Good", colors=["W"], gihwr=60.0),
        make_card("Blue Good", colors=["U"], gihwr=60.0),
        make_card(
            "Red Trash", colors=["R"], gihwr=40.0
        ),  # Below baseline, should be ignored
    ]

    pairs = identify_top_pairs(pool, mock_metrics)

    # Highest scoring colors are W and U. Top pair should be WU (or UW).
    assert set(pairs[0]) == {"W", "U"}


def test_holistic_score_aggro_bonus(mock_metrics):
    """Verify a deck with a perfectly low curve gets the Aggro Curve bonus (+5.0)."""
    deck = [
        make_card("Mountain", count=16, types=["Land"]),
        make_card("Goblin 1", count=14, cmc=1, gihwr=55.0),  # Super low curve
        make_card("Goblin 2", count=10, cmc=2, gihwr=55.0),
    ]

    score, notes = calculate_holistic_score(
        deck, colors=["R"], pool_size=45, metrics=mock_metrics
    )

    assert "Excellent Aggro Curve (+5.0)" in notes
    assert score > 75.0  # Average deck is 75, this should be boosted


def test_holistic_score_clunky_penalty(mock_metrics):
    """Verify a deck with too many high-CMC cards relative to its lands gets severely penalized."""
    deck = [
        make_card("Forest", count=15, types=["Land"]),  # Not enough lands!
        make_card("Big Dino", count=25, cmc=6, gihwr=55.0),  # Way too heavy!
    ]

    score, notes = calculate_holistic_score(
        deck, colors=["G"], pool_size=45, metrics=mock_metrics
    )

    assert "High Curve / Needs Lands" in notes
    assert score < 75.0  # Should be heavily penalized below the 75 baseline


def test_holistic_score_tribal_synergy(mock_metrics):
    """Verify tribal density triggers the synergy bonus."""
    deck = [
        make_card("Island", count=17, types=["Land"]),
        # 7 Ninjas (We inject 'Ninja' into the types array so the scorer detects the tribe)
        make_card(
            "Ninja", count=7, types=["Creature", "Ninja"], text="Ninja", gihwr=55.0
        ),
        # 3 Payoffs that care about Ninjas
        make_card(
            "Ninja Lord",
            count=3,
            types=["Creature", "Ninja"],
            text="ninja creatures you control get +1/+1",
            gihwr=55.0,
        ),
        make_card("Filler", count=13, types=["Creature"], gihwr=55.0),
    ]

    score, notes = calculate_holistic_score(
        deck, colors=["U"], pool_size=45, metrics=mock_metrics
    )

    assert "Synergy" in notes
    assert score > 75.0


def test_holistic_score_domain_bonus_and_penalty(mock_metrics):
    """Verify 3+ color decks are rewarded for fixing, or punished for being greedy."""

    # Scenario A: Greedy 4-color soup (No fixing)
    greedy_deck = [
        make_card("Basic", count=17, types=["Land"]),
        make_card(
            "Spell", count=23, types=["Creature"], text="basic land types", gihwr=55.0
        ),
    ]
    score_greedy, notes_greedy = calculate_holistic_score(
        greedy_deck, colors=["W", "U", "B", "R"], pool_size=45, metrics=mock_metrics
    )
    assert "Greedy Mana Strain" in notes_greedy

    # Scenario B: Supported 4-color soup (Lots of fixing)
    supported_deck = [
        make_card("Basic", count=13, types=["Land"]),
        make_card(
            "Dual Land", count=4, types=["Land"], colors=["W", "U"]
        ),  # 4 Fixing sources
        make_card(
            "Domain Payoff",
            count=2,
            types=["Creature"],
            text="basic land types",
            gihwr=55.0,
        ),
        make_card("Filler", count=21, types=["Creature"], gihwr=55.0),
    ]
    score_supported, notes_supported = calculate_holistic_score(
        supported_deck, colors=["W", "U", "B", "R"], pool_size=45, metrics=mock_metrics
    )
    assert "Supported Domain/Soup (+6.0)" in notes_supported


def test_holistic_score_incomplete_deck(mock_metrics):
    """Verify massive penalty if the user tries to analyze a deck with 5 cards."""
    deck = [make_card("Spell", count=5, gihwr=65.0)]  # Only 5 cards!

    score, notes = calculate_holistic_score(
        deck, colors=["W"], pool_size=45, metrics=mock_metrics
    )

    assert "Incomplete Deck" in notes
    # Score should be completely ruined (probably 0.0)
    assert score < 50.0


def test_estimate_record():
    """Verify the record string generation logic for BO1 and BO3."""
    # BO1 (Premier Draft)
    assert "7-x" in estimate_record(90.0, is_bo3=False)
    assert "0-3" in estimate_record(50.0, is_bo3=False)

    # BO3 (Traditional Draft)
    assert "3-0" in estimate_record(90.0, is_bo3=True)
    assert "0-2" in estimate_record(50.0, is_bo3=True)

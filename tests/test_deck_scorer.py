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
    BASE_SCORE,
    WEIGHTS,
    deck_features,
    expected_wins,
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


def test_holistic_score_domain_bonus(mock_metrics):
    """3+ color decks with domain payoffs get a bonus only with the fixing for them."""

    # Scenario A: Greedy 4-color soup (No fixing)
    greedy_deck = [
        make_card("Basic", count=17, types=["Land"]),
        make_card(
            "Spell", count=23, types=["Creature"], text="basic land types", gihwr=55.0
        ),
    ]
    _, notes_greedy = calculate_holistic_score(
        greedy_deck, colors=["W", "U", "B", "R"], pool_size=45, metrics=mock_metrics
    )
    assert "Domain" not in notes_greedy

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
    _, notes_supported = calculate_holistic_score(
        supported_deck, colors=["W", "U", "B", "R"], pool_size=45, metrics=mock_metrics
    )
    assert (
        f"Supported Domain/Soup (+{WEIGHTS['domain_supported']:.1f})" in notes_supported
    )


def test_holistic_score_incomplete_deck(mock_metrics):
    """Verify massive penalty if the user tries to analyze a deck with 5 cards."""
    deck = [make_card("Spell", count=5, gihwr=65.0)]  # Only 5 cards!

    score, notes = calculate_holistic_score(
        deck, colors=["W"], pool_size=45, metrics=mock_metrics
    )

    assert "Incomplete Deck" in notes
    # Score should be completely ruined (probably 0.0)
    assert score < 50.0


def test_holistic_score_is_the_weighted_sum_of_deck_features(mock_metrics):
    """The score is BASE_SCORE plus each feature times its weight."""
    deck = [
        make_card("Swamp", count=17, types=["Land"]),
        make_card("Good Spell", count=13, cmc=4, gihwr=59.0),
        make_card("Big Spell", count=10, cmc=6, gihwr=55.0),
    ]

    score, notes = calculate_holistic_score(
        deck, colors=["B"], pool_size=45, metrics=mock_metrics
    )
    features = deck_features(deck, ["B"], 45, mock_metrics)

    assert features["card_quality"] == pytest.approx(
        (59.0 * 13 + 55.0 * 10) / 23 / 4.0 - 55.0 / 4.0
    )
    assert features["two_colors"] == 1.0
    assert score == pytest.approx(
        BASE_SCORE + sum(WEIGHTS[k] * v for k, v in features.items())
    )
    assert notes == f"Rock-Solid Mana (+{WEIGHTS['two_colors']:.1f})"


def test_expected_wins_by_recursion():
    def by_recursion(p, max_wins, max_losses, wins=0, losses=0):
        if wins == max_wins or losses == max_losses:
            return wins
        return p * by_recursion(p, max_wins, max_losses, wins + 1, losses) + (
            1 - p
        ) * by_recursion(p, max_wins, max_losses, wins, losses + 1)

    for p in (0.0, 0.3, 0.55, 1.0):
        assert expected_wins(p, 7, 3) == pytest.approx(by_recursion(p, 7, 3))


def test_estimate_record():
    """Expected wins rise with the score, up to each event's cap."""
    bo1 = [float(estimate_record(s).split()[0]) for s in (50, 75, 90, 200)]
    assert bo1 == sorted(bo1) and bo1[-1] == 7.0
    # A deck of the base score wins about half its games: about 3 wins in Bo1.
    assert 2.8 <= bo1[1] <= 3.2
    bo3 = [float(estimate_record(s, is_bo3=True).split()[0]) for s in (50, 75, 200)]
    assert bo3 == sorted(bo3) and bo3[-1] == 3.0
    # Bo3 always plays three matches, so a coin-flip deck averages 1.5 wins.
    assert 1.4 <= bo3[1] <= 1.6

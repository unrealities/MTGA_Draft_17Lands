import pytest
from unittest.mock import MagicMock
from src.advisor.engine import DraftAdvisor
from src.advisor.schema import Recommendation


@pytest.fixture
def mock_metrics():
    metrics = MagicMock()
    # get_metrics returns (mean, std)
    metrics.get_metrics.return_value = (55.0, 4.0)
    return metrics


def test_identify_main_colors(mock_metrics):
    pool = [
        {"colors": ["W"], "deck_colors": {"All Decks": {"gihwr": 60.0}}},
        {"colors": ["W"], "deck_colors": {"All Decks": {"gihwr": 60.0}}},
        {"colors": ["U"], "deck_colors": {"All Decks": {"gihwr": 55.0}}},
        {"colors": ["R"], "deck_colors": {"All Decks": {"gihwr": 40.0}}},
    ]
    advisor = DraftAdvisor(mock_metrics, pool)

    # Because White has high WR and multiple cards, it should be top
    assert "W" in advisor.main_colors


@pytest.mark.parametrize(
    "first,second,expected",
    [("B", "U", "UB"), ("U", "B", "UB"), ("G", "W", "WG"), ("R", "G", "RG")],
)
def test_main_archetype_uses_wubrg_key(mock_metrics, first, second, expected):
    """main_archetype is used to look up deck_colors stats, whose keys are
    WUBRG-ordered; it must not be alphabetically sorted (issue #203)."""
    pool = [
        {"colors": [first], "deck_colors": {"All Decks": {"gihwr": 62.0}}}
        for _ in range(4)
    ] + [
        {"colors": [second], "deck_colors": {"All Decks": {"gihwr": 60.0}}}
        for _ in range(3)
    ]
    advisor = DraftAdvisor(mock_metrics, pool)

    assert set(advisor.main_colors[:2]) == {first, second}
    assert advisor.main_archetype == expected


def test_analyze_pool(mock_metrics):
    # Establish a definitive "White Lane" by padding the pool > 15 cards
    pool = [
        {
            "colors": ["W"],
            "types": ["Creature"],
            "cmc": 2,
            "deck_colors": {"All Decks": {"gihwr": 60.0}},
        }
        for _ in range(15)
    ]

    # Add a black removal spell (not a bomb, just utility)
    pool.append(
        {
            "colors": ["B"],
            "tags": ["removal"],
            "cmc": 4,
            "deck_colors": {"All Decks": {"gihwr": 55.0}},
        }
    )

    # Add a green fixing bomb. Because we are definitively in White, this will trigger the splash logic.
    pool.append(
        {
            "colors": ["G"],
            "tags": ["fixing_ramp"],
            "cmc": 1,
            "deck_colors": {"All Decks": {"gihwr": 65.0}},
        }
    )

    advisor = DraftAdvisor(mock_metrics, pool)

    assert advisor.pool_metrics["early_plays"] == 15
    assert advisor.pool_metrics["hard_removal_count"] == 1
    assert advisor.pool_metrics["fixing_count"] == 1

    # 65.0 > 55.0 + (1.5 * 4.0) = 61.0, so 'G' triggers as a premium splash target
    assert "G" in advisor.pool_metrics["splash_targets"]


def test_calculate_castability_v5(mock_metrics):
    advisor = DraftAdvisor(mock_metrics, [])
    advisor.main_colors = ["W", "U"]
    advisor.pool_metrics = {"fixing_count": 0}

    # On lane card
    mult, _ = advisor._calculate_castability_v5(
        {"colors": ["W"]}, pack=2, pick=1, z_score=0.0
    )
    assert mult == 1.0

    # Off lane card, double pip (uncastable)
    mult, _ = advisor._calculate_castability_v5(
        {"colors": ["B"], "mana_cost": "{B}{B}"}, pack=2, pick=1, z_score=0.0
    )
    assert mult == 0.01

    # Splashable bomb
    mult, _ = advisor._calculate_castability_v5(
        {"colors": ["R"], "mana_cost": "{R}"}, pack=2, pick=1, z_score=2.0
    )

    # Without fixing in the pool, it's heavily penalized even if it's a bomb
    assert mult == 0.05


def test_wheel_chance(mock_metrics):
    advisor = DraftAdvisor(mock_metrics, [])
    # Should wheel if ALSA is greater than the current pick
    pct = advisor._wheel_chance(
        {"deck_colors": {"All Decks": {"alsa": 10.0}}}, pick=2, rank_in_pack=5
    )

    assert pct > 0.0


@pytest.mark.parametrize("pick, pack_size", [(6, 8), (7, 8), (8, 7)])
def test_wheel_chance_needs_nine_cards(mock_metrics, pick, pack_size):
    """A pack with fewer than 9 cards can't come back, whatever the pick."""
    advisor = DraftAdvisor(mock_metrics, [])
    pct = advisor._wheel_chance(
        {"deck_colors": {"All Decks": {"alsa": 8.5}}},
        pick=pick,
        rank_in_pack=5,
        pack_size=pack_size,
    )

    assert pct == 0.0


def test_wheel_chance_allows_last_wheelable_pick(mock_metrics):
    advisor = DraftAdvisor(mock_metrics, [])
    pct = advisor._wheel_chance(
        {"deck_colors": {"All Decks": {"alsa": 8.5}}},
        pick=6,
        rank_in_pack=5,
        pack_size=9,
    )

    assert pct > 0.0


@pytest.mark.parametrize("pack_size, wheels", [(8, False), (9, True)])
def test_evaluate_pack_wheel_chance_uses_pack_size(mock_metrics, pack_size, wheels):
    """Pick 7 of a 14-card pack (8 cards) can't wheel; pick 7 of 15 (9 cards) can."""
    advisor = DraftAdvisor(mock_metrics, [])
    pack = [
        {
            "name": f"Filler{i}",
            "colors": ["G"],
            "types": ["Creature"],
            "cmc": 2,
            "deck_colors": {"All Decks": {"gihwr": 50.0, "alsa": 8.5}},
        }
        for i in range(pack_size)
    ]

    recs = advisor.evaluate_pack(pack, current_pick=7)

    assert any(r.wheel_chance > 0 for r in recs) is wheels


def test_wheel_chance_does_not_change_score(mock_metrics):
    """The wheel chance is shown, but a likely wheel isn't marked down."""
    advisor = DraftAdvisor(mock_metrics, [])
    pack = [
        {
            "name": f"Card{i}",
            "colors": ["G"],
            "types": ["Creature"],
            "cmc": 3,
            "deck_colors": {"All Decks": {"gihwr": 55.0, "alsa": alsa}},
        }
        for i, alsa in enumerate([1.5, 1.5, 1.5, 1.5, 1.5, 12.0, 12.0, 12.0, 12.0])
    ]

    recs = {r.card_name: r for r in advisor.evaluate_pack(pack, current_pick=2)}

    assert recs["Card8"].wheel_chance >= 75.0
    assert recs["Card8"].contextual_score == recs["Card0"].contextual_score


def test_evaluate_pack_elite_detection(mock_metrics):
    # Establish a baseline pool
    pool = [
        {
            "name": "Grizzly Bears",
            "colors": ["G"],
            "types": ["Creature"],
            "cmc": 2,
            "deck_colors": {"All Decks": {"gihwr": 55.0}},
        }
    ] * 10
    advisor = DraftAdvisor(mock_metrics, pool)

    # Construct a pack with a massive outlier (Bomb) and filler
    pack = [
        {
            "name": "Bomb",
            "colors": ["G"],
            "types": ["Creature"],
            "cmc": 4,
            "deck_colors": {"All Decks": {"gihwr": 75.0, "iwd": 5.0, "alsa": 2.0}},
        },
        {
            "name": "Filler1",
            "colors": ["G"],
            "types": ["Creature"],
            "cmc": 2,
            "deck_colors": {"All Decks": {"gihwr": 50.0, "iwd": 1.0, "alsa": 4.0}},
        },
        {
            "name": "Filler2",
            "colors": ["G"],
            "types": ["Creature"],
            "cmc": 2,
            "deck_colors": {"All Decks": {"gihwr": 50.0, "iwd": 1.0, "alsa": 4.0}},
        },
        {
            "name": "Filler3",
            "colors": ["G"],
            "types": ["Creature"],
            "cmc": 2,
            "deck_colors": {"All Decks": {"gihwr": 50.0, "iwd": 1.0, "alsa": 4.0}},
        },
    ]

    recs = advisor.evaluate_pack(pack, current_pick=1)

    assert len(recs) == 4
    assert recs[0].card_name == "Bomb"
    # Elite designation triggers because Z-score > 1.5, IWD > 4.5, and it is on-color
    assert recs[0].is_elite is True


def _white_blue_advisor(metrics):
    """An advisor whose pool leads in white-blue."""
    pool = [
        {"colors": ["W"], "deck_colors": {"All Decks": {"gihwr": 62.0}}}
        for _ in range(4)
    ] + [
        {"colors": ["U"], "deck_colors": {"All Decks": {"gihwr": 60.0}}}
        for _ in range(3)
    ]
    advisor = DraftAdvisor(metrics, pool)
    assert advisor.main_archetype == "WU"
    return advisor


def _white_card(name, pair_wr):
    """A white common with a GIH WR of 55 overall and pair_wr in WU decks."""
    return {
        "name": name,
        "colors": ["W"],
        "types": ["Creature"],
        "cmc": 2,
        "rarity": "common",
        "deck_colors": {
            "All Decks": {"gihwr": 55.0},
            "WU": {"gihwr": pair_wr, "samples": 1000},
        },
    }


@pytest.mark.parametrize(
    "pick,expected", [(1, 59.7), (13, 68.1), (15, 69.5), (30, 69.5)]
)
def test_archetype_weight_ramps_within_the_pack(mock_metrics, pick, expected):
    """The archetype's edge is weighted 0.65 at a pack's first pick and 1.21 at
    its 13th, the last choice in a 14-card pack. It stops at 1.3, at pick 15."""
    advisor = DraftAdvisor(mock_metrics, [])
    advisor.main_archetype = "WU"
    card = _white_card("Glue", 59.0)

    # The mean is 55 and the SD 4, and a score is 50 + 15 points per SD.
    # Pick 1: 55 + 0.647 * (59 - 55) = 57.6, 0.65 SD up: 50 + 0.65 * 15 = 59.7.
    # Pick 13: 55 + 1.207 * (59 - 55) = 59.8, 1.21 SD up: 50 + 1.21 * 15 = 68.1.
    # Pick 15: 55 + 1.3 * (59 - 55) = 60.2, 1.3 SD up: 50 + 1.3 * 15 = 69.5.
    assert advisor._calculate_weighted_score(card, pick) == pytest.approx(
        expected, abs=0.05
    )


@pytest.mark.parametrize(
    "pick,cards_per_pick,points",
    [(1, 1, 9.7), (6, 1, 13.2), (1, 2, 9.7), (6, 2, 16.7), (7, 2, 18.1)],
)
def test_pick_two_weighs_a_pick_by_the_cards_gone(
    mock_metrics, pick, cards_per_pick, points
):
    """Pick-Two drafts take two cards a pick, so their pick 6 weighs the
    archetype like pick 11 of a one-card draft: 10 cards have left the pack."""
    advisor = _white_blue_advisor(mock_metrics)
    pack = [_white_card("Glue", 59.0), _white_card("Plain", 55.0)]

    recs = advisor.evaluate_pack(pack, pick, cards_per_pick=cards_per_pick)

    # The edge is one SD, so it scores 15 points times the weight: 0.647 at
    # pick 1, 0.88 at pick 6, 1.113 at pick 11 and 1.207 at pick 13.
    glue = next(r for r in recs if r.card_name == "Glue")
    assert f"Better in WU (+{points})" in glue.reasoning


def test_evaluate_pack_counts_the_archetype_edge_once(mock_metrics):
    """A card that does better in the lane's pair gains only through the
    archetype weight, with no glue or synergy bonus on top, and says so."""
    advisor = _white_blue_advisor(mock_metrics)
    glue, plain = _white_card("Glue", 59.0), _white_card("Plain", 55.0)
    recs = {r.card_name: r for r in advisor.evaluate_pack([glue, plain], 1)}

    # The two cards get the same multipliers, so their scores differ only by
    # their base scores, 59.7 against 50. The old glue bonus added 20 more.
    ratio = advisor._calculate_weighted_score(
        glue, 1
    ) / advisor._calculate_weighted_score(plain, 1)
    assert recs["Glue"].contextual_score == pytest.approx(
        recs["Plain"].contextual_score * ratio, abs=0.1
    )
    assert "Better in WU (+9.7)" in recs["Glue"].reasoning
    assert not any("WU" in r for r in recs["Plain"].reasoning)


def test_composition_bonus_heuristics(mock_metrics):
    advisor = DraftAdvisor(mock_metrics, [])

    # Setup pool metrics to trigger specific heuristic thresholds
    advisor.pool_metrics = {
        "heavy_drops": 4,
        "creature_count": 5,
        "artifacts": 4,
        "graveyard_enablers": 3,
        "counters_enablers": 3,
        "fixing_count": 0,
        "off_color_playables": 2,
        "splash_targets": ["U"],
        "hard_removal_count": 1,
        "early_plays": 2,
    }
    advisor.TOTAL_PICKS = 45
    advisor.pool = [1] * 20  # Simulate mid-draft (Pick 20)

    # 1. Heavy Drops Penalty
    mult, reason = advisor._calculate_composition_bonus(
        {"cmc": 6, "types": ["Creature"]}, pack=2
    )
    assert mult == 0.7
    assert "Curve Too Heavy" in reason

    # 2. Creature Quota Bonus
    mult, reason = advisor._calculate_composition_bonus(
        {"cmc": 3, "types": ["Creature"]}, pack=2
    )
    assert mult == 1.25
    assert "Critical: Needs Creatures" in reason

    # 3. Artifact Synergy
    mult, reason = advisor._calculate_composition_bonus(
        {"cmc": 3, "tags": ["synergy_artifacts"]}, pack=2
    )
    assert mult == 1.2
    assert "Artifact Synergy" in reason

    # 4. Fixing Hunger (Because off_color_playables > fixing_count)
    mult, reason = advisor._calculate_composition_bonus({"types": ["Land"]}, pack=2)
    assert mult == 1.4
    assert "Critical: Needs Fixing" in reason

    # 5. Removal Hunger
    mult, reason = advisor._calculate_composition_bonus({"tags": ["removal"]}, pack=2)
    assert mult == 1.3
    assert "Critical: Needs Removal" in reason

import pytest
from unittest.mock import MagicMock
from src.advisor.engine import DraftAdvisor
from src.advisor.schema import Recommendation


@pytest.fixture
def mock_metrics():
    metrics = MagicMock()
    # Mocking format_texture for VOR (Value Over Replacement) tests
    metrics.format_texture = {
        "R": {"2-drop": 1, "removal": 10},  # Extremely scarce red 2-drops
        "G": {"2-drop": 10, "removal": 1},  # Extremely scarce green removal
    }
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


def test_check_relative_wheel(mock_metrics):
    advisor = DraftAdvisor(mock_metrics, [])
    # Should wheel if ALSA is greater than the current pick
    mult, reason, pct = advisor._check_relative_wheel(
        {"deck_colors": {"All Decks": {"alsa": 10.0}}}, pick=2, rank_in_pack=5
    )

    assert pct > 0.0
    assert mult == 0.8
    assert "Wheels" in reason


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


def test_evaluate_value_over_replacement(mock_metrics):
    advisor = DraftAdvisor(mock_metrics, [])
    advisor.main_colors = ["R"]
    advisor.global_mean = 55.0
    advisor.global_std = 4.0

    # A playable red 2-drop. Because we defined Red 2-drops as incredibly scarce
    # in the mock_metrics fixture above, this card should trigger a VOR bonus!
    pack = [
        {
            "name": "Scarce Red 2-Drop",
            "colors": ["R"],
            "types": ["Creature"],
            "cmc": 2,
            "tags": ["evasion"],
            "deck_colors": {"All Decks": {"gihwr": 54.0}},
        }
    ]

    recs = advisor.evaluate_pack(pack, current_pick=1)

    assert len(recs) == 1
    assert any("High VOR: Scarce R 2-Drops" in reason for reason in recs[0].reasoning)


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


# --- B1: draft-wide progress from the controller's locked scanner snapshot ---

def _metrics_54_4():
    from unittest.mock import MagicMock

    m = MagicMock()
    m.get_metrics.return_value = (54.0, 4.0)
    return m


def _rg_pool(n, gihwr=54.0):
    return [
        {"name": f"RG Card {i}", "colors": ["R", "G"], "types": ["Creature"], "cmc": 3,
         "deck_colors": {"All Decks": {"gihwr": gihwr}}}
        for i in range(n)
    ]


def _arch_card():
    return {
        "name": "Arch Card", "colors": ["R", "G"], "types": ["Creature"], "cmc": 3,
        "deck_colors": {
            "All Decks": {"gihwr": 54.0, "samples": 10 ** 9},
            "RG": {"gihwr": 64.0, "samples": 10 ** 9},
        },
    }


@pytest.mark.parametrize(
    "picks,total,expected",
    [
        (31, 45, 0.6822),   # Premier P3P1, 30 raw IDs: progress = 30 + 1
        (16, 45, 0.4489),   # Premier P2P1, 15 raw IDs
        (1, 45, 0.2156),    # Premier P1P1
        (8, 21, 0.4667),    # Pick-Two P2P1: 7 picks / 14 raw IDs, 21-pick format
        (21, 21, 0.9),      # Pick-Two last pick: cap reached exactly
        (22, 21, 0.9),      # Pick-Two after the last pick completes: clamped back
        (45, 45, 0.9),      # Premier cap reached exactly
        (46, 45, 0.9),      # Premier clamped
    ],
)
def test_draft_progress_arch_weight_values(picks, total, expected):
    """arch_weight = min(0.9, 0.2 + (progress / total_picks) * 0.7), with progress
    supplied by the controller (raw picked-ID count // cards_per_pick + 1) and
    total_picks from the draft format. The raw 30 -> progress 31 convention is
    pinned by the first case."""
    advisor = DraftAdvisor(
        _metrics_54_4(),
        _rg_pool(12),
        draft_progress={"picks": picks, "total_picks": total, "cards": 45, "total_cards": 45},
    )
    clamped = max(1, min(total, advisor._progress_picks))
    base = advisor._calculate_weighted_score(_arch_card(), clamped)
    w = (base - 50.0) / 37.5  # global 54 == mean, arch delta 10, std 4 -> 15*10/4
    assert w == pytest.approx(expected, abs=1e-4)


def test_progress_invariant_under_metadata_resolution():
    """30 raw picked IDs with one unresolved: whether 29 or 30 cards have resolved
    metadata, the recommendations must not move — progress derives from the raw
    count, never from the filtered pool."""
    pack = [
        _arch_card(),
        {"name": "Pack Card B", "colors": ["G"], "types": ["Creature"], "cmc": 4,
         "deck_colors": {"All Decks": {"gihwr": 55.0}}},
    ]
    progress = {"picks": 31, "total_picks": 45, "cards": 30, "total_cards": 45}

    def scores(pool):
        advisor = DraftAdvisor(_metrics_54_4(), pool, draft_progress=progress)
        return [r.contextual_score for r in advisor.evaluate_pack(pack, 1, current_pack=3)]

    before = scores(_rg_pool(29))
    after = scores(_rg_pool(30))
    assert before == after

    legacy = DraftAdvisor(_metrics_54_4(), _rg_pool(29))
    legacy_scores = [r.contextual_score for r in legacy.evaluate_pack(pack, 1, current_pack=3)]
    assert legacy_scores != before  # the legacy pi=1 ramp (0.2156) is the B1 defect


def test_pack3_deck_scoring_gate_uses_raw_card_count():
    """The pack-3 deck-scoring gate counts raw picked IDs: 22 resolved cards with
    23 raw picks opens the gate; the filtered pool alone (22) must not."""
    pack = [{"name": "Pack Card", "colors": ["R"], "types": ["Creature"], "cmc": 2,
             "deck_colors": {"All Decks": {"gihwr": 57.0}}}]

    open_advisor = DraftAdvisor(
        _metrics_54_4(), _rg_pool(22, gihwr=60.0),
        draft_progress={"picks": 24, "total_picks": 45, "cards": 23, "total_cards": 45},
    )
    open_advisor.evaluate_pack(pack, 1, current_pack=3)
    assert open_advisor.base_deck_score > 0

    closed_advisor = DraftAdvisor(
        _metrics_54_4(), _rg_pool(22, gihwr=60.0),
        draft_progress={"picks": 23, "total_picks": 45, "cards": 22, "total_cards": 45},
    )
    closed_advisor.evaluate_pack(pack, 1, current_pack=3)
    assert closed_advisor.base_deck_score == 0.0


def test_wheel_logic_keeps_pack_local_pick():
    """The wheel path consumes the pack-local pick, never the draft-wide progress:
    deep and early progress must produce identical wheel output at the same
    pack-local pick, and picks 9+ short-circuit to 0."""
    pack = [
        {"name": "Wheel Bait", "colors": ["R"], "types": ["Creature"], "cmc": 2,
         "deck_colors": {"All Decks": {"gihwr": 54.0, "alsa": 8.5}}},
        {"name": "Plain", "colors": ["G"], "types": ["Creature"], "cmc": 3,
         "deck_colors": {"All Decks": {"gihwr": 54.0, "alsa": 2.0}}},
    ]

    def wheel(picks):
        advisor = DraftAdvisor(
            _metrics_54_4(), _rg_pool(12),
            draft_progress={"picks": picks, "total_picks": 45, "cards": 45, "total_cards": 45},
        )
        recs = advisor.evaluate_pack(pack, 3, current_pack=2)
        return {r.card_name: r.wheel_chance for r in recs}

    early, deep = wheel(3), wheel(43)
    assert early == deep
    assert early["Wheel Bait"] > 0.0  # wheel logic is live in pack 2 at pick 3

    advisor = DraftAdvisor(
        _metrics_54_4(), _rg_pool(12),
        draft_progress={"picks": 12, "total_picks": 45, "cards": 11, "total_cards": 45},
    )
    recs = advisor.evaluate_pack(pack, 9, current_pack=2)
    assert all(r.wheel_chance == 0.0 for r in recs)


def test_projection_pair_documents_composition_semantics():
    """Projections are composition quantities: 10 creatures over 29 resolved cards
    project to 15.52; the same 10 after a noncreature resolves (30 resolved)
    project to 15.00. Only progress-derived terms are resolution-invariant."""
    advisor = DraftAdvisor(
        _metrics_54_4(), _rg_pool(29),
        draft_progress={"picks": 31, "total_picks": 45, "cards": 30, "total_cards": 45},
    )
    assert advisor._projected_total(10) == pytest.approx(10 * 45 / 29, abs=1e-4)

    advisor_after = DraftAdvisor(
        _metrics_54_4(), _rg_pool(30),
        draft_progress={"picks": 31, "total_picks": 45, "cards": 30, "total_cards": 45},
    )
    assert advisor_after._projected_total(10) == pytest.approx(15.0, abs=1e-4)


# --- B2: lookahead improvement must not be contaminated by the pool-size step ---


def _stepping_pool():
    """23 resolved cards: adding one more steps expected_spells (int(23*23/42)=12
    -> int(23*24/42)=13), so the completeness penalty differs by a constant 10
    between base and lookahead scorings on the parent."""
    return _rg_pool(23, gihwr=60.0)


def _true_improver():
    return {
        "name": "True Improver", "colors": ["R", "G"], "types": ["Creature"], "cmc": 2,
        "deck_colors": {
            "All Decks": {"gihwr": 75.0, "samples": 5000},
            "RG": {"gihwr": 75.0, "samples": 1000},
        },
    }


def test_lookahead_uses_constant_pool_size_for_both_scorings():
    """At a stepping pool size the lookahead must score the +1 pool with the
    BASELINE's pool_size: the emitted improvement bonus equals 3x the true deck
    gain, without the -10-per-step contamination."""
    import re as _re

    pool = _stepping_pool()
    advisor = DraftAdvisor(
        _metrics_54_4(), pool,
        draft_progress={"picks": 25, "total_picks": 45, "cards": 24, "total_cards": 45},
    )
    recs = advisor.evaluate_pack([_true_improver()], 1, current_pack=3)
    assert advisor.color_options  # gate open (24 raw >= 23)

    base = advisor._get_fast_best_deck_score(pool, advisor.color_options, pool_size=23)
    new = advisor._get_fast_best_deck_score(
        pool + [_true_improver()], advisor.color_options, pool_size=23
    )
    true_gain = new - base
    assert true_gain > 0.1  # the card genuinely improves the deck

    bonus_texts = [
        r for rec in recs for r in rec.reasoning if "Improves Best Deck" in r
    ]
    assert bonus_texts, "real deck-improver must earn the improvement bonus"
    emitted = float(_re.search(r"\(([+-]?\d+\.\d)\)", bonus_texts[0]).group(1))
    assert emitted == pytest.approx(true_gain * 3.0, abs=0.05)


def test_junk_card_earns_no_improvement_bonus_at_stepping_size():
    """A junk card at a stepping pool size must not earn the bonus (the gate
    already clamps negative deltas end-to-end; this pins the intent)."""
    junk = {
        "name": "Junk", "colors": ["R", "G"], "types": ["Creature"], "cmc": 7,
        "deck_colors": {"All Decks": {"gihwr": 30.0}},
    }
    advisor = DraftAdvisor(
        _metrics_54_4(), _stepping_pool(),
        draft_progress={"picks": 25, "total_picks": 45, "cards": 24, "total_cards": 45},
    )
    recs = advisor.evaluate_pack([junk], 1, current_pack=3)
    assert not [r for rec in recs for r in rec.reasoning if "Improves Best Deck" in r]


# --- B8: castability discount applied once; color-specific splash gate ---


class _FixMetrics:
    """Metrics stub with fixed (mean, std)."""

    def __init__(self, mean=55.0, std=4.0):
        self._pair = (mean, std)

    def get_metrics(self, *a, **k):
        return self._pair


def _bomb_with_single_u_pip():
    return {
        "name": "U Pip Bomb", "colors": ["U"], "types": ["Creature"], "cmc": 4,
        "mana_cost": "{3}{U}",
        # z = (63 - 55) / 4 = 2.0 >= BOMB_Z_SCORE
        "deck_colors": {"All Decks": {"gihwr": 63.0, "samples": 5000}},
    }


def _gw_lane_pool(dual_colors=("G", "W"), duals=3):
    """GBW-free Gruul lane pool with `duals` multicolor lands of dual_colors."""
    pool = [
        {"name": f"RG Spell {i}", "colors": ["R", "G"], "types": ["Creature"], "cmc": 3,
         "mana_cost": "{1}{R}{G}", "deck_colors": {"All Decks": {"gihwr": 56.0}}}
        for i in range(18)
    ]
    pool += [
        {"name": f"Dual {dual_colors[0]}{dual_colors[1]} {i}", "colors": list(dual_colors),
         "types": ["Land"], "deck_colors": {"All Decks": {"gihwr": 55.0}}}
        for i in range(duals)
    ]
    return pool


def test_color_blind_fixing_does_not_unlock_bomb_splash():
    """Three G/W duals raise fixing_count to 3 but fix nothing blue: the bomb
    splash gate must require per-color fixing for the splash colors too."""
    advisor = DraftAdvisor(_FixMetrics(), _gw_lane_pool(("G", "W"), duals=3))
    advisor.main_colors = ["R", "G"]
    advisor.pool_metrics["fixing_count"] = 3
    mult, reason = advisor._calculate_castability_v5(
        _bomb_with_single_u_pip(), pack=2, pick=1, z_score=2.0
    )
    assert reason != "Bomb Splash"
    assert mult < 0.45


def test_specific_fixing_with_rich_pool_unlocks_bomb_splash():
    """The conjunction: per-color fixing present AND fixing_count over the pack
    threshold (3 before pack 3, 4 in pack 3)."""
    advisor = DraftAdvisor(_FixMetrics(), _gw_lane_pool(("G", "U"), duals=3))
    advisor.main_colors = ["R", "G"]
    advisor.pool_metrics["fixing_count"] = 3

    mult, reason = advisor._calculate_castability_v5(
        _bomb_with_single_u_pip(), pack=2, pick=1, z_score=2.0
    )
    assert (mult, reason) == (0.45, "Bomb Splash")

    mult, reason = advisor._calculate_castability_v5(
        _bomb_with_single_u_pip(), pack=3, pick=1, z_score=2.0
    )
    assert reason != "Bomb Splash"  # pack 3 needs 4 total

    advisor.pool_metrics["fixing_count"] = 4
    mult, reason = advisor._calculate_castability_v5(
        _bomb_with_single_u_pip(), pack=3, pick=1, z_score=2.0
    )
    assert (mult, reason) == (0.35, "Bomb Splash")


def test_deck_improvement_bonus_not_discounted_by_castability(monkeypatch):
    """The improvement bonus joins the score after the castability multiplier:
    halving castability must halve every other term but keep the bonus whole —
    ctx(0.5) - 0.5*ctx(1.0) == 0.5*bonus > 0."""
    pool = [
        {"name": f"WB Spell {i}", "colors": ["W", "B"], "types": ["Creature"], "cmc": 3,
         "mana_cost": "{1}{W}{B}",
         "deck_colors": {"All Decks": {"gihwr": 60.0, "samples": 5000}}}
        for i in range(23)
    ]
    improver = {
        "name": "W Splash Improver", "colors": ["W"], "types": ["Creature"], "cmc": 2,
        "mana_cost": "{1}{W}",
        "deck_colors": {"All Decks": {"gihwr": 72.0, "samples": 5000}},
    }
    pool += [
        {"name": f"Dual BW {i}", "colors": ["B", "W"], "types": ["Land"],
         "deck_colors": {"All Decks": {"gihwr": 55.0}}}
        for i in range(3)
    ]

    def run(cast_mult):
        advisor = DraftAdvisor(_FixMetrics(), pool)
        monkeypatch.setattr(
            DraftAdvisor,
            "_calculate_castability_v5",
            lambda self, *a, **k: (cast_mult, ""),
        )
        recs = advisor.evaluate_pack([improver], 1, current_pack=3)
        monkeypatch.undo()
        assert recs
        assert any("Improves Best Deck" in r for rec in recs for r in rec.reasoning)
        return recs[0].contextual_score

    ctx_one, ctx_half = run(1.0), run(0.5)
    assert ctx_half - 0.5 * ctx_one > 0.05


# --- Cycle 2 item 1b: reliability on raw-rate bonus paths ---


def test_small_sample_bomb_cannot_buy_its_bonus_back():
    """Two identical bombs differing only in sample count: the ten-game spike
    loses its raw-rate power bonus (bomb z-score path), the 50k-game one
    keeps it."""
    def bomb(samples):
        return {
            "name": f"Bomb s{samples}", "colors": ["R"], "types": ["Creature"],
            "cmc": 4, "mana_cost": "{3}{R}",
            "deck_colors": {"All Decks": {"gihwr": 63.0, "samples": samples}},
        }

    pool = [
        {"name": f"RG {i}", "colors": ["R", "G"], "types": ["Creature"], "cmc": 3,
         "deck_colors": {"All Decks": {"gihwr": 54.0, "samples": 10 ** 9}}}
        for i in range(12)
    ]
    filler = {
        "name": "Filler", "colors": ["R"], "types": ["Creature"], "cmc": 2,
        "mana_cost": "{1}{R}", "deck_colors": {"All Decks": {"gihwr": 54.0}},
    }
    pack = [bomb(10), bomb(50000), filler, filler, filler]
    advisor = DraftAdvisor(
        _FixMetrics(), pool,
        draft_progress={"picks": 10, "total_picks": 45, "cards": 9, "total_cards": 45},
    )
    recs = {r.card_name: r.contextual_score for r in advisor.evaluate_pack(pack, 1, current_pack=1)}
    assert recs["Bomb s50000"] > recs["Bomb s10"] + 3.0


# --- Cycle 2 item 1d: n=0 state matrix, Day-1 heuristic routing ---


def test_day_one_set_routes_through_heuristic_evaluator():
    """No dataset win rates at all: every card is priced by the same
    HeuristicEvaluator deck_scorer uses, so a premium removal rare outranks a
    vanilla common and the score follows the mapped formula exactly."""
    from unittest.mock import MagicMock

    from src.sealed_logic import HeuristicEvaluator

    metrics = MagicMock()
    metrics.get_metrics.return_value = (0, 0)  # day-1 set: no data
    pool = [
        {"name": f"Any {i}", "colors": ["R"], "types": ["Creature"], "cmc": 3,
         "deck_colors": {}}
        for i in range(12)
    ]
    advisor = DraftAdvisor(
        metrics, pool,
        draft_progress={"picks": 2, "total_picks": 45, "cards": 1, "total_cards": 45},
    )
    assert advisor.set_has_data is False

    removal_rare = {
        "name": "Premium Removal", "colors": ["B"], "types": ["Instant"], "cmc": 2,
        "rarity": "rare", "tags": ["removal"], "deck_colors": {},
    }
    vanilla_common = {
        "name": "Vanilla", "colors": ["B"], "types": ["Creature"], "cmc": 3,
        "rarity": "common", "deck_colors": {},
    }
    recs = {
        r.card_name: r
        for r in advisor.evaluate_pack([removal_rare, vanilla_common], 1, current_pack=1)
    }
    h = HeuristicEvaluator.evaluate(removal_rare)
    expected_base = 50.0 + ((h - 54.0) / 4.0) * 15.0
    assert advisor._calculate_weighted_score(removal_rare, 1) == pytest.approx(
        expected_base
    )
    assert recs["Premium Removal"].contextual_score > recs["Vanilla"].contextual_score


def test_established_set_with_card_without_data_scores_zero():
    """State 2: the set has data but the card has none of its own — the
    conservative 0.0 sentinel, never an invented metadata score."""
    metrics = MagicMock()
    metrics.get_metrics.return_value = (54.0, 4.0)
    pool = [
        {"name": f"RG {i}", "colors": ["R", "G"], "types": ["Creature"], "cmc": 3,
         "deck_colors": {"All Decks": {"gihwr": 54.0, "samples": 10 ** 9}}}
        for i in range(12)
    ]
    advisor = DraftAdvisor(metrics, pool)
    card = {
        "name": "No Data", "colors": ["R", "G"], "types": ["Creature"], "cmc": 3,
        "rarity": "mythic", "deck_colors": {},
    }
    base = advisor._calculate_weighted_score(card, 10)
    # mapped from a 0.0 WR: 50 + ((0-54)/4)*15 = -152.5, clamped to 0
    assert base == 0.0


# --- Cycle 3 item 3.5: lookahead caching (heuristic-only path) ---


def test_lookahead_cache_hits_on_second_evaluation():
    """Same pool + card twice: the second evaluation must not re-run the deck
    scoring (the cache serves it), and the bonus is identical."""
    from unittest.mock import patch

    pool = [
        {"name": f"WB Spell {i}", "colors": ["W", "B"], "types": ["Creature"],
         "cmc": 3, "mana_cost": "{1}{W}{B}",
         "deck_colors": {"All Decks": {"gihwr": 60.0, "samples": 10 ** 9}}}
        for i in range(23)
    ]
    improver = {
        "name": "W Splash Improver", "colors": ["W"], "types": ["Creature"],
        "cmc": 2, "mana_cost": "{1}{W}",
        "deck_colors": {"All Decks": {"gihwr": 72.0, "samples": 10 ** 9}},
    }
    pool += [
        {"name": f"Dual BW {i}", "colors": ["B", "W"], "types": ["Land"],
         "deck_colors": {"All Decks": {"gihwr": 55.0}}}
        for i in range(3)
    ]

    from src.advisor.engine import _LOOKAHEAD_CACHE

    _LOOKAHEAD_CACHE.clear()  # module-level: an earlier test may share the signature
    calls = []
    advisor = DraftAdvisor(_FixMetrics(), pool)
    real = DraftAdvisor._get_fast_best_deck_score

    def spy(self, pool_, options, pool_size=None):
        if len(pool_) == len(pool) + 1:  # the lookahead call, not base scoring
            calls.append(1)
        return real(self, pool_, options, pool_size=pool_size)

    with patch.object(DraftAdvisor, "_get_fast_best_deck_score", spy):
        first = advisor.evaluate_pack([improver], 1, current_pack=3)
        advisor2 = DraftAdvisor(_FixMetrics(), pool)
        second = advisor2.evaluate_pack([improver], 1, current_pack=3)

    assert first[0].contextual_score == second[0].contextual_score
    assert len(calls) >= 1  # first run scored
    baseline_calls = len(calls)
    advisor3 = DraftAdvisor(_FixMetrics(), pool)
    with patch.object(DraftAdvisor, "_get_fast_best_deck_score", spy):
        third = advisor3.evaluate_pack([improver], 1, current_pack=3)
    assert len(calls) == baseline_calls  # served from cache, no re-scoring
    assert third[0].contextual_score == first[0].contextual_score

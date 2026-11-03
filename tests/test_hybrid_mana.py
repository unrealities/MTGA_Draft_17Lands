"""Hybrid symbols offer alternative payments, never conjunctive colors."""

from collections import Counter
from unittest.mock import Mock

import pytest

from src.advisor.engine import DraftAdvisor
from src.advisor.mana_base import calculate_dynamic_mana_base, is_castable, get_strict_colors
from src.advisor import deck_builder as db
from src.configuration import Configuration


def spell(name, cost, colors, cmc=3, wr=55.0):
    return {"name": name, "mana_cost": cost, "colors": colors, "cmc": cmc,
            "types": ["Creature"], "deck_colors": {"All Decks": {"gihwr": wr}}}


@pytest.fixture
def metrics():
    result = Mock()
    result.get_metrics.return_value = (55.0, 4.0)
    return result


@pytest.mark.parametrize("cost,colors,plain_cost", [
    ("{2}{G/U}", ["G", "U"], "{2}{G}"),
    ("{2}{U/G}", ["U", "G"], "{2}{G}"),
    ("{2/U}", ["U"], "{2}"),
])
@pytest.mark.parametrize("pack", [1, 2, 3])
def test_payable_hybrid_gets_same_lane_treatment(metrics, cost, colors, plain_cost, pack):
    advisor = DraftAdvisor(metrics, [])
    advisor.main_colors = ["G", "R"]
    hybrid = spell("Hybrid", cost, colors)
    plain = spell("Plain", plain_cost, ["G"] if "G" in plain_cost else [])
    assert is_castable(hybrid, ["G", "R"])
    recs = {r.card_name: r for r in advisor.evaluate_pack([hybrid, plain], 10, pack)}
    assert recs["Hybrid"].contextual_score == recs["Plain"].contextual_score


@pytest.mark.parametrize("cost,fixing,expected", [
    ("{2}{U/R}", {"R": 1}, 0.45),
    ("{2}{R/U}", {"U": 1}, 0.45),
    ("{2}{U/R}", {}, 0.05),
    ("{2}{U/R}", {"G": 4}, 0.05),  # quantity of wrong-color fixing is irrelevant
    ("{G/U}{B}", {"U": 1}, 0.05),  # on-lane hybrid cannot excuse a black pip
    ("{U}{R}", {"R": 1}, 0.01),    # genuine gold still requires both colors
])
def test_splash_requires_a_payable_route_for_each_symbol(metrics, cost, fixing, expected):
    advisor = DraftAdvisor(metrics, [])
    advisor.main_colors = ["W", "G"]
    advisor.fixing_map = fixing
    advisor.pool_metrics["fixing_count"] = sum(fixing.values())
    card = spell("Splash", cost, list({p for p in cost if p in "WUBRG"}))
    assert advisor._calculate_castability_v5(card, 2, 1, 2.0)[0] == expected


def test_two_brid_does_not_force_an_off_color_basic():
    spells = [spell("Green", "{2}{G}", ["G"])] * 15
    spells += [spell("Optional blue", "{2/U}", ["U"], cmc=2)] * 8
    lands = calculate_dynamic_mana_base(spells, [], ["G"], 17)
    assert Counter(c["name"] for c in lands) == {"Forest": 17}


def test_hybrid_only_color_cover_is_order_independent():
    a = spell("A", "{W/U}", ["W", "U"], 1)
    b = spell("B", "{U/B}", ["U", "B"], 1)
    assert get_strict_colors([a, b]) == ["U"]
    assert get_strict_colors([b, a]) == ["U"]


def test_builder_does_not_label_or_penalize_a_hybrid_as_a_third_color(metrics, monkeypatch):
    pool = [spell(f"Red {i}", "{2}{R}", ["R"]) for i in range(19)]
    pool += [spell(f"Hybrid {i}", "{2}{G/U}", ["G", "U"]) for i in range(4)]
    monkeypatch.setattr(db, "identify_top_pairs", lambda *a: [["R", "G"]])
    monkeypatch.setattr(db, "build_variant_consistency", lambda *a: pool)
    monkeypatch.setattr(db, "build_variant_curve", lambda *a: [])
    monkeypatch.setattr(db, "build_variant_greedy", lambda *a: ([], None))
    monkeypatch.setattr(db, "build_variant_soup", lambda *a: ([], []))
    monkeypatch.setattr(db, "simulate_deck", lambda *a, **kw: None)
    db.clear_deck_cache()
    try:
        builds = db.suggest_deck(pool, metrics, Configuration())
    finally:
        db.clear_deck_cache()
    assert len(builds) == 1
    data = next(iter(builds.values()))
    assert set(data["colors"]) == {"G", "R"}
    assert set(data["identity_colors"]) == {"G", "R"}
    assert "Greedy Mana Strain" not in data["breakdown"]
    assert "Rock-Solid Mana" in data["breakdown"]


def test_greedy_builder_accepts_one_supported_hybrid_splash(metrics):
    pool = [spell(f"Green {i}", "{2}{G}", ["G"], wr=56.0) for i in range(23)]
    pool += [spell("Hybrid bomb", "{2}{U/R}", ["U", "R"], wr=68.0)]
    pool += [{"name": "Red fixer", "types": ["Land"], "colors": ["R"],
              "tags": ["fixing_ramp"], "text": "{T}: Add {R}."}]
    deck, splash = db.build_variant_greedy(pool, ["W", "G"], metrics)
    assert splash == "R"
    assert any(c["name"] == "Hybrid bomb" for c in deck)


def test_hybrid_helpers_do_not_change_card_colors():
    from src.mana_cost import mana_color_demand

    card = spell("Hybrid", "{G/U}", ["G", "U"], 1)
    assert is_castable(card, ["G"])
    assert mana_color_demand([card], ["G"])["U"] == 0
    assert card["colors"] == ["G", "U"]


def test_hybrid_demand_is_invariant_to_stacking_and_order():
    from src.mana_cost import mana_color_demand

    a = spell("A", "{W/U}", ["W", "U"], 1)
    b = spell("B", "{U/B}", ["U", "B"], 1)
    assert mana_color_demand([dict(a, count=4), b]) == mana_color_demand([b, a, a, a, a])
    assert mana_color_demand([a, b]) == {"W": 0, "U": 2, "B": 0, "R": 0, "G": 0}


def test_two_brid_simulation_counts_cheaper_blue_payment():
    from src.advisor.simulator import simulate_deck

    spell_card = spell("Two-brid", "{1}{2/U}", ["U"], 3)
    blue = [{"name": "Island", "types": ["Land"], "colors": ["U"], "count": 17},
            dict(spell_card, count=23)]
    red = [{"name": "Mountain", "types": ["Land"], "colors": ["R"], "count": 17},
           dict(spell_card, count=23)]
    assert simulate_deck(blue, iterations=1000)["cast_t2"] > 50.0
    assert simulate_deck(red, iterations=1000)["cast_t2"] == 0.0
    assert simulate_deck(red, iterations=1000)["cast_t3"] > 50.0


def test_simulator_payment_matches_independent_exhaustive_source_assignment():
    """Compare Hall matching/optional payments with direct source consumption.

    In particular one dual land cannot pay two hybrid symbols, and paying a
    two-brid symbol with two generic cannot reuse a source needed for {U}.
    """
    import itertools
    import re
    import numpy as np
    from src.advisor.simulator import (
        COLOR_BITS, MAX_PIPS, _fill_cover, _payment_size, parse_mana_cost,
    )

    def oracle(symbols, sources):
        if not symbols:
            return 0
        best = 1000
        for option in symbols[0].split("/"):
            if option.isdigit():
                n = int(option)
                for indices in itertools.combinations(range(len(sources)), n):
                    rest = [s for i, s in enumerate(sources) if i not in indices]
                    paid = oracle(symbols[1:], rest)
                    if paid >= 0:
                        best = min(best, paid + n)
            else:
                for i, source in enumerate(sources):
                    if source & COLOR_BITS[option]:
                        paid = oracle(symbols[1:], sources[:i] + sources[i + 1:])
                        if paid >= 0:
                            best = min(best, paid + 1)
        return best if best < 1000 else -1

    for cost in ("{G/U}{G}", "{2/U}{U}", "{2/U}{2/U}", "{1}{2/U}",
                 "{G/U}{U/R}", "{1}{U}{R}", "{G/U}{U/R}{G}", "{2/U}{2/U}{R}"):
        colored, generic = parse_mana_cost(cost)
        pips = np.zeros((1, MAX_PIPS), dtype=np.int32)
        pips[0, :len(colored)] = colored
        counts = np.array([len(colored)], dtype=np.int8)
        gen = np.array([generic], dtype=np.int8)
        for n in range(5):
            for sources in itertools.combinations_with_replacement([0, 2, 8, 16, 10], n):
                cover = np.zeros(32, dtype=np.int32)
                masks = np.array(sources, dtype=np.int32)
                _fill_cover(masks, n, cover)
                assert _payment_size(0, pips, counts, gen, n, cover) == oracle(
                    re.findall(r"\{(.*?)\}", cost), list(sources)
                ), (cost, sources)

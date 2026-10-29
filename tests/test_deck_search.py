"""Cycle 3: bounded search over the spells."""
import pytest
from unittest.mock import MagicMock

from src.advisor.deck_builder import (
    candidate_is_legal,
    hill_climb_search,
    search_neighbors,
    _search_score,
)
from src.advisor.engine import DraftAdvisor


def _metrics(mean=54.0, std=4.0):
    m = MagicMock()
    m.get_metrics.return_value = (mean, std)
    return m


def _creature(name, colors, wr, cmc=3, count=1):
    cost = "{" + "}{".join(colors * max(1, cmc - 1)) + "}" if colors else ""
    return {
        "name": name, "types": ["Creature"], "colors": colors, "cmc": cmc,
        "mana_cost": cost or "{0}", "count": count,
        "deck_colors": {"All Decks": {"gihwr": wr}},
    }


def _deck_entry(spells, lands_for):
    return spells + lands_for


# --- 3.1 legality ---


def test_legality_rejects_wrong_sizes_counts_and_copies():
    pool = [_creature(f"S{i}", ["U"], 56.0) for i in range(30)]
    legal23 = pool[:23] + [
        {"name": "Island", "types": ["Land", "Basic"], "colors": [], "count": 17}
    ]
    assert candidate_is_legal(legal23, pool)

    too_few = pool[:21] + [
        {"name": "Island", "types": ["Land", "Basic"], "colors": [], "count": 19}
    ]
    assert not candidate_is_legal(too_few, pool)  # 21 spells

    forty_one = pool[:23] + [
        {"name": "Island", "types": ["Land", "Basic"], "colors": [], "count": 18}
    ]
    assert not candidate_is_legal(forty_one, pool)  # 41 cards

    cheater = pool[:22] + [dict(pool[0], count=8)] + [
        {"name": "Island", "types": ["Land", "Basic"], "colors": [], "count": 17}
    ]
    assert not candidate_is_legal(cheater, pool)  # more copies than owned

    # basics are exempt from the owned-copy check
    assert candidate_is_legal(legal23, pool)


# --- 3.2 coupled moves ---


def test_neighbors_are_coupled_and_count_aware():
    spells = [_creature(f"Main {i}", ["U"], 55.0) for i in range(23)]
    sideboard = [_creature(f"Sb {i}", ["U"], 58.0) for i in range(6)]
    pool = spells + sideboard
    deck = spells + [
        {"name": "Island", "types": ["Land", "Basic"], "colors": [], "count": 17}
    ]

    neighbors = list(search_neighbors(deck, pool, ["U"]))
    assert neighbors, "a pool with sideboard options must produce moves"
    for cand in neighbors:
        assert sum(c.get("count", 1) for c in cand) == 40
        n_spells = sum(
            c.get("count", 1) for c in cand if "Land" not in c.get("types", [])
        )
        assert n_spells in (22, 23, 24)
    spell_counts = {
        sum(c.get("count", 1) for c in cand if "Land" not in c.get("types", []))
        for cand in neighbors
    }
    assert spell_counts == {22, 23, 24}, "count-aware moves must reach 22 and 24"
    assert all(candidate_is_legal(c, pool) for c in neighbors)


# --- 3.3 hill climb ---


def _typed_card(name, colors, wr, cmc=3, types=("Creature",)):
    cost = "{" + "}{".join(colors * max(1, cmc - 1)) + "}" if colors else "{0}"
    return {
        "name": name, "types": list(types), "colors": colors, "cmc": cmc,
        "mana_cost": cost, "count": 1,
        "deck_colors": {"All Decks": {"gihwr": wr}},
    }


def _role_deficient_setup():
    """A creature-light control pool: the greedy 23 is spell-heavy while the
    sideboard holds the bodies the deck needs."""
    main_spells = (
        [_typed_card(f"Control Sorcery {i}", ["U"], 58.0, cmc=3, types=("Sorcery",)) for i in range(9)]
        + [_typed_card(f"Control Instant {i}", ["U"], 57.0, cmc=2, types=("Instant",)) for i in range(8)]
        + [_typed_card(f"Wincon {i}", ["U"], 60.0, cmc=6, types=("Creature",)) for i in range(3)]
    )
    creatures = [_typed_card(f"Bodies {i}", ["U"], 56.0, cmc=3) for i in range(10)]
    pool = main_spells + creatures
    deck = (
        main_spells[:20] + creatures[:3]
    )  # greedy-like: 20 noncreature spells + 3 bodies
    return pool, deck


def test_search_improves_role_deficient_deck():
    pool, deck = _role_deficient_setup()
    seed_score, _, _ = _search_score(deck, 45, _metrics())
    results = hill_climb_search([deck], pool, 45, _metrics(), max_evals=160)
    best, best_score = results[0]
    assert best_score >= seed_score - 1e-9  # never worse than the seed
    assert best_score > seed_score  # and here it genuinely improves

    def creature_count(d):
        return sum(
            c.get("count", 1)
            for c in d
            if "Creature" in c.get("types", [])
        )

    assert creature_count(best) > creature_count(deck)
    assert candidate_is_legal(best, pool)


def test_search_is_deterministic_in_evaluation_count_mode():
    pool, deck = _role_deficient_setup()
    a = hill_climb_search([deck], pool, 45, _metrics(), max_evals=120)
    b = hill_climb_search([deck], pool, 45, _metrics(), max_evals=120)
    sig = lambda d: tuple(sorted(f"{c.get('name')}:{c.get('count', 1)}" for c in d))
    assert sig(a[0][0]) == sig(b[0][0])
    assert a[0][1] == b[0][1]


def test_search_idempotent_on_its_own_output():
    """Scoped to neighborhood-exhausted runs: re-seeding the search with its
    own output accepts no further moves."""
    pool, deck = _role_deficient_setup()
    results = hill_climb_search([deck], pool, 45, _metrics(), max_evals=4000)
    best, best_score = results[0]
    again = hill_climb_search([best], pool, 45, _metrics(), max_evals=4000)
    assert again[0][1] <= best_score + 1e-9


# --- Step 4 (ADR): MC cache + beam search ---


def test_mc_cache_reuses_mana_identical_decks():
    """Two decks differing only in spell NAME (same cost/pips/flags) hit the
    same kernel profiles: the second simulation is served from cache."""
    from unittest.mock import patch

    import src.advisor.deck_builder as db

    def spell(name, colors=("U",), cmc=3):
        cost = "{" + "}{".join(colors * max(1, cmc - 1)) + "}"
        return {"name": name, "types": ["Creature"], "colors": list(colors),
                "cmc": cmc, "mana_cost": cost, "count": 1,
                "deck_colors": {"All Decks": {"gihwr": 55.0}}}

    base = [spell(f"A{i}") for i in range(23)] + [
        {"name": "Island", "types": ["Land", "Basic"], "colors": [], "count": 17}
    ]
    renamed = [spell(f"B{i}") for i in range(23)] + [
        {"name": "Island", "types": ["Land", "Basic"], "colors": [], "count": 17}
    ]
    import src.advisor.simulator as sim

    db._MC_CACHE.clear()
    calls = []
    real = sim.simulate_deck
    with patch.object(sim, "simulate_deck", side_effect=lambda *a, **k: (calls.append(1), real(*a, **k))[1]):
        s1 = db._mc_simulation(base, 300, 42)
        s2 = db._mc_simulation(renamed, 300, 42)
    assert s1 == s2
    assert len(calls) == 1


def test_beam_search_deterministic_and_legal():
    from src.advisor.deck_builder import beam_search, candidate_is_legal

    pool, deck = _role_deficient_setup()
    a = beam_search([deck], pool, 45, _metrics(), width=6, max_evals=200)
    b = beam_search([deck], pool, 45, _metrics(), width=6, max_evals=200)
    ka = tuple(sorted(f"{c.get('name')}:{c.get('count', 1)}" for c in a[0][0]))
    kb = tuple(sorted(f"{c.get('name')}:{c.get('count', 1)}" for c in b[0][0]))
    assert ka == kb and a[0][1] == b[0][1]
    assert candidate_is_legal(a[0][0], pool)
    seed_score, _, _ = _search_score(deck, 45, _metrics())
    assert a[0][1] >= seed_score - 1e-9


def test_beam_beats_or_matches_hill_climb_on_role_deficient():
    from src.advisor.deck_builder import beam_search, hill_climb_search

    pool, deck = _role_deficient_setup()
    climb = hill_climb_search([deck], pool, 45, _metrics(), max_evals=200)
    beam = beam_search([deck], pool, 45, _metrics(), width=8, max_evals=300)
    assert beam[0][1] >= climb[0][1] - 1e-9

"""Cycle 2 item 2a: seeded common random numbers for the mana simulator."""

import pytest

from src.advisor.simulator import simulate_deck


def _deck():
    spells, lands = [], []
    for i in range(23):
        colors = ["W"] if i % 2 else ["U"]
        spells.append(
            {
                "name": f"S{i}",
                "types": ["Creature"],
                "colors": colors,
                "cmc": (i % 5) + 1,
                "mana_cost": "{" + "}{".join(colors * ((i % 5) + 1)) + "}",
                "count": 1,
            }
        )
    for i in range(17):
        lands.append(
            {
                "name": "Plains" if i < 9 else "Island",
                "types": ["Land"],
                "colors": [],
                "count": 1,
            }
        )
    return spells + lands


def test_same_seed_is_byte_identical():
    a = simulate_deck(_deck(), iterations=1000, seed=20261026)
    b = simulate_deck(_deck(), iterations=1000, seed=20261026)
    assert a == b


def test_different_seed_changes_the_stream():
    a = simulate_deck(_deck(), iterations=1000, seed=1)
    b = simulate_deck(_deck(), iterations=1000, seed=2)
    assert a != b


def test_unseeded_call_still_works_and_matches_legacy_shape():
    stats = simulate_deck(_deck(), iterations=500)
    assert stats is not None
    assert set(stats) == {
        "mulligans", "screw_t3", "screw_t4", "flood_t5", "cast_t2", "cast_t3",
        "cast_t4", "curve_out", "removal_t4", "color_screw_t3", "avg_hand_size",
    }


def test_sim_executor_is_single_worker():
    """Precondition for CRN (numba's RNG state is per-thread): the executor
    that runs seeded simulations must have exactly one worker."""
    import inspect

    from src.ui.windows import suggest_deck as sd

    assert "ThreadPoolExecutor(max_workers=1)" in inspect.getsource(sd)

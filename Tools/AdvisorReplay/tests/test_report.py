import json

import numpy as np

import report


def runs(n=400, seed=0):
    """Base and head replays where head's picks match the drafter more often.

    Drafters who stray from head (higher regret) win fewer games; base's
    regret is noise.
    """
    rng = np.random.default_rng(seed)
    out = {"base": {"FRA": {}}, "head": {"FRA": {}}}
    for i in range(n):
        follow = rng.random()
        wins = int(round(6 * follow))
        common = {
            "id": f"d{i}",
            "skill": 0.62,
            "games": 100,
            "wins": wins,
            "losses": 3,
            "pool_gihwr": 55.0 + follow,
        }
        out["base"]["FRA"][f"d{i}"] = common | {
            "picks": [[1, 1, 1, rng.random(), 0], [2, 5, 0, rng.random(), 1]],
            "deck_score": rng.random(),
        }
        out["head"]["FRA"][f"d{i}"] = common | {
            "picks": [[1, 1, 0, 1 - follow, 0], [2, 5, 0, 1 - follow, 1]],
            "deck_score": follow,
        }
    return out


def test_pick_table():
    table = report.pick_table(runs())
    assert "| base | 50.0 / 100.0 |" in table
    assert "| head | 100.0 / 100.0 |" in table
    assert "| highest GIH WR | 50.0 / 100.0 |" in table
    assert "**+50.0 points** (paired bootstrap SE 0.0)" in table


def test_wins_table_finds_the_better_advisor():
    lines = report.wins_table(runs()).splitlines()
    regret = next(line for line in lines if line.startswith("| regret"))
    deck = next(line for line in lines if line.startswith("| final pool"))
    _, _, base, head, diff, _, _ = regret.split("|")
    assert float(head) < -1 and abs(float(base)) < 0.3
    assert float(diff.split("**")[1]) < 0
    _, _, base, head, diff, _, _ = deck.split("|")
    assert float(head) > 1 and float(diff.split("**")[1]) > 0


def test_needs_enough_complete_events():
    assert report.wins_table(runs(n=50)).startswith("Fewer than 100")


def test_load_pairs_drafts(tmp_path):
    data = runs(n=5)
    del data["head"]["FRA"]["d0"]
    for label in report.LABELS:
        drafts = list(data[label]["FRA"].values())
        (tmp_path / f"{label}.json").write_text(
            json.dumps({"set": "FRA", "label": label, "drafts": drafts})
        )
    loaded = report.load(sorted(map(str, tmp_path.iterdir())))
    assert (
        list(loaded["base"]["FRA"])
        == list(loaded["head"]["FRA"])
        == ["d1", "d2", "d3", "d4"]
    )
    assert report.report(loaded).startswith("## Picks")


def test_skill_bins_are_two_buckets_wide():
    # Every 17Lands win rate bucket from 0.30 to 0.74, as the dump writes them.
    buckets = {
        0.30: 0, 0.32: 0, 0.34: 1, 0.36: 1, 0.38: 2, 0.40: 2, 0.42: 3, 0.44: 3,
        0.46: 4, 0.48: 4, 0.50: 5, 0.52: 5, 0.54: 6, 0.56: 6, 0.58: 7, 0.60: 7,
        0.62: 8, 0.64: 8, 0.66: 9, 0.68: 9, 0.70: 10, 0.72: 10, 0.74: 11,
    }
    assert {s: report.skill_bin(s) for s in buckets} == buckets
    # Float noise in the dump, and the clamps at both ends.
    assert report.skill_bin(0.7000000000000001) == 10
    assert report.skill_bin(0.0) == report.skill_bin(0.24) == 0
    assert report.skill_bin(0.76) == report.skill_bin(0.82) == 11
    assert report.skill_bin(None) is None

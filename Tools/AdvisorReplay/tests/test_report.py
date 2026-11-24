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


def test_sim_table_only_with_simulated_drafts():
    data = runs()
    assert report.sim_table(data) is None
    assert "Simulated drafts" not in report.report(data)
    rng = np.random.default_rng(1)
    for i, draft in data["base"]["FRA"].items():
        win = 55 + rng.normal()
        draft["sim"] = {"win": win}
        data["head"]["FRA"][i]["sim"] = {"win": win + 0.5}
    table = report.sim_table(data)
    assert "| FRA | 400 |" in table
    assert "+0.500 (0.000)" in table
    assert "Simulated drafts" in report.report(data)

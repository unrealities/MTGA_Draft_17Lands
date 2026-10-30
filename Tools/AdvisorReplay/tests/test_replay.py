import gzip
import json
import os

import pytest

import replay

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DATASET = os.path.join(ROOT, "tests", "data", "MKM_PremierDraft_Data_2024_5_3.json")


@pytest.fixture(scope="module")
def app():
    return replay.App(DATASET)


@pytest.fixture(scope="module")
def names(app):
    """Card names from the dataset, commons and uncommons first."""
    cards = app.dataset.get_card_ratings().values()
    return sorted(c["name"] for c in cards if c.get("rarity") in ("common", "uncommon"))


def draft(names, n_picks, pack_size=5):
    """A draft that takes the first card of each pack."""
    picks = []
    for i in range(n_picks):
        pack = names[i : i + pack_size]
        picks.append([1 + i // 14, 1 + i % 14, pack[0], pack, [p[2] for p in picks]])
    return {
        "id": "d1",
        "skill": 0.6,
        "games": 100,
        "wins": 7,
        "losses": 2,
        "picks": picks,
    }


def test_ranks_and_regret_of_each_pick(app, names):
    result = replay.replay_draft(app, draft(names, 3), replay.Counter())
    assert len(result["picks"]) == 3
    for pack, pick, rank, regret, gihwr_rank in result["picks"]:
        assert 0 <= rank < 5 and 0 <= gihwr_rank < 5
        assert regret >= 0 and (rank > 0 or regret == 0)
    # Too few cards for a deck.
    assert result["deck_score"] is None


def test_scores_a_full_pool(app, names):
    result = replay.replay_draft(app, draft(names, 30), replay.Counter())
    assert result["deck_score"] > 0
    assert 0 < result["pool_gihwr"] < 100


def test_skips_cards_missing_from_the_dataset(app, names):
    d = draft(names, 2)
    d["picks"][0][2] = "Not A Card"
    skipped = replay.Counter()
    assert len(replay.replay_draft(app, d, skipped)["picks"]) == 1
    assert skipped == {"taken card not in dataset": 1}


def test_command_line(tmp_path, names):
    drafts = tmp_path / "drafts.json.gz"
    with gzip.open(drafts, "wt") as f:
        json.dump([draft(names, 3)], f)
    out = tmp_path / "head.json"
    replay.main(
        [
            "--src",
            ROOT,
            "--drafts",
            str(drafts),
            "--dataset",
            DATASET,
            "--set",
            "MKM",
            "--label",
            "head",
            "--out",
            str(out),
        ]
    )
    result = json.loads(out.read_text())
    assert (result["set"], result["label"]) == ("MKM", "head")
    assert [d["id"] for d in result["drafts"]] == ["d1"]


def test_rank_and_regret():
    scores = {"a": 3.0, "b": 1.0, "c": 2.0}
    assert [replay.rank_of(scores, n) for n in "abc"] == [0, 2, 1]
    assert replay.regret(scores, "a") == 0
    assert replay.regret(scores, "b") == pytest.approx(2 / 0.8165, rel=1e-3)

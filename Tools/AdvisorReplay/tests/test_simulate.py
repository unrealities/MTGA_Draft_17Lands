import json
import os
from collections import Counter
from types import SimpleNamespace

import pytest

import replay
import simulate

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DATASET = os.path.join(ROOT, "tests", "data", "MKM_PremierDraft_Data_2024_5_3.json")


def full_draft(packs, takes, rounds=1):
    """A draft in sample.py's form: packs[r][p] the pack at pick p + 1 of round r + 1,
    takes[r][p] the card taken, pools built from the takes."""
    picks, pool = [], []
    for r in range(rounds):
        for p, (pack, taken) in enumerate(zip(packs[r], takes[r])):
            picks.append([r + 1, p + 1, taken, list(pack), sorted(pool)])
            pool.append(taken)
    return {"id": "d", "skill": 0.6, "games": 100, "wins": 3, "losses": 3, "picks": picks}


class FakeApp:
    """Names are cards; the advisor likes the alphabetically first card."""

    full_names = {}
    scorer = SimpleNamespace(BASE_SCORE=75.0, WIN_LOG_ODDS_AT_BASE=0.0, WIN_LOG_ODDS_PER_POINT=0.05)

    def __init__(self):
        self.pools, self.packs = [], []

    def cards(self, names):
        return [{"name": n} for n in names if n != "unknown"]

    def advise(self, pack, pool, pack_no, pick_no):
        self.pools.append([c["name"] for c in pool])
        self.packs.append([c["name"] for c in pack])
        return {c["name"]: -i for i, c in enumerate(sorted(pack, key=lambda c: c["name"]))}

    def suggest(self, pool):
        return {"deck": {"rating": 75.0 + len(pool), "deck_cards": pool, "colors": ["W"]}}

    def quick_build(self, pool):
        return 0.0, [], []


def test_returning_pack_swaps_the_advisors_card_for_the_drafters():
    counts = Counter()
    pack, kept = simulate.returning_pack(["a", "b", "c"], [("a", "x"), ("z", "y")], counts)
    assert pack == ["x", "b", "c"]
    assert kept == [("a", "x")]
    assert counts == {"wheel swap applied": 1, "wheel swap dropped (taken by another drafter)": 1}


def test_wheel_pick_sees_the_drafters_card_back():
    # 10-card packs, one round: pick 9 sees pick 1's pack again.
    first = ["b", "a"] + [f"c{i}" for i in range(8)]
    packs = [[first] + [[f"p{p}a", f"p{p}b"] for p in range(2, 9)] + [["c6", "c7"], ["c7"]]]
    # The drafter took b at pick 1; the advisor (alphabetical) takes a.
    takes = [["b"] + [f"p{p}a" for p in range(2, 9)] + ["c7", "c7"]]
    app, counts = FakeApp(), Counter()
    # Another drafter took a in the real draft: the swap is dropped and the
    # returning pack kept as it was.
    out = simulate.simulate_draft(app, full_draft(packs, takes), counts)
    assert counts["wheel swap dropped (taken by another drafter)"] == 1
    assert counts["wheel picks"] == 2 and counts["picks"] == 10
    assert out["agree"] == 7 and out["decided"] == 9  # pick 1 and pick 9 differ
    assert app.packs[-1] == ["c6", "c7"]
    assert app.pools[-1] == ["a"] + [f"p{p}a" for p in range(2, 9)]

    # a came back in the real draft: the advisor's draft gets b back instead.
    packs[0][8] = ["a", "c7"]
    app, counts = FakeApp(), Counter()
    out = simulate.simulate_draft(app, full_draft(packs, takes), counts)
    assert counts["wheel swap applied"] == 1 and out["wheel_swaps"] == 1
    assert app.packs[-1] == ["b", "c7"]


def test_missing_rows_are_forced_from_the_pools():
    packs = [[["a", "b", "c"], ["d", "e"], ["f"]]]
    takes = [["c", "e", "f"]]
    d = full_draft(packs, takes)
    del d["picks"][0]  # as in TLA and TMT dumps
    assert simulate.forced_picks(d) == {(1, 1): "c"}
    app, counts = FakeApp(), Counter()
    out = simulate.simulate_draft(app, d, counts)
    assert counts["picks forced (no row in the dump)"] == 1
    assert app.pools[0] == ["c"]  # the forced card is in the advisor's pool
    assert out["score"] == 78.0


def test_unaccountable_gap_skips_the_draft():
    d = full_draft([[["a", "b"], ["c", "d"], ["e"]]], [["a", "c", "e"]])
    del d["picks"][0]
    d["picks"][0][4] = []  # the pool no longer shows pick 1's card
    counts = Counter()
    assert simulate.simulate_draft(FakeApp(), d, counts) is None
    assert counts == {"drafts: pools don't account for missing picks": 1}


def test_win_rate():
    s = FakeApp.scorer
    assert simulate.win_rate(75.0, s) == pytest.approx(50.0)
    assert simulate.win_rate(85.0, s) == pytest.approx(100 / (1 + 2.718281828 ** -0.5), rel=1e-6)


@pytest.fixture(scope="module")
def app():
    return replay.App(DATASET)


def test_simulates_a_real_draft(app):
    cards = sorted(
        c["name"] for c in app.dataset.get_card_ratings().values()
        if c.get("rarity") in ("common", "uncommon")
    )
    # Three rounds of 14 picks; each pack a fresh slice of the set.
    packs, takes = [], []
    for r in range(3):
        rp, rt = [], []
        for p in range(14):
            start = (r * 14 + p) * 3 % (len(cards) - 14)
            pack = cards[start : start + 14 - p]
            rp.append(pack)
            rt.append(pack[-1])
        packs.append(rp)
        takes.append(rt)
    d = full_draft(packs, takes, rounds=3)
    counts = Counter()
    out = simulate.simulate_draft(app, d, counts)
    assert counts["picks"] == 42 and out["decided"] == 39
    assert out["deck"] == "suggest deck"
    assert 30 < out["win"] < 80
    result = replay.replay_draft(app, d, Counter(), Counter(), drafter_deck=True)
    assert result["sim"]["win"] == out["win"]
    assert 30 < result["sim"]["drafter_win"] < 80

    # The deck survives the results file: the same scorer grades it the same.
    saved = json.loads(json.dumps(out))
    assert any(isinstance(c, dict) for c in saved["cards"])  # basic lands
    assert simulate.grade(app, saved) == out["win"]


def test_grade_uses_the_judges_scorer_not_the_decks(app, monkeypatch):
    out = {
        "cards": [[c["name"], 1] for c in list(app.dataset.get_card_ratings().values())[:23]],
        "colors": ["W", "U"],
        "pool_size": 42,
        "win": 99.0,  # what another copy's deck score made of it
    }
    before = simulate.grade(app, out)
    assert before != 99.0
    monkeypatch.setattr(app.scorer, "WIN_LOG_ODDS_AT_BASE", app.scorer.WIN_LOG_ODDS_AT_BASE + 0.1)
    assert simulate.grade(app, out) > before


def test_grade_refuses_a_deck_from_another_dataset(app):
    with pytest.raises(SystemExit, match="not in this dataset"):
        simulate.grade(app, {"cards": [["No Such Card", 1]], "colors": [], "pool_size": 1})

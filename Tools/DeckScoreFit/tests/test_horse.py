import io
import json

import horse
import numpy as np
import pytest

WEIGHTS = {"card_quality": 12.0, "two_colors": 3.5, "missing_spells": -10.0}


VERSIONS = ["engine", "no-archetype", "no-shrinkage", "no-iwd", "overall-only"]


def simulated(n=12000, sets=("AAA", "BBB"), seed=0):
    rng = np.random.default_rng(seed)
    features, quality = [], []
    for s in sets:
        rows, decks = [], {}
        for i in range(n // len(sets)):
            true = rng.normal()
            games = int(rng.integers(3, 10))
            wins = int(rng.binomial(games, 1 / (1 + np.exp(-(0.2 + 0.5 * true)))))
            engine = 50 + 15 * true + rng.normal(0, 3)
            row = [
                engine,
                # A worse rating: more noise.
                50 + 15 * true + rng.normal(0, 12),
                # The same rating.
                engine,
                # A better one.
                50 + 15 * true,
                50 + 15 * true + rng.normal(0, 6),
            ]
            key = f"{s}{i}:0"
            decks[key] = [row] * horse.FOLDS
            rows.append({
                "id": key, "wins": wins, "games": games,
                "skill": rng.choice(["0.48", "0.60"]), "experience": "5",
                "features": {"card_quality": rng.normal(), "two_colors": float(rng.random() < 0.8),
                             "missing_spells": 0.0},
                "extra": {}, "rules": {},
            })
        features.append({"set": s, "base_score": 75.0, "weights": WEIGHTS, "rows": rows})
        quality.append({"set": s, "versions": VERSIONS, "decks": decks})
    return features, quality


@pytest.fixture(scope="module")
def hd():
    return horse.HorseData(*simulated())


def test_verdict():
    z = horse.Z
    assert horse.verdict(1.0, 0.1, 10.0) == "engine's predicts better"
    assert horse.verdict(-1.0, 0.1, 10.0) == "ablation predicts better"
    assert horse.verdict(0.0, 0.05, 10.0) == "no difference"
    assert horse.verdict(0.0, 1.0, 10.0) == "can't tell"
    assert horse.verdict(0.0, 0.2 / z, 10.0) == "no difference"


def test_compare_is_per_game():
    a, b = np.array([0.0, 0.0]), np.array([-2.0, -4.0])
    gain, se = horse.compare(a, b, np.array([1.0, 2.0]), np.array([0, 1]))
    assert gain == pytest.approx(2.0) and se == pytest.approx(0.0)


def test_splitting_a_draft_into_builds_does_not_tighten_its_interval():
    a, b = np.array([2.0, 2.0, 0.0]), np.zeros(3)
    games = np.array([2.0, 2.0, 4.0])
    whole = horse.compare(np.array([4.0, 0.0]), np.zeros(2), np.array([4.0, 4.0]),
                          np.array([0, 1]))
    assert horse.compare(a, b, games, np.array([0, 0, 1])) == pytest.approx(whole)
    # Counted as separate drafts, the same games would look more certain.
    assert horse.compare(a, b, games, np.array([0, 1, 2]))[1] < whole[1]


def two_builds():
    features, quality = simulated(n=6000)
    # Each draft in AAA has a second build, with its own results.
    f, q = features[0], quality[0]
    for r in list(f["rows"]):
        draft = r["id"].rsplit(":", 1)[0]
        f["rows"].append(dict(r, id=f"{draft}:1"))
        q["decks"][f"{draft}:1"] = q["decks"][r["id"]]
    return features, quality


def test_builds_of_a_draft_share_a_fold_and_a_cluster():
    hd = horse.HorseData(*two_builds())
    ids = [hd.base.rows[i]["id"] for i in hd.row]
    by_id = dict(zip(ids, zip(hd.fold, hd.draft)))
    for key, (fold, draft) in by_id.items():
        twin = by_id.get(key.rsplit(":", 1)[0] + ":1")
        if twin:
            assert (fold, draft) == twin


def test_each_split_uses_its_own_quality_and_ignores_its_test_decks_results():
    features, quality = simulated(n=4000)
    for q in quality:
        for key, rows in q["decks"].items():
            # Each split's quality is its number.
            q["decks"][key] = [[float(t)] * len(VERSIONS) for t in range(horse.FOLDS)]
    hd = horse.HorseData(features, quality)
    assert set(hd.design("engine", 3)[:, 0]) == {3.0}
    features, quality = simulated(n=4000)
    hd = horse.HorseData(features, quality)
    test, before = horse.predictions(hd, "engine", 2)
    hd.wins[test] = hd.games[test] - hd.wins[test]
    _, after = horse.predictions(hd, "engine", 2)
    assert np.array_equal(before, after)


def test_no_rated_decks_is_a_clear_error():
    features, quality = simulated(n=100)
    for q in quality:
        q["decks"] = {}
    with pytest.raises(ValueError, match="two main colors"):
        horse.HorseData(features, quality)


def test_report(tmp_path, hd):
    out = io.StringIO()
    results = horse.report(hd, out)
    text = out.getvalue()
    assert "## Primary results" in text and "## By set" in text
    assert results["worth"] > 0
    assert results["no-archetype"]["verdict"] == "engine's predicts better"
    assert results["no-shrinkage"]["verdict"] == "no difference"
    assert results["no-iwd"]["verdict"] in ("ablation predicts better", "can't tell")
    assert results["no-iwd"]["gain"] < 0
    assert set(results["per_set"]) == {"AAA", "BBB"}
    paths = {}
    for kind, files in zip(("features", "quality"), simulated(n=2000)):
        paths[kind] = []
        for f in files:
            p = tmp_path / f"{kind}-{f['set']}.json"
            p.write_text(json.dumps(f))
            paths[kind].append(str(p))
    horse.main(["--features", *paths["features"], "--quality", *paths["quality"],
                "--json", str(tmp_path / "horse.json")])
    saved = json.loads((tmp_path / "horse.json").read_text())
    assert "no-archetype" in saved and "log_loss" in saved

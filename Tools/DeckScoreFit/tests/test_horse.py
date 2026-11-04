import io
import json

import horse
import numpy as np
import pytest

WEIGHTS = {"card_quality": 12.0, "two_colors": 3.5, "missing_spells": -10.0}


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
            decks[f"{s}{i}"] = {
                "engine": engine,
                # A worse rating: more noise.
                "no-archetype": 50 + 15 * true + rng.normal(0, 12),
                # The same rating.
                "no-shrinkage": engine,
                # A better one.
                "no-iwd": 50 + 15 * true,
                "overall-only": 50 + 15 * true + rng.normal(0, 6),
            }
            rows.append({
                "id": f"{s}{i}", "wins": wins, "games": games,
                "skill": rng.choice(["0.48", "0.60"]), "experience": "5",
                "features": {"card_quality": rng.normal(), "two_colors": float(rng.random() < 0.8),
                             "missing_spells": 0.0},
                "extra": {}, "rules": {},
            })
        features.append({"set": s, "base_score": 75.0, "weights": WEIGHTS, "rows": rows})
        quality.append({"set": s, "decks": decks})
    return features, quality


@pytest.fixture(scope="module")
def hd():
    return horse.HorseData(*simulated())


def test_verdict():
    z = horse.Z
    assert horse.verdict(1.0, 0.1, 10.0) == "keep"
    assert horse.verdict(-1.0, 0.1, 10.0) == "drop"
    assert horse.verdict(0.0, 0.05, 10.0) == "no difference"
    assert horse.verdict(0.0, 1.0, 10.0) == "can't tell"
    assert horse.verdict(0.0, 0.2 / z, 10.0) == "no difference"


def test_compare_is_per_game():
    a, b = np.array([0.0, 0.0]), np.array([-2.0, -4.0])
    gain, se = horse.compare(a, b, np.array([1.0, 2.0]))
    assert gain == pytest.approx(2.0) and se == pytest.approx(0.0)


def test_report(tmp_path, hd):
    out = io.StringIO()
    results = horse.report(hd, out)
    text = out.getvalue()
    assert "## Primary results" in text and "## By set" in text
    assert results["worth"] > 0
    assert results["no-archetype"]["verdict"] == "keep"
    assert results["no-shrinkage"]["verdict"] == "no difference"
    assert results["no-iwd"]["verdict"] in ("drop", "can't tell")
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

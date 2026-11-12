import io
import json

import numpy as np
import parts
import pytest
import quality

WEIGHTS = {"card_quality": 12.0, "two_colors": 3.5, "missing_spells": -10.0}
PAIRS = ["WU", "UB", "BR", "RG"]
# Log-odds a score point, by part.
OVERALL_SLOPE, LEVEL_SLOPE, FIT_SLOPE = 0.03, 0.01, 0.024


def simulated(n=60000, sets=("AAA", "BBB"), seed=0):
    rng = np.random.default_rng(seed)
    features, qualities = [], []
    for s in sets:
        levels = dict(zip(PAIRS, rng.normal(0, 6, len(PAIRS))))
        rows, decks, part_rows, pairs = [], {}, {}, {}
        for i in range(n // len(sets)):
            pair = PAIRS[int(rng.integers(len(PAIRS)))]
            overall = 50 + rng.normal(0, 8)
            level, fit = levels[pair], rng.normal(0, 4)
            few = rng.random() < 0.5
            games = int(rng.integers(3, 10))
            eta = (OVERALL_SLOPE * (overall - 50) + LEVEL_SLOPE * level
                   + FIT_SLOPE * fit)
            wins = int(rng.binomial(games, 1 / (1 + np.exp(-eta))))
            key = f"{s}{i}:0"
            row = [overall, level, fit, fit if few else 0.0, 0.0 if few else fit]
            part_rows[key] = [row] * quality.FOLDS
            decks[key] = [[overall] * 2] * quality.FOLDS
            pairs[key] = pair
            rows.append({
                "id": key, "wins": wins, "games": games,
                "skill": str(rng.choice(["0.48", "0.62"])), "experience": "5",
                "features": {"card_quality": rng.normal(), "two_colors": 1.0,
                             "missing_spells": 0.0},
                "extra": {}, "rules": {},
            })
        features.append({"set": s, "base_score": 75.0, "weights": WEIGHTS, "rows": rows})
        qualities.append({"set": s, "versions": ["engine", "no-archetype"], "decks": decks,
                          "part_names": quality.PARTS, "parts": part_rows, "pairs": pairs})
    return features, qualities


@pytest.fixture(scope="module")
def pd():
    return parts.PartsData(*simulated())


def test_the_engine_weight_matches_quality():
    assert parts.ENGINE_WEIGHT == pytest.approx(quality.ENGINE_WEIGHT)


def test_a_cards_parts_add_up_to_the_engines_rating():
    counts = {
        "All Decks": {
            "Filler": [1000, 550, 1200, 1000, 540],
            "Chaff": [1000, 450, 1200, 1000, 460],
            "Other": [1000, 500, 1200, 1000, 500],
        },
        "WU": {
            "Filler": [400, 240, 800, 400, 200],
            "Chaff": [600, 300, 3500, 400, 200],
        },
    }
    r = quality.Ratings(counts)
    for name in ("Filler", "Chaff", "Other"):
        value, level, fit, few, many = r.parts(name, "WU")
        assert r.value(name, "WU", "engine") == pytest.approx(
            value + quality.ENGINE_WEIGHT * (level + fit))
        assert few + many == pytest.approx(fit)
    # Level is the games-weighted mean gain: 0.8 x (60 - 55) and 1 x (50 - 45).
    assert r.level("WU") == pytest.approx((400 * 4 + 600 * 5) / 1000)
    # A card with no pair rate adds nothing.
    assert r.parts("Other", "WU")[1:] == [0.0, 0.0, 0.0, 0.0]
    # Under FEW_GAMES its fit is few; from it, many.
    assert r.parts("Filler", "WU")[4] == 0.0 and r.parts("Filler", "WU")[3] != 0.0
    assert r.parts("Chaff", "WU")[3] == 0.0 and r.parts("Chaff", "WU")[4] != 0.0


def test_a_decks_parts_add_up_over_its_spells():
    class App:
        def deck(self, cards):
            return [dict(types=["Land"] if n == "Plains" else ["Creature"], count=c)
                    for n, c in cards.items()]

    fold = [{"All Decks": {"Filler": [500, 300, 500, 250], "Chaff": [500, 200, 500, 250]},
             "WU": {"Filler": [200, 130, 200, 100], "Chaff": [200, 90, 200, 100]}}
            for _ in range(quality.FOLDS)]
    splits = quality.Splits(fold)
    deck = {"id": "d0:0", "main_colors": "WU", "cards": {"Filler": 3, "Chaff": 1, "Plains": 17}}
    got = quality.deck_quality(App(), splits, [deck])
    rows = quality.deck_parts(App(), splits, [deck], got)["d0:0"]
    assert len(rows) == quality.FOLDS
    versions = quality.NAMES
    for split in range(quality.FOLDS):
        overall, level, fit = rows[split][:3]
        assert overall == pytest.approx(got["d0:0"][split][versions.index("no-archetype")],
                                        abs=2e-3)
        engine = got["d0:0"][split][versions.index("engine")]
        assert overall + quality.ENGINE_WEIGHT * (level + fit) == pytest.approx(engine, abs=5e-3)


def test_each_part_gets_its_own_weight(pd):
    everyone = np.ones(len(pd.row), dtype=bool)
    got = parts.weights(pd, ["level", "fit"], everyone, False, clustered=False)
    assert got["level"][0] == pytest.approx(LEVEL_SLOPE / OVERALL_SLOPE, abs=0.1)
    assert got["fit"][0] == pytest.approx(FIT_SLOPE / OVERALL_SLOPE, abs=0.1)


def test_pair_terms_absorb_the_level_but_not_the_fit(pd):
    everyone = np.ones(len(pd.row), dtype=bool)
    # Each set's three less common pairs.
    assert pd.pair_terms.shape[1] == 6
    within = parts.weights(pd, ["fit"], everyone, True, clustered=False)["fit"]
    assert within[0] == pytest.approx(FIT_SLOPE / OVERALL_SLOPE, abs=0.1)
    A = np.hstack([pd.columns(pd.parts[:, 0], "free"), pd.controls, pd.pair_terms])
    assert np.linalg.matrix_rank(A[:, [1] + list(range(3, A.shape[1]))]) < A.shape[1] - 2


def test_rare_pairs_share_the_sets_baseline():
    features, qualities = simulated(n=4000, sets=("AAA",))
    pairs = qualities[0]["pairs"]
    rare = list(pairs)[:10]
    for k in rare:
        pairs[k] = "WG"
    assert parts.PartsData(features, qualities).pair_terms.shape[1] == 3


@pytest.mark.parametrize("weight,se,gain,gain_se,expected", [
    (0.1, 0.1, 1.0, 0.1, "not the level"),
    (-0.5, 0.1, 1.0, 0.1, "not the level"),
    (0.8, 0.1, 1.0, 0.1, "the level explains it"),
    (0.8, 0.1, 0.1, 0.1, "partly"),
    (0.8, 0.1, -1.0, 0.1, "partly"),
])
def test_verdict(weight, se, gain, gain_se, expected):
    assert parts.verdict(weight, se, gain, gain_se) == expected


def test_usable_drops_empty_and_repeated_constant_columns():
    A = np.array([[1.0, 0.0, 1.0, 1.0, 2.0], [2.0, 0.0, 1.0, 1.0, 3.0]])
    assert parts._usable(A, 1).tolist() == [[1.0, 1.0, 2.0], [2.0, 1.0, 3.0]]


def test_report_reads_the_simulation(pd):
    out = io.StringIO()
    results = parts.report(pd, out)
    text = out.getvalue()
    assert "By the protocol's rule" in text and results["verdict"] in text
    # Fit is worth 0.8 here, and 0.95 is close, so fit only beats no blend.
    assert results["verdict"] == "the level explains it"
    assert results["held_out"]["fit-only"][0] > 0
    assert set(results["by_skill"]) == {"strong drafters", "the rest"}
    assert set(results["per_set"]) == {"AAA", "BBB"}
    json.dumps(results, default=float)

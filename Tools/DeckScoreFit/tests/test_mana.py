import io
import json
from math import comb

import hands
import mana
import numpy as np
import pytest

WEIGHTS = {"card_quality": 12.0, "two_colors": 3.5, "missing_spells": -10.0}
QUALITY = 0.4
# Win probability lost when each event happens.
COST = {"screw_t3": -0.30, "flood_t5": -0.20, "color_screw_t3": -0.25}
# The simulator's color screw rate is twice the real chance in keeps.
COLOR_SIM = 2.0


def simulated(n=6000, sets=("AAA", "BBB", "CCC"), seed=0):
    rng = np.random.default_rng(seed)
    features, hand_files = [], []
    for s in sets:
        rows, decks = [], []
        for i in range(n // len(sets)):
            lands = int(rng.choice([16, 17, 18]))
            q = rng.normal()
            color_mean = rng.uniform(0.02, 0.2)
            games, wins = [], 0
            for _ in range(int(rng.integers(3, 10))):
                on_play = int(rng.random() < 0.5)
                if rng.random() < 0.1:
                    won = int(rng.random() < 0.45)
                    games.append([on_play, 1, won, None, None, None, None])
                    wins += won
                    continue
                pmf = [comb(lands, x) * comb(40 - lands, 7 - x) / comb(40, 7)
                       for x in range(8)]
                h = int(rng.choice(8, p=pmf))
                p = {"screw_t3": hands.screw_chance(h, lands),
                     "flood_t5": hands.flood_chance(h, lands),
                     "color_screw_t3": rng.uniform(0, 2 * color_mean)}
                prob = 0.55 + 0.1 * q / (1 + abs(q)) + 0.02 * on_play
                prob += sum(COST[k] * (rng.random() < p[k]) for k in COST)
                won = int(rng.random() < min(max(prob, 0.01), 0.99))
                wins += won
                games.append([on_play, 0, won, h, p["screw_t3"], p["flood_t5"],
                              p["color_screw_t3"]])
            screw = 100 * sum(pmf[x] * hands.screw_chance(x, lands) for x in range(8))
            flood = 100 * sum(pmf[x] * hands.flood_chance(x, lands) for x in range(8))
            decks.append({
                "id": f"{s}{i}", "lands": lands,
                "sim": {"screw_t3": screw, "flood_t5": flood,
                        "color_screw_t3": COLOR_SIM * 100 * color_mean, "mulligans": 10.0},
                "kept7": {"keep": 90.0, "screw_t3": screw, "flood_t5": flood,
                          "color_screw_t3": 100 * color_mean},
                "games": games,
            })
            rows.append({
                "id": f"{s}{i}", "wins": wins, "games": len(games),
                "skill": rng.choice(["0.48", "0.54", "0.60"]),
                "experience": rng.choice(["5", "50"]),
                "features": {"card_quality": q, "two_colors": float(rng.random() < 0.8),
                             "missing_spells": 0.0},
                "extra": {"lands": float(lands)},
                "rules": {},
            })
        features.append({"set": s, "base_score": 75.0, "weights": WEIGHTS, "rows": rows})
        hand_files.append({"set": s, "decks": decks})
    return features, hand_files


@pytest.fixture(scope="module")
def md():
    return mana.ManaData(*simulated())


def test_recovers_the_cost_of_each_event(md):
    cost, by_deck, by_set = mana.event_costs(md)
    se = np.sqrt(np.maximum(np.diag(by_deck), np.diag(by_set)))
    for i, k in enumerate(mana.RATES):
        assert abs(cost[i] - COST[k]) < 3.5 * se[i], k


def test_calibration_slope(md):
    slope, var_deck, var_set = mana.calibration(md, "color_screw_t3")
    assert slope == pytest.approx(1 / COLOR_SIM, abs=4 * max(var_deck, var_set) ** 0.5)
    slope, *_ = mana.calibration(md, "screw_t3")
    assert slope == pytest.approx(1.0, abs=0.15)


def test_leaves_out_dumps_without_mulligans():
    features, hand_files = simulated(n=900)
    for deck in hand_files[0]["decks"]:
        for g in deck["games"]:
            g[1] = 0
    md = mana.ManaData(features, hand_files)
    assert set(md.left_out) == {"AAA"} and md.sets == ["BBB", "CCC"]


def test_hand_shares_add_up(md):
    obs, rand, simk = mana.hand_shares(md)
    assert obs.sum() == pytest.approx(1) and rand.sum() == pytest.approx(1)
    assert simk[[0, 1, 6, 7]].sum() == 0 and simk.sum() == pytest.approx(1)
    # The simulated hands are random 7s.
    assert np.abs(obs - rand).max() < 0.02


def test_report(tmp_path, md):
    out = io.StringIO()
    results = mana.report(md, out)
    text = out.getvalue()
    for heading in ("## Primary results", "## Calibration", "## Win rate by lands in hand",
                    "## By set", "## Deck-level fit"):
        assert heading in text
    for k, *_ in mana.PENALTIES:
        assert results[k]["keep_or_drop"] in ("keep", "drop", "can't tell")
        # Every event costs wins, so a point of rate costs score points.
        assert results[k]["points"] < 0
    assert results["all"]["size"] <= 0
    # Fewer lands in hand than 3 loses more.
    assert results["by_hand"]["0-1"][0] < results["by_hand"]["2"][0] < 0
    feats, hand_files = simulated(n=1500)
    paths = {}
    for kind, files in (("features", feats), ("hands", hand_files)):
        paths[kind] = []
        for f in files:
            p = tmp_path / f"{kind}-{f['set']}.json"
            p.write_text(json.dumps(f))
            paths[kind].append(str(p))
    mana.main(["--features", *paths["features"], "--hands", *paths["hands"],
               "--json", str(tmp_path / "mana.json")])
    saved = json.loads((tmp_path / "mana.json").read_text())
    assert {"screw_t3", "flood_t5", "color_screw_t3", "all"} <= set(saved)

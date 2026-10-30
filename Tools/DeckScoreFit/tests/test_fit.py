import ast
import io
import json
import math

import fit
import numpy as np
import pytest

WEIGHTS = {
    "card_quality": 12.0,
    "two_colors": 2.5,
    "lacks_evasion": -5.0,
    "tribal_synergy": 1.0,
    "missing_spells": -10.0,
}
# Log-odds of a game win per unit of each feature, in the simulated data.
TRUE = {"card_quality": 0.4, "two_colors": 0.1, "lacks_evasion": 0.0}


def files(n=6000, sets=("AAA", "BBB", "CCC"), seed=0):
    """features.py output for simulated decks of known worth."""
    rng = np.random.default_rng(seed)
    out = []
    for s, set_effect in zip(sets, (-0.1, 0.0, 0.1)):
        rows = []
        for i in range(n // len(sets)):
            f = {
                "card_quality": rng.normal(),
                "two_colors": float(rng.random() < 0.5),
                "lacks_evasion": float(rng.random() < 0.2),
                "tribal_synergy": 0.0,
                "missing_spells": float(i < 5),
            }
            skill = rng.choice(["0.44", "0.52", "0.60"])
            eta = set_effect + (float(skill) - 0.52) * 4
            eta += sum(TRUE[k] * f[k] for k in TRUE)
            games = int(rng.integers(3, 10))
            rows.append(
                {
                    "id": f"{s}{i}",
                    "wins": int(rng.binomial(games, 1 / (1 + math.exp(-eta)))),
                    "games": games,
                    "skill": skill,
                    "experience": rng.choice(["5", "50"]),
                    "features": f,
                    "extra": {"lands": 17.0, "spells": 23.0},
                }
            )
        out.append({"set": s, "base_score": 75.0, "weights": WEIGHTS, "rows": rows})
    return out


@pytest.fixture(scope="module")
def data():
    return fit.Data(files())


def test_leaves_out_unfinished_decks_and_features_that_never_fire(data):
    assert data.unfinished == 15
    assert data.never == ["tribal_synergy"]
    assert data.names == ["card_quality", "two_colors", "lacks_evasion"]
    assert len(data.set) == 6000 - 15


def test_recovers_weights_in_score_points(data):
    fitted = fit.fit_weights(data, np.ones(len(data.set), dtype=bool))
    assert fitted["card_quality"][0] == pytest.approx(12.0)
    for k in ("two_colors", "lacks_evasion"):
        points, se = fitted[k]
        truth = 12.0 * TRUE[k] / TRUE["card_quality"]
        assert 0.3 < se < 2
        assert abs(points - truth) < 3 * se


def test_fit_logit_matches_a_known_answer():
    # One group: the MLE of a lone intercept is the log-odds of its win rate.
    beta, cov = fit.fit_logit(
        np.ones((2, 1)), np.array([3.0, 4.0]), np.array([5.0, 5.0])
    )
    assert beta[0] == pytest.approx(math.log(0.7 / 0.3))
    assert cov[0, 0] == pytest.approx(1 / (10 * 0.7 * 0.3))


def test_expected_wins():
    def by_recursion(p, wins=0, losses=0):
        if wins == 7 or losses == 3:
            return wins
        return p * by_recursion(p, wins + 1, losses) + (1 - p) * by_recursion(
            p, wins, losses + 1
        )

    for p in (0.0, 0.3, 0.5, 0.6, 1.0):
        assert fit.expected_wins(p) == pytest.approx(by_recursion(p))
    assert fit.expected_wins(1.0) == 7


def test_held_out_ranks_the_true_model_best(data):
    results = fit.held_out(data)
    assert set(results) == {"AAA", "BBB", "CCC"}
    for rows in results.values():
        # lacks_evasion is worth nothing here, so the app's weights rank worse.
        assert rows["fitted weights"][0] < rows["app's current weights"][0]
        assert rows["fitted weights"][1] > 0


def test_report(tmp_path):
    paths = []
    for f in files(n=3000):
        path = tmp_path / f"{f['set']}.json"
        path.write_text(json.dumps(f))
        paths.append(path)
    out = io.StringIO()
    fit.report(fit.Data([json.loads(p.read_text()) for p in paths]), out)
    text = out.getvalue()
    for heading in ("## Weights", "## On sets the fit didn't see", "## Records"):
        assert heading in text
    block = text.split("```python\n")[1].split("```")[0]
    weights = {
        node.targets[0].id: ast.literal_eval(node.value)
        for node in ast.parse(block).body
    }
    assert list(weights["WEIGHTS"]) == list(WEIGHTS)
    assert weights["WEIGHTS"]["card_quality"] == 12.0
    assert weights["WEIGHTS"]["tribal_synergy"] == 0.0
    assert weights["WEIGHTS"]["missing_spells"] == -10.0
    assert weights["WIN_LOG_ODDS_PER_POINT"] > 0


def test_one_set_skips_the_held_out_check():
    out = io.StringIO()
    fit.report(fit.Data(files(n=1000, sets=("AAA",))), out)
    assert "## On sets the fit didn't see" not in out.getvalue()
    assert "## Records" in out.getvalue()

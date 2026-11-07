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



def test_fit_clustered_agrees_with_fit_logit():
    rng = np.random.default_rng(1)
    n = 400
    A = np.column_stack([np.ones(n), rng.normal(size=n)])
    games = rng.integers(3, 10, size=n).astype(float)
    wins = rng.binomial(games.astype(int), fit.expit(0.2 + 0.5 * A[:, 1])).astype(float)
    beta, model, cluster = fit.fit_clustered(A, wins, games)
    ref, ref_cov = fit.fit_logit(A, wins, games)
    assert beta == pytest.approx(ref, abs=1e-8)
    assert model == pytest.approx(ref_cov, rel=1e-6)
    assert cluster is None


def test_fit_clustered_cluster_covariance():
    rng = np.random.default_rng(2)
    n = 600
    groups = np.repeat(np.array(["a", "b", "c", "d", "e", "f"]), n // 6)
    # Each group has its own shift that the model doesn't know about, so the
    # cluster sandwich should be wider than the model's errors.
    shift = {g: s for g, s in zip("abcdef", rng.normal(scale=0.5, size=6))}
    x = rng.normal(size=n) + np.array([shift[g] for g in groups])
    A = np.column_stack([np.ones(n), x])
    games = np.full(n, 8.0)
    eta = 0.3 * x + np.array([shift[g] for g in groups])
    wins = rng.binomial(8, fit.expit(eta)).astype(float)
    beta, model, cluster = fit.fit_clustered(A, wins, games, groups)
    assert cluster.shape == model.shape
    assert cluster[1, 1] > model[1, 1]
    # The labels may come as a plain list.
    assert fit.fit_clustered(A, wins, games, list(groups))[2] == pytest.approx(cluster)
    # One group: no cluster covariance.
    assert fit.fit_clustered(A, wins, games, np.full(n, "a"))[2] is None


def test_varying_drops_constant_columns():
    C = np.array([[1.0, 0.0, 2.0], [1.0, 1.0, 2.0]])
    assert fit.varying(C).tolist() == [[0.0], [1.0]]
    assert fit.varying(np.zeros((0, 3))).shape == (0, 3)


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


def test_report_keeps_the_apps_weight_for_features_not_fit_to_games():
    out_files = files(n=3000)
    rng = np.random.default_rng(1)
    for f in out_files:
        f["weights"] = dict(WEIGHTS, missing_fixing=-2.5)
        for r in f["rows"]:
            r["features"]["missing_fixing"] = float(rng.random() < 0.1)
    data = fit.Data(out_files)
    # Still fit, so the other weights are measured with it in the model...
    assert "missing_fixing" in data.names
    out = io.StringIO()
    fit.report(data, out)
    text = out.getvalue()
    assert "the app's weight is kept" in text
    # ...but the weights to paste keep the app's value, not the fitted ~0.
    block = text.split("```python\n")[1].split("```")[0]
    weights = ast.literal_eval(block.split("WEIGHTS = ")[1].split("\nWIN_")[0])
    assert weights["missing_fixing"] == -2.5


def test_one_set_skips_the_held_out_check():
    out = io.StringIO()
    fit.report(fit.Data(files(n=1000, sets=("AAA",))), out)
    assert "## On sets the fit didn't see" not in out.getvalue()
    assert "## Records" in out.getvalue()

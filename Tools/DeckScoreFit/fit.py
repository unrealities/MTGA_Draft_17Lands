"""Fit the deck score's weights to game results, and report how well they do.

    python Tools/DeckScoreFit/fit.py results/*.json > report.md

The fit is a logistic regression of each deck's games won on its features,
over all sets at once. It controls for the set and for the player's win rate
and experience buckets, so the weights are for the deck, not the player. They
come out in the score's own units, where the app's card_quality weight (12
points) is one standard deviation of card quality.

Needs NumPy. If LightGBM is installed, the report also shows how much better a
model with no linear form does, as a yardstick.
"""

import argparse
import json
import math
import sys
from collections import Counter

import numpy as np

QUALITY = "card_quality"
# Guards for unfinished decks. Finished decks never set them off, so the data
# can't fit them; the few decks that do are left out.
FIXED = ("missing_spells",)
# A Premier Draft event ends at 7 wins or 3 losses.
MAX_WINS, MAX_LOSSES = 7, 3


class Data:
    """Decks from features.py, as arrays."""

    def __init__(self, files):
        self.weights = files[0]["weights"]
        self.base_score = files[0]["base_score"]
        rows = [dict(r, set=f["set"]) for f in files for r in f["rows"]]
        kept = [r for r in rows if not any(r["features"][k] for k in FIXED)]
        self.unfinished = len(rows) - len(kept)
        names = [k for k in self.weights if k not in FIXED]
        self.never = [k for k in names if not any(r["features"][k] for r in kept)]
        self.names = [k for k in names if k not in self.never]
        self.q = self.names.index(QUALITY)

        self.set = np.array([r["set"] for r in kept])
        self.sets = sorted(set(self.set))
        self.X = np.array([[r["features"][k] for k in self.names] for r in kept])
        self.wins = np.array([r["wins"] for r in kept], dtype=float)
        self.games = np.array([r["games"] for r in kept], dtype=float)
        self.extra_names = sorted(kept[0]["extra"]) if kept else []
        self.extra = np.array([[r["extra"][k] for k in self.extra_names] for r in kept])
        # Player buckets as indicators, leaving out the most common of each.
        cols = []
        for key in ("skill", "experience"):
            values = [r[key] for r in kept]
            common = Counter(values).most_common()
            for value, _ in common[1:]:
                cols.append([v == value for v in values])
        self.C = np.array(cols, dtype=float).T.reshape(len(kept), len(cols))

    def set_dummies(self, mask, sets):
        return np.array([[s == t for t in sets] for s in self.set[mask]], dtype=float)


def expit(x):
    return 1.0 / (1.0 + np.exp(-x))


def fit_logit(A, wins, games, offset=0.0):
    """Coefficients and their covariance for a binomial logistic regression."""
    beta = np.zeros(A.shape[1])
    ridge = 1e-8 * np.eye(A.shape[1])
    for _ in range(100):
        p = expit(A @ beta + offset)
        H = A.T @ (A * (games * p * (1 - p))[:, None]) + ridge
        step = np.linalg.solve(H, A.T @ (wins - games * p) - ridge @ beta)
        beta += step
        if np.abs(step).max() < 1e-9:
            break
    p = expit(A @ beta + offset)
    # Players differ by more than their buckets say, so the games of one deck
    # vary more than a binomial: widen the errors by the Pearson dispersion.
    dispersion = ((wins - games * p) ** 2 / (games * p * (1 - p))).sum() / max(
        1, len(wins) - A.shape[1]
    )
    return beta, np.linalg.inv(H) * max(1.0, dispersion)


def to_points(beta, cov, k, q, scale):
    """Coefficient k in score points (scale per unit of coefficient q), with its SE."""
    g = np.zeros(len(beta))
    g[k], g[q] = scale / beta[q], -scale * beta[k] / beta[q] ** 2
    return scale * beta[k] / beta[q], math.sqrt(g @ cov @ g)


def fit_weights(data, mask):
    """{feature: (points, SE)} from the decks in mask."""
    sets = sorted(set(data.set[mask]))
    A = np.hstack([data.X[mask], data.set_dummies(mask, sets), data.C[mask]])
    beta, cov = fit_logit(A, data.wins[mask], data.games[mask])
    scale = data.weights[QUALITY]
    return {k: to_points(beta, cov, i, data.q, scale) for i, k in enumerate(data.names)}


def log_loss(eta, wins, games):
    """Per game, after refitting one intercept for the held-out set."""
    a = fit_logit(np.ones((len(eta), 1)), wins, games, offset=eta)[0][0]
    p = np.clip(expit(eta + a), 1e-9, 1 - 1e-9)
    return -(wins * np.log(p) + (games - wins) * np.log(1 - p)).sum() / games.sum()


def spread(score, wins, games):
    """Game win rate of the top fifth of decks by score less the bottom fifth's."""
    order = np.argsort(score, kind="stable")
    n = len(order) // 5
    bottom, top = order[:n], order[-n:]
    return wins[top].sum() / games[top].sum() - wins[bottom].sum() / games[bottom].sum()


def held_out(data):
    """For each set, how models fit on the other sets do on it.

    Each model gives every held-out deck a score for the deck alone, which
    ranks the decks for the spread. For the log loss, the model's player terms
    are added and one intercept is refit for the held-out set.
    """
    scale = data.weights[QUALITY]
    current = data.X @ np.array([data.weights[k] for k in data.names]) / scale
    out = {}
    for s in data.sets:
        train, test = data.set != s, data.set == s
        sets = sorted(set(data.set[train]))
        rows = {}
        for label, cols in (
            ("card quality only", data.X[:, [data.q]]),
            ("app's current weights", current[:, None]),
            ("fitted weights", data.X),
        ):
            A = np.hstack([cols[train], data.set_dummies(train, sets), data.C[train]])
            beta = fit_logit(A, data.wins[train], data.games[train])[0]
            k = cols.shape[1]
            score = cols[test] @ beta[:k]
            player = data.C @ beta[k + len(sets) :]
            rows[label] = evaluate(score, player[test], data, test)
        # The set and player terms of the fitted weights' model, for LightGBM
        # to start from, so that it too scores only the deck.
        offset = A[:, k:] @ beta[k:]
        score = lightgbm_score(data, train, test, offset)
        if score is not None:
            rows["LightGBM (yardstick)"] = evaluate(score, player[test], data, test)
        out[s] = rows
    return out


def evaluate(score, player, data, test):
    """(log loss, spread) of a deck score on the held-out decks."""
    wins, games = data.wins[test], data.games[test]
    return log_loss(score + player, wins, games), spread(score, wins, games)


def lightgbm_score(data, train, test, offset):
    """Held-out deck scores (log-odds) from LightGBM on the features and counts.

    It starts from offset, the set and player terms, and learns the rest.
    """
    try:
        import lightgbm
    except ImportError:
        return None
    Z = np.hstack([data.X, data.extra])
    # One row for a deck's wins and one for its losses, weighted by count.
    n = train.sum()
    rows = lightgbm.Dataset(
        np.vstack([Z[train], Z[train]]),
        label=np.r_[np.ones(n), np.zeros(n)],
        weight=np.r_[data.wins[train], data.games[train] - data.wins[train]],
        init_score=np.r_[offset, offset],
    )
    params = {
        "objective": "binary",
        "learning_rate": 0.05,
        "num_leaves": 15,
        "min_data_in_leaf": 200,
        "verbose": -1,
    }
    model = lightgbm.train(params, rows, num_boost_round=300)
    return model.predict(Z[test], raw_score=True)


def record_curve(data, weights):
    """Log-odds of winning a game at the base score, and per point of score.

    Fit on the score alone, without the player buckets: the app doesn't know
    the player, so this is what decks with each score won, players and all.
    """
    score = data.X @ np.array([weights[k] for k in data.names])
    A = np.column_stack([np.ones(len(score)), score])
    beta = fit_logit(A, data.wins, data.games)[0]
    return beta[0], beta[1], score


def expected_wins(p):
    """Expected wins in a Premier Draft event with game win rate p."""
    q, total = 1 - p, 0.0
    for w in range(MAX_WINS):
        total += w * math.comb(w + MAX_LOSSES - 1, w) * p**w * q**MAX_LOSSES
    reach = sum(
        math.comb(MAX_WINS - 1 + losses, losses) * p**MAX_WINS * q**losses
        for losses in range(MAX_LOSSES)
    )
    return total + MAX_WINS * reach


def report(data, out=sys.stdout):
    w = lambda line="": print(line, file=out)
    fitted = fit_weights(data, np.ones(len(data.set), dtype=bool))
    games = int(data.games.sum())
    w("## Data")
    w()
    w(
        f"{len(data.set)} decks and {games} games from {len(data.sets)} sets "
        f"({', '.join(data.sets)}). {data.unfinished} unfinished decks were "
        "left out."
    )
    if data.never:
        w(f"Never set off by any deck, so not fitted: {', '.join(data.never)}.")
    w()
    w("## Weights")
    w()
    w("In score points. A weight within two SEs of 0 is marked ~0.")
    w()
    w("| feature | decks it applies to | app's weight | fitted weight |")
    w("|---|---|---|---|")
    for i, k in enumerate(data.names):
        share = (data.X[:, i] != 0).mean()
        pts, se = fitted[k]
        flag = " ~0" if abs(pts) < 2 * se and k != QUALITY else ""
        shown = f"{pts:+.1f} ± {se:.1f}{flag}" if k != QUALITY else f"{pts:+.1f}"
        w(f"| {k} | {share:.1%} | {data.weights[k]:+.1f} | {shown} |")
    w()
    w("## Weights fit on each set alone")
    w()
    w("If these agree, one set of weights can serve every set.")
    w()
    w("| feature | " + " | ".join(data.sets) + " |")
    w("|---" * (len(data.sets) + 1) + "|")
    per_set = {s: fit_weights(data, data.set == s) for s in data.sets}
    for i, k in enumerate(data.names):
        if k == QUALITY:
            continue
        cells = []
        for s in data.sets:
            if (data.X[data.set == s, i] != 0).sum() < 30:
                cells.append("–")
            else:
                cells.append(f"{per_set[s][k][0]:+.1f}")
        w(f"| {k} | " + " | ".join(cells) + " |")
    w()
    if len(data.sets) > 1:
        held_out_report(data, w)

    weights = {k: round(fitted[k][0], 1) for k in data.names}
    weights[QUALITY] = data.weights[QUALITY]
    a, b, score = record_curve(data, weights)
    w("## Records")
    w()
    w(
        "Game win rate by score, fit on the score alone (the app doesn't know "
        "the player), and the expected wins in a Premier Draft event."
    )
    w()
    w("| score | decks at or below | game win rate | expected wins |")
    w("|---|---|---|---|")
    base = data.base_score
    for s in range(55, 100, 5):
        p = 1 / (1 + math.exp(-(a + b * (s - base))))
        below = (score + base <= s).mean()
        w(f"| {s} | {below:.0%} | {p:.1%} | {expected_wins(p):.1f} |")
    w()
    w("## For deck_scorer.py")
    w()
    w("```python")
    w("WEIGHTS = {")
    for k in data.weights:
        value = weights.get(k, 0.0 if k in data.never else data.weights[k])
        w(f'    "{k}": {value},')
    w("}")
    w(f"WIN_LOG_ODDS_AT_BASE = {a:.4f}")
    w(f"WIN_LOG_ODDS_PER_POINT = {b:.5f}")
    w("```")


def held_out_report(data, w):
    w("## On sets the fit didn't see")
    w()
    w(
        "Each set is scored by models fit on the other sets. *Spread*: the game "
        "win rate of the top fifth of decks by score, less the bottom fifth's; "
        "higher is better. *Log loss*: per game, lower is better."
    )
    w()
    results = held_out(data)
    labels = list(next(iter(results.values())))
    weight = {s: data.games[data.set == s].sum() for s in data.sets}
    games = data.games.sum()
    w("| model | spread | log loss |")
    w("|---|---|---|")
    for label in labels:
        loss = sum(results[s][label][0] * weight[s] for s in data.sets) / games
        gap = sum(results[s][label][1] * weight[s] for s in data.sets) / games
        w(f"| {label} | {gap:.1%} | {loss:.5f} |")
    w()
    w("Spread by set:")
    w()
    w("| model | " + " | ".join(data.sets) + " |")
    w("|---" * (len(data.sets) + 1) + "|")
    for label in labels:
        w(
            f"| {label} | "
            + " | ".join(f"{results[s][label][1]:.1%}" for s in data.sets)
            + " |"
        )
    w()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("files", nargs="+", help="From features.py, one per set")
    args = parser.parse_args(argv)
    files = []
    for path in args.files:
        with open(path, encoding="utf-8") as f:
            files.append(json.load(f))
    report(Data(files))


if __name__ == "__main__":
    main()

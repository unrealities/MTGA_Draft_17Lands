"""Looked at after the result: what a pair's rating is worth between pairs.

    python experiments/2026-11-08-pair-parts/between_pairs.py \
        experiments/2026-11-08-pair-parts/pair_means.json

Regresses each pair's win rate, as a difference from its set's, on its decks'
mean parts. Unlike parts.py it controls for nothing but the set. The input is
pair_means.py's output. See RESULTS.md.
"""
import json
import sys

import numpy as np

MIN_DECKS = 50
# Win rate points per score point at the deck score's slope: 0.0387 log-odds a
# point x 12 points per SD / 4 win rate points per SD, about 2.9 win rate points
# per rating point; 15 score points are one SD, so 3.75 are one rating point.
RATING_POINT = 3.75
WITHIN = 2.9 / RATING_POINT


def load(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    rows = []
    for s, pairs in data.items():
        if s.startswith("Cube"):
            continue
        kept = [p for p in pairs.values() if p["decks"] >= MIN_DECKS]
        games = np.array([p["games"] for p in kept])
        columns = {k: np.array([p[k] for p in kept]) for k in ("overall", "level")}
        columns["rate"] = 100 * np.array([p["wins"] / p["games"] for p in kept])
        for values in columns.values():
            values -= np.average(values, weights=games)
        rows.append(np.column_stack([games, columns["rate"], columns["overall"],
                                     columns["level"], np.full(len(kept), len(rows))]))
    return np.vstack(rows)


def wls(a, columns):
    """Games-weighted slopes of the win rate, with set-clustered SEs."""
    w, y, sets = a[:, 0], a[:, 1], a[:, 4]
    X = a[:, columns]
    inv = np.linalg.inv(X.T @ (w[:, None] * X))
    b = inv @ (X.T @ (w * y))
    e = w * (y - X @ b)
    meat = sum(np.outer(g, g) for g in
               ((X[sets == s] * e[sets == s, None]).sum(axis=0) for s in np.unique(sets)))
    return b, np.sqrt(np.diag(inv @ meat @ inv))


def main(path):
    a = load(path)
    w, y, o, l = a[:, 0], a[:, 1], a[:, 2], a[:, 3]
    sd = lambda x: np.sqrt(np.average(x ** 2, weights=w))  # noqa: E731
    corr = np.average(o * l, weights=w) / sd(o) / sd(l)
    print(f"{len(a)} pairs in {len(np.unique(a[:, 4]))} sets")
    print(f"SDs: win rate {sd(y):.2f} points; overall {sd(o) / RATING_POINT:.2f} and "
          f"level {sd(l) / RATING_POINT:.2f} rating points; correlation {corr:.2f}")
    b, se = wls(a, [2])
    print(f"overall alone: {b[0] * RATING_POINT:+.2f} ({se[0] * RATING_POINT:.2f}) "
          "win rate points a rating point")
    b, se = wls(a, [2, 3])
    print(f"together: overall {b[0] * RATING_POINT:+.2f} ({se[0] * RATING_POINT:.2f}), "
          f"level {b[1] * RATING_POINT:+.2f} ({se[1] * RATING_POINT:.2f})")
    # With overall's slope held at the within-pair value, what's left falls on level.
    implied = b[1] + (b[0] - WITHIN) * corr * sd(o) / sd(l)
    print(f"level's weight implied, overall's slope held at {WITHIN * RATING_POINT:.1f}: "
          f"{implied / WITHIN:+.2f}")
    for weight in (0.0, 0.7):
        r = o + weight * l
        slope = np.average(r * y, weights=w) / np.average(r * r, weights=w)
        print(f"overall + {weight} x level: {slope * RATING_POINT:+.2f} win rate points a "
              f"rating point, against {WITHIN * RATING_POINT:.1f} priced")


if __name__ == "__main__":
    main(sys.argv[1])

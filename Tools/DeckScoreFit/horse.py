"""Which version of the engine's card rating best predicts deck results.

    python Tools/DeckScoreFit/horse.py --features features/*.json \
        --quality quality/*.json --json horse.json > horse.md

The inputs are features.py's and quality.py's output for the same decks.
For each version of the rating, fit.py's logistic regression with card
quality replaced by the version's deck quality is fit on four fifths of the
decks and scored on the rest, five times; versions are compared on held-out
log loss per game, deck by deck. See README.md.

Needs NumPy.
"""

import argparse
import json
import math
import sys

import numpy as np

from decks import deck_hash
from fit import QUALITY, Data, expit, fit_logit
from rules import _varying

# Two-sided 98.33% intervals: 95% familywise across the three comparisons.
Z = 2.394
FOLDS = 5
ENGINE = "engine"
PRIMARY = {
    "no-archetype": "Archetype weighting",
    "no-shrinkage": "Shrinkage",
    "no-iwd": "IWD premium",
}
SECONDARY = {
    "weight-0.65": "blend weight 0.65 (engine's at pick 1)",
    "weight-1.3": "blend weight 1.3 (engine's from pick 15)",
    "no-power-bonus": "no power bonus",
    "overall-only": "overall GIH WR alone",
    "deck-score-blend": "the deck score's blend (0.7 pair, 0.3 overall)",
}
NONE = "no card quality"
# Within this share of card quality's worth, a difference doesn't matter.
MARGIN = 0.02


class HorseData:
    """fit.Data's decks that quality.py rated, with each version's quality."""

    def __init__(self, feature_files, quality_files):
        self.base = d = Data(feature_files)
        q = {(f["set"], k): v for f in quality_files for k, v in f["decks"].items()}
        keep = [i for i, r in enumerate(d.rows) if (r["set"], r["id"]) in q]
        self.row = np.array(keep, dtype=int)
        self.set = d.set[self.row]
        self.sets = sorted(set(self.set))
        first = q[(d.rows[keep[0]]["set"], d.rows[keep[0]]["id"])]
        self.versions = list(first)
        self.quality = {
            v: np.array([q[(d.rows[i]["set"], d.rows[i]["id"])][v] for i in keep])
            for v in self.versions
        }
        self.fold = np.array(
            [deck_hash(f"{d.rows[i]['set']}:{d.rows[i]['id']}", "horse") % FOLDS
             for i in keep]
        )
        self.wins = d.wins[self.row]
        self.games = d.games[self.row]

    def design(self, version):
        d, r = self.base, self.row
        others = [i for i, k in enumerate(d.names) if k != QUALITY]
        cols = [] if version == NONE else [self.quality[version][:, None]]
        cols.append(d.X[r][:, others])
        cols.append(np.array([[s == t for t in self.sets] for s in self.set], dtype=float))
        cols.append(_varying(d.C[r]))
        return np.hstack(cols)


def held_out(hd, version):
    """Each deck's held-out log-likelihood under a version."""
    A = hd.design(version)
    ll = np.zeros(len(hd.row))
    for f in range(FOLDS):
        test = hd.fold == f
        beta, _ = fit_logit(A[~test], hd.wins[~test], hd.games[~test])
        p = np.clip(expit(A[test] @ beta), 1e-9, 1 - 1e-9)
        w, g = hd.wins[test], hd.games[test]
        ll[test] = w * np.log(p) + (g - w) * np.log(1 - p)
    return ll


def compare(a, b, games, mask=None):
    """(per-game gain of a over b in log-likelihood, SE), from per-deck differences."""
    if mask is not None:
        a, b, games = a[mask], b[mask], games[mask]
    diff = a - b
    r = diff.sum() / games.sum()
    se = math.sqrt(((diff - r * games) ** 2).sum()) / games.sum()
    return float(r), se


def verdict(gain, se, worth):
    low, high = gain - Z * se, gain + Z * se
    if low > 0:
        return "keep"
    if high < 0:
        return "drop"
    if max(abs(low), abs(high)) <= MARGIN * worth:
        return "no difference"
    return "can't tell"


def report(hd, out=sys.stdout):
    def w(line=""):
        print(line, file=out)

    ll = {v: held_out(hd, v) for v in [ENGINE, NONE] + list(PRIMARY) + list(SECONDARY)
          if v == NONE or v in hd.versions}
    g = hd.games
    worth, worth_se = compare(ll[ENGINE], ll[NONE], g)
    w(f"{len(hd.row)} decks and {int(g.sum())} games from {len(hd.sets)} sets; "
      f"held-out log loss per game, {FOLDS} folds. Intervals are 98.33%.")
    w()
    w(f"Card quality is worth {1000 * worth:.2f} [{1000 * (worth - Z * worth_se):.2f}, "
      f"{1000 * (worth + Z * worth_se):.2f}] millinats a game: the engine's version "
      "against no card quality at all.")
    w()
    results = {"worth": worth, "worth_se": worth_se,
               "log_loss": {v: float(-ll[v].sum() / g.sum()) for v in ll}}
    w("## Primary results")
    w()
    w("Gain: how much better the engine's version predicts than the ablation, in "
      "millinats a game (positive: the engine's is better) and as a share of what "
      "card quality is worth.")
    w()
    w("| what the engine does | ablation | gain (millinats a game) | share of card quality's worth | verdict |")
    w("|---|---|---|---|---|")
    for v, label in PRIMARY.items():
        if v not in ll:
            continue
        gain, se = compare(ll[ENGINE], ll[v], g)
        results[v] = {"gain": gain, "se": se, "share": gain / worth,
                      "verdict": verdict(gain, se, worth)}
        w(f"| {label} | `{v}` | {1000 * gain:+.3f} [{1000 * (gain - Z * se):+.3f}, "
          f"{1000 * (gain + Z * se):+.3f}] | {100 * gain / worth:+.1f}% "
          f"[{100 * (gain - Z * se) / worth:+.1f}%, {100 * (gain + Z * se) / worth:+.1f}%] "
          f"| {results[v]['verdict']} |")
    w()
    w("## Other versions")
    w()
    w("Not used for a verdict. Gain of the engine's version over each.")
    w()
    w("| version | gain (millinats a game) | share of card quality's worth |")
    w("|---|---|---|")
    for v, label in SECONDARY.items():
        if v not in ll:
            continue
        gain, se = compare(ll[ENGINE], ll[v], g)
        results[v] = {"gain": gain, "se": se, "share": gain / worth}
        w(f"| {label} | {1000 * gain:+.3f} [{1000 * (gain - Z * se):+.3f}, "
          f"{1000 * (gain + Z * se):+.3f}] | {100 * gain / worth:+.1f}% |")
    w()
    w("## By set")
    w()
    w("Gain of the engine's version over each ablation, in millinats a game (± SE).")
    w()
    w("| set | decks | card quality's worth | " + " | ".join(f"`{v}`" for v in PRIMARY) + " |")
    w("|---|---|---|" + "---|" * len(PRIMARY))
    per_set = {}
    for s in hd.sets:
        m = hd.set == s
        sw, _ = compare(ll[ENGINE], ll[NONE], g, m)
        cells = {}
        for v in PRIMARY:
            if v in ll:
                cells[v] = compare(ll[ENGINE], ll[v], g, m)
        per_set[s] = {"worth": sw, **{v: c for v, c in cells.items()}}
        w(f"| {s} | {int(m.sum())} | {1000 * sw:.2f} | "
          + " | ".join(f"{1000 * c[0]:+.3f} ± {1000 * c[1]:.3f}" for c in cells.values())
          + " |")
    results["per_set"] = per_set
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--features", nargs="+", required=True, help="From features.py")
    parser.add_argument("--quality", nargs="+", required=True, help="From quality.py")
    parser.add_argument("--json", help="Also write the results here")
    args = parser.parse_args(argv)
    load = lambda p: json.load(open(p, encoding="utf-8"))
    hd = HorseData([load(p) for p in args.features], [load(p) for p in args.quality])
    results = report(hd)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=1, default=float)


if __name__ == "__main__":
    main()

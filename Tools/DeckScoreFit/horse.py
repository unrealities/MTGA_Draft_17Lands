"""Which version of the engine's card rating best predicts deck results.

    python Tools/DeckScoreFit/horse.py --features features/*.json \
        --quality quality/*.json --json horse.json > horse.md

The inputs are features.py's and quality.py's output for the same decks.
For each version of the rating, fit.py's logistic regression with card
quality replaced by the version's deck quality is fit on four fifths of the
drafts and scored on the rest, five times. The splits are games.py's folds, so
a split's test games are in none of the win rates behind it, and all builds of
a draft are on one side. Versions are compared on held-out log loss per game,
with SEs from per-draft differences. See
experiments/2026-11-03-rating-parts/PROTOCOL.md.

Needs NumPy.
"""

import argparse
import json
import math
import sys

import numpy as np

from fit import QUALITY, Data, expit, fit_logit, varying
from games import FOLDS, fold_of

# Two-sided 98.33% intervals: 95% familywise across the three comparisons.
Z = 2.394
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
        if not keep:
            raise ValueError("no deck in the input has two main colors and ratings")
        self.row = r = np.array(keep, dtype=int)
        self.set = d.set[r]
        self.sets = sorted(set(self.set))
        self.versions = quality_files[0]["versions"]
        # (deck, split, version)
        self.quality = np.array(
            [q[(d.rows[i]["set"], d.rows[i]["id"])] for i in keep], dtype=np.float32
        )
        self.fold = np.array([fold_of(d.rows[i]["id"]) for i in keep])
        # Builds of a draft share a player, a pool and an event.
        drafts = [f"{d.rows[i]['set']}:{d.rows[i]['id'].rsplit(':', 1)[0]}" for i in keep]
        self.draft = np.unique(drafts, return_inverse=True)[1]
        self.wins = d.wins[r]
        self.games = d.games[r]
        others = [i for i, k in enumerate(d.names) if k != QUALITY]
        self.controls = np.hstack([
            d.X[r][:, others],
            (self.set[:, None] == np.array(self.sets)).astype(float),
            varying(d.C[r]),
        ])

    def design(self, version, split):
        """The model matrix under a version's quality for this split."""
        if version == NONE:
            return self.controls
        v = self.versions.index(version)
        return np.hstack([self.quality[:, split, v][:, None], self.controls])


def predictions(hd, version, split):
    """(the split's test decks, their predicted win rates), from the others'."""
    A = hd.design(version, split)
    test = hd.fold == split
    beta, _ = fit_logit(A[~test], hd.wins[~test], hd.games[~test])
    return test, np.clip(expit(A[test] @ beta), 1e-9, 1 - 1e-9)


def held_out(hd, version):
    """Each deck's held-out log-likelihood under a version."""
    ll = np.zeros(len(hd.row))
    for split in range(FOLDS):
        test, p = predictions(hd, version, split)
        w, g = hd.wins[test], hd.games[test]
        ll[test] = w * np.log(p) + (g - w) * np.log(1 - p)
    return ll


def compare(a, b, games, drafts, mask=None):
    """(per-game gain of a over b in log-likelihood, SE), from per-draft differences.

    drafts: an integer label per row.
    """
    if mask is not None:
        a, b, games, drafts = a[mask], b[mask], games[mask], drafts[mask]
    diff = a - b
    r = diff.sum() / games.sum()
    per_draft = np.bincount(drafts, weights=diff - r * games)
    return float(r), math.sqrt((per_draft ** 2).sum()) / games.sum()


def verdict(gain, se, worth):
    low, high = gain - Z * se, gain + Z * se
    if low > 0:
        return "engine's predicts better"
    if high < 0:
        return "ablation predicts better"
    if max(abs(low), abs(high)) <= MARGIN * worth:
        return "no difference"
    return "can't tell"


def report(hd, out=sys.stdout):
    def w(line=""):
        print(line, file=out)

    ll = {v: held_out(hd, v) for v in [ENGINE, NONE] + list(PRIMARY) + list(SECONDARY)
          if v == NONE or v in hd.versions}
    g = hd.games
    worth, worth_se = compare(ll[ENGINE], ll[NONE], g, hd.draft)
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
        gain, se = compare(ll[ENGINE], ll[v], g, hd.draft)
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
        gain, se = compare(ll[ENGINE], ll[v], g, hd.draft)
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
        sw, _ = compare(ll[ENGINE], ll[NONE], g, hd.draft, m)
        cells = {}
        for v in PRIMARY:
            if v in ll:
                cells[v] = compare(ll[ENGINE], ll[v], g, hd.draft, m)
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

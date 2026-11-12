"""Which part of the pair's win rates deck results object to: its level or the fit.

    python Tools/DeckScoreFit/parts.py --features features/*.json \
        --quality quality/*.json --json parts.json > parts.md

The inputs are features.py's and quality.py's output for the same decks. See
experiments/2026-11-08-pair-parts/PROTOCOL.md.

Needs NumPy.
"""

import argparse
import json
import sys

import numpy as np

from fit import fit_clustered, to_points
from horse import HorseData, compare, held_out
from rules import STRONG, _float

# The engine's blend weight averaged over a pack's 14 picks: quality.ENGINE_WEIGHT.
# (quality.py imports the app's helpers, so it isn't imported here.)
ENGINE_WEIGHT = 0.95
# t on 19 degrees of freedom: 20 sets.
T = 2.09
Z = 1.96
# A pair needs this many decks in a set for its own term.
MIN_PAIR_DECKS = 50
# Too few decks for a per-set fit to count.
MIN_SET_DECKS = 1000
BASELINE = "overall"
SINGLE = {
    "engine": ("level", "fit"),
    "fit-only": ("fit",),
    "level-only": ("level",),
}
SINGLE_LABELS = {
    "engine": "the engine's rating",
    "fit-only": "fit only (0.95 x fit)",
    "level-only": "level only (0.95 x level)",
    "free": "free slopes",
}


def verdict(weight, se, fit_gain, fit_se):
    """How the protocol reads fit's weight and fit only's held-out gain."""
    if weight - T * se <= 0:
        return "not the level"
    if fit_gain - Z * fit_se > 0:
        return "the level explains it"
    return "partly"


class PartsData(HorseData):
    """HorseData with each deck's parts and pair."""

    def __init__(self, feature_files, quality_files):
        super().__init__(feature_files, quality_files)
        d = self.base
        rows = [d.rows[i] for i in self.row]
        parts = {(f["set"], k): v for f in quality_files for k, v in f["parts"].items()}
        pairs = {(f["set"], k): v for f in quality_files for k, v in f["pairs"].items()}
        self.part_names = quality_files[0]["part_names"]
        self.parts = np.array(
            [parts[(r["set"], r["id"])] for r in rows], dtype=np.float32
        )
        self.skill = np.array([_float(r["skill"]) for r in rows])
        self.pair = np.array([f"{r['set']}:{pairs[(r['set'], r['id'])]}" for r in rows])
        self.pair_terms = self._pair_terms()
        # Each deck's rating from the four folds that aren't its own.
        self.own = self.parts[np.arange(len(rows)), self.fold]

    def _pair_terms(self):
        """Indicators for each set's pairs with enough decks, less its most common."""
        columns = []
        for s in self.sets:
            labels, counts = np.unique(self.pair[self.set == s], return_counts=True)
            order = np.argsort(-counts, kind="stable")
            for label, n in zip(labels[order][1:], counts[order][1:]):
                if n >= MIN_PAIR_DECKS:
                    columns.append(self.pair == label)
        n = len(self.pair)
        return np.array(columns, dtype=float).T.reshape(n, len(columns))

    def _part(self, P, name):
        return P[:, self.part_names.index(name)]

    def columns(self, P, model):
        """The rating columns of a model, from a parts matrix."""
        if model == BASELINE:
            return self._part(P, "overall")[:, None]
        if model == "free":
            return np.column_stack(
                [self._part(P, k) for k in ("overall", "level", "fit")]
            )
        added = sum(self._part(P, k) for k in SINGLE[model])
        return (self._part(P, "overall") + ENGINE_WEIGHT * added)[:, None]

    def design(self, version, split):
        """horse.held_out's model matrix: version is (model, with pair terms)."""
        model, with_pairs = version
        blocks = [self.columns(self.parts[:, split], model), self.controls]
        if with_pairs:
            blocks.append(self.pair_terms)
        return np.hstack(blocks)


def _usable(A, k):
    """A with the columns after the first k kept only if they tell the fit
    something: no empty columns, and one constant column at most."""
    keep, constant = list(range(k)), False
    for j in range(k, A.shape[1]):
        low, high = A[:, j].min(), A[:, j].max()
        if low == high:
            if low == 0 or constant:
                continue
            constant = True
        keep.append(j)
    return A[:, keep]


def weights(pd, names, mask, with_pairs, clustered=True):
    """{part: (weight, SE)}: each of names' slope over the overall rating's."""
    columns = ["overall"] + list(names)
    rating = np.column_stack([pd._part(pd.own[mask], k) for k in columns])
    blocks = [rating, pd.controls[mask]]
    if with_pairs:
        blocks.append(pd.pair_terms[mask])
    A = _usable(np.hstack(blocks), len(columns))
    clusters = pd.set[mask] if clustered else None
    beta, model, cluster = fit_clustered(A, pd.wins[mask], pd.games[mask], clusters)
    cov = cluster if cluster is not None else model
    return {k: to_points(beta, cov, i + 1, 0, 1.0) for i, k in enumerate(names)}


def _interval(weight, se, t=T):
    return f"{weight:+.2f} [{weight - t * se:+.2f}, {weight + t * se:+.2f}]"


def report(pd, out=sys.stdout):
    def w(line=""):
        print(line, file=out)

    everyone = np.ones(len(pd.row), dtype=bool)
    results = {}
    g = pd.games
    w(f"{len(pd.row)} decks and {int(g.sum())} games from {len(pd.sets)} sets; "
      f"{pd.pair_terms.shape[1]} color-pair-by-set terms.")
    w()

    fit_with_pairs = weights(pd, ["fit"], everyone, True)["fit"]
    level_fit = weights(pd, ["level", "fit"], everyone, False)
    results["weights"] = {"fit_with_pairs": fit_with_pairs, **level_fit}
    w("## Weights")
    w()
    w(f"A part's slope over the overall rating's. The engine assumes {ENGINE_WEIGHT}; "
      "0 is no blend. Set-clustered 95% intervals.")
    w()
    w("| part | model | weight |")
    w("|---|---|---|")
    w(f"| fit (primary) | with pair terms | {_interval(*fit_with_pairs)} |")
    w(f"| fit | no pair terms | {_interval(*level_fit['fit'])} |")
    w(f"| level | no pair terms | {_interval(*level_fit['level'])} |")
    w()

    w("## Held-out log loss")
    w()
    w("Gain over the overall rating with the same terms, in millinats a game, with "
      "1.96 per-draft SEs. Positive: predicts better than no blend.")
    w()
    w("| rating | no pair terms | with pair terms |")
    w("|---|---|---|")
    ll = {}
    for with_pairs in (False, True):
        for model in [BASELINE] + list(SINGLE) + ["free"]:
            if not (with_pairs and model == "level-only"):
                ll[(model, with_pairs)] = held_out(pd, (model, with_pairs))
    gains = {}
    for model in list(SINGLE) + ["free"]:
        cells = []
        for with_pairs in (False, True):
            key = (model, with_pairs)
            if key not in ll:
                cells.append("–")
                continue
            gain, se = compare(ll[key], ll[(BASELINE, with_pairs)], g, pd.draft)
            gains[f"{model}{'+pairs' if with_pairs else ''}"] = (gain, se)
            cells.append(f"{1000 * gain:+.3f} [{1000 * (gain - Z * se):+.3f}, "
                         f"{1000 * (gain + Z * se):+.3f}]")
        w(f"| {SINGLE_LABELS[model]} | {cells[0]} | {cells[1]} |")
    w()
    results["held_out"] = gains

    results["verdict"] = verdict(*fit_with_pairs, *gains["fit-only"])
    w(f"**By the protocol's rule: {results['verdict']}.**")
    w()

    w("## Not deciding")
    w()
    tiers = weights(pd, ["fit-few", "fit-many"], everyone, True)
    results["by_games"] = tiers
    w("Fit's weight with pair terms:")
    w()
    w("| decks or cards | weight |")
    w("|---|---|")
    w(f"| cards under 3,000 games in the pair | {_interval(*tiers['fit-few'])} |")
    w(f"| cards from 3,000 games in the pair | {_interval(*tiers['fit-many'])} |")
    by_skill = {}
    for label, mask in (("strong drafters", pd.skill >= STRONG),
                        ("the rest", pd.skill < STRONG)):
        by_skill[label] = weights(pd, ["fit"], mask, True)["fit"]
        w(f"| {label} | {_interval(*by_skill[label])} |")
    results["by_skill"] = by_skill
    w()

    w("## By set")
    w()
    w("Model SEs. Level is fit with no pair terms; fit, with them.")
    w()
    w("| set | decks | fit (± SE) | level (± SE) |")
    w("|---|---|---|---|")
    per_set = {}
    for s in pd.sets:
        m = pd.set == s
        n = int(m.sum())
        if n < MIN_SET_DECKS:
            w(f"| {s} | {n} | – | – |")
            continue
        fit = weights(pd, ["fit"], m, True, clustered=False)["fit"]
        level = weights(pd, ["level", "fit"], m, False, clustered=False)["level"]
        per_set[s] = {"decks": n, "fit": fit, "level": level}
        w(f"| {s} | {n} | {fit[0]:+.2f} ± {fit[1]:.2f} | {level[0]:+.2f} ± {level[1]:.2f} |")
    results["per_set"] = per_set
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--features", nargs="+", required=True, help="From features.py")
    parser.add_argument("--quality", nargs="+", required=True, help="From quality.py")
    parser.add_argument("--json", help="Also write the results here")
    args = parser.parse_args(argv)

    def load(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    pd = PartsData([load(p) for p in args.features], [load(p) for p in args.quality])
    results = report(pd)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=1, default=float)


if __name__ == "__main__":
    main()

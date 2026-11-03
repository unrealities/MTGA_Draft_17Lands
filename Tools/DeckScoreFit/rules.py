"""Test what three of the advisor's pick rules protect against, on game results.

    python Tools/DeckScoreFit/rules.py results/*.json > rules.md

The input is features.py's output. For each rule, a logistic regression of
each deck's games won asks whether the thing the rule steers away from (or
toward) changed how often registered decks won, beyond the average rating of
their spells. Like fit.py it controls for the set, the app's other deck
features and the player's win rate and experience buckets.

The rules, from _calculate_composition_bonus() in src/advisor/engine.py:

- Removal saturated: once the pool has more than 6 removal spells, removal
  is scored at 0.8x. Tested: is each removal spell past the sixth in a deck
  worth less than a spell of the same rating?
- Curve too heavy: once the pool has 4+ spells costing 5 or more, those are
  scored at 0.7x. Tested: is each such spell past the fourth worth less than
  a spell of the same rating?
- Needs fixing: from pack 2, while fixing cards are no more than the pool's
  off-color playables, fixing is scored at 1.4x. Tested: in decks with
  off-color spells, is a fixing card worth more while the deck has no more
  fixing cards than off-color spells than once it has more?

These are associations in observational data, not the effect of switching
the advisor's policy; see Tools/DeckScoreFit/README.md.

Needs NumPy.
"""

import argparse
import json
import math
import sys

import numpy as np

from fit import QUALITY, Data, expit

# Two-sided 98.33% intervals: 95% familywise across the three rules.
Z = 2.394
# Decks a per-set estimate needs in the region where the rule applies.
MIN_REGION = 100
# Spells in a finished deck, to turn a per-card effect into rating units.
SPELLS = 23
# Skill bucket from which a drafter counts as strong.
STRONG = 0.58


def hinge(x, knot):
    return np.maximum(0.0, x - knot)


class Rule:
    """One rule's test: its terms, the combination tested, and what it claims."""

    def __init__(self, name, label, claim, terms, estimand, direction, region, implied,
                 drop=(), secondary=None):
        self.name, self.label, self.claim = name, label, claim
        self.terms = terms  # function of the rule counts -> {term: array}
        self.estimand = estimand  # {term: coefficient multiplier}
        self.direction = direction  # sign the estimand has if the rule is right
        self.region = region  # function of the rule counts -> bool array
        self.implied = implied  # the rule's own size, in rating SDs per card
        self.drop = drop  # app features left out of the controls
        self.secondary = secondary or {}  # {label: estimand}


def fixing_terms(r):
    off = r["off_color"]
    multi = (off > 0).astype(float)
    # The engine's test: hungry while fixing <= off-color playables.
    short = np.where(off > 0, np.maximum(0.0, off + 1 - r["fixing"]), 0.0)
    return {
        "fixing": r["fixing"],
        "fixing_in_off_color_deck": r["fixing"] * multi,
        "off_color": off,
        "fixing_short": short,
    }


# The rule's own size: its multiplier applied to a card's score on the engine's
# scale (50 at the format mean, 15 points per SD), in rating SDs. Removal and
# heavy drops are taken at +1 SD (score 65), fixing at the mean (50).
RULES = [
    Rule(
        "removal_saturation",
        "Removal Saturated (0.8x past 6)",
        "a removal spell past the sixth is worth less than a spell of the same rating",
        lambda r: {"removal": r["removal"], "removal_past_6": hinge(r["removal"], 6)},
        {"removal": 1, "removal_past_6": 1},
        -1,
        lambda r: r["removal"] > 6,
        (0.8 - 1) * 65 / 15,
        secondary={
            "removal up to the sixth": {"removal": 1},
            "change in slope past the sixth": {"removal_past_6": 1},
        },
    ),
    Rule(
        "curve_heavy",
        "Curve Too Heavy (0.7x past 4)",
        "a 5+ mana spell past the fourth is worth less than a spell of the same rating",
        lambda r: {"heavy": r["heavy"], "heavy_past_4": hinge(r["heavy"], 4)},
        {"heavy": 1, "heavy_past_4": 1},
        -1,
        lambda r: r["heavy"] > 4,
        (0.7 - 1) * 65 / 15,
        secondary={
            "5+ drops up to the fourth": {"heavy": 1},
            "change in slope past the fourth": {"heavy_past_4": 1},
        },
    ),
    Rule(
        "fixing_hunger",
        "Critical: Needs Fixing (1.4x)",
        "in decks with off-color spells, a fixing card is worth more while fixing "
        "is no more than the off-color spells",
        fixing_terms,
        {"fixing_short": -1},
        1,
        lambda r: fixing_terms(r)["fixing_short"] > 0,
        (1.4 - 1) * 50 / 15,
        # missing_fixing measures the same shortfall; leave it out so the
        # rule's term isn't measured on top of it.
        drop=("missing_fixing",),
        secondary={
            "fixing card while short": {
                "fixing": 1, "fixing_in_off_color_deck": 1, "fixing_short": -1,
            },
            "fixing card once not short": {"fixing": 1, "fixing_in_off_color_deck": 1},
            "fixing card in a deck with no off-color spells": {"fixing": 1},
        },
    ),
]

DOSE = {
    "removal_saturation": ("removal", 6, [(None, 2), (3, 3), (4, 4), (5, 5), (7, 7),
                                          (8, 8), (9, 9), (10, None)]),
    "curve_heavy": ("heavy", 4, [(None, 0), (1, 1), (2, 2), (3, 3), (5, 5), (6, 6),
                                 (7, None)]),
}


class RuleData:
    """fit.Data plus the rule counts of the same decks."""

    def __init__(self, files):
        self.base = d = Data(files)
        self.counts = {
            k: np.array([r["rules"][k] for r in d.rows], dtype=float)
            for k in d.rows[0]["rules"]
        }
        self.skill = np.array([_float(r["skill"]) for r in d.rows])
        self.tags = {f["set"]: f.get("tags", {}) for f in files}
        self.win_rate = d.wins.sum() / d.games.sum()


def _float(text):
    try:
        return float(text)
    except ValueError:
        return float("nan")


def fit(A, wins, games, clusters=None):
    """Coefficients, model covariance (dispersion-widened), set-cluster covariance."""
    beta = np.zeros(A.shape[1])
    ridge = 1e-8 * np.eye(A.shape[1])
    for _ in range(100):
        p = expit(A @ beta)
        H = A.T @ (A * (games * p * (1 - p))[:, None]) + ridge
        step = np.linalg.solve(H, A.T @ (wins - games * p) - ridge @ beta)
        beta += step
        if np.abs(step).max() < 1e-9:
            break
    p = expit(A @ beta)
    H = A.T @ (A * (games * p * (1 - p))[:, None]) + ridge
    Hinv = np.linalg.inv(H)
    resid = wins - games * p
    dispersion = (resid**2 / (games * p * (1 - p))).sum() / max(1, len(wins) - A.shape[1])
    model = Hinv * max(1.0, dispersion)
    cluster = None
    if clusters is not None:
        groups = sorted(set(clusters))
        if len(groups) > 1:
            S = A * resid[:, None]
            G = np.array([S[clusters == g].sum(axis=0) for g in groups])
            cluster = Hinv @ (G.T @ G) @ Hinv * len(groups) / (len(groups) - 1)
    return beta, model, cluster


def design(rd, rule, mask, extra=False):
    """The model matrix for rows in mask, and the column of each named term."""
    d = rd.base
    names = [k for k in d.names if k not in rule.drop]
    cols = [d.X[mask][:, d.names.index(k)] for k in names]
    terms = rule.terms({k: v[mask] for k, v in rd.counts.items()})
    blocks = [np.column_stack(cols + list(terms.values()))]
    index = {k: i for i, k in enumerate(names + list(terms))}
    if extra:
        for k in ("lands", "creatures", "colors"):
            if k in d.extra_names:
                blocks.append(d.extra[mask][:, [d.extra_names.index(k)]])
    sets = sorted(set(d.set[mask]))
    blocks.append(d.set_dummies(mask, sets))
    blocks.append(_varying(d.C[mask]))
    return np.hstack(blocks), index


def _varying(C):
    """Player bucket columns that vary in these rows (others are collinear)."""
    return C[:, C.min(axis=0) != C.max(axis=0)] if len(C) else C


def estimate(rd, rule, mask, extra=False, estimand=None):
    """{pp, se, se_model, se_cluster, sd, sd_se} of the estimand on the rows in mask."""
    return estimates(rd, rule, mask, extra, [estimand or rule.estimand])[0]


def estimates(rd, rule, mask, extra=False, estimands=()):
    """estimate() for each of several estimands, from one fit."""
    d = rd.base
    A, index = design(rd, rule, mask, extra)
    beta, model, cluster = fit(A, d.wins[mask], d.games[mask], d.set[mask])
    del A
    per_pp = 100 * rd.win_rate * (1 - rd.win_rate)
    q = index[QUALITY]
    out = []
    for estimand in estimands:
        g = np.zeros(len(beta))
        for k, m in estimand.items():
            g[index[k]] = m
        value = g @ beta
        se_model = math.sqrt(g @ model @ g)
        se_cluster = math.sqrt(g @ cluster @ g) if cluster is not None else None
        se = max(se_model, se_cluster or 0.0)
        cov = model if cluster is None or se_cluster < se_model else cluster
        # In rating SDs per card: the change in a spell's rating, in format
        # SDs, that would move card quality (a mean over SPELLS spells) as much.
        sd = SPELLS * value / beta[q]
        h = g * SPELLS / beta[q]
        h[q] = -SPELLS * value / beta[q] ** 2
        out.append({
            "logit": value,
            "pp": per_pp * value,
            "se": per_pp * se,
            "se_model": per_pp * se_model,
            "se_cluster": per_pp * se_cluster if se_cluster is not None else None,
            "sd": sd,
            "sd_se": math.sqrt(h @ cov @ h),
        })
    return out


def usable_sets(rd, rule):
    """Sets where some deck reaches the rule's region (else its tags are missing)."""
    region = rule.region(rd.counts)
    return [s for s in rd.base.sets if region[rd.base.set == s].any()]


def verdict(rule, est):
    low, high = est["pp"] - Z * est["se"], est["pp"] + Z * est["se"]
    if low > 0 or high < 0:
        agrees = (low > 0) == (rule.direction > 0)
        return "supported" if agrees else "contradicted"
    return "not established"


def dose(rd, rule, mask):
    """Win rate of decks at each count against decks at the knot, in points."""
    var, ref, buckets = DOSE[rule.name]
    x = rd.counts[var][mask]
    rows = []  # (label, indicator or None for the reference)
    for lo, hi in sorted(buckets + [(ref, ref)], key=lambda b: -1 if b[0] is None else b[0]):
        sel = np.ones(len(x), dtype=bool)
        if lo is not None:
            sel &= x >= lo
        if hi is not None:
            sel &= x <= hi
        rows.append((_bucket(lo, hi), sel, lo == ref))
    d = rd.base
    names = [k for k in d.names if k not in rule.drop]
    cols = [sel.astype(float) for _, sel, is_ref in rows if not is_ref]
    X = np.column_stack([d.X[mask][:, d.names.index(k)] for k in names] + cols)
    sets = sorted(set(d.set[mask]))
    A = np.hstack([X, d.set_dummies(mask, sets), _varying(d.C[mask])])
    beta, model, cluster = fit(A, d.wins[mask], d.games[mask], d.set[mask])
    per_pp = 100 * rd.win_rate * (1 - rd.win_rate)
    out, j = [], len(names)
    for label, sel, is_ref in rows:
        if is_ref:
            out.append((f"{label} (reference)", int(sel.sum()), 0.0, 0.0))
            continue
        se = math.sqrt(max(model[j, j], cluster[j, j] if cluster is not None else 0))
        out.append((label, int(sel.sum()), per_pp * beta[j], per_pp * se))
        j += 1
    return var, out


def _bucket(lo, hi):
    if lo is None:
        return f"{hi} or fewer"
    if hi is None:
        return f"{lo} or more"
    return str(lo) if lo == hi else f"{lo}–{hi}"


def interval(est):
    return f"[{est['pp'] - Z * est['se']:+.2f}, {est['pp'] + Z * est['se']:+.2f}]"


def report(rd, out=sys.stdout):
    w = lambda line="": print(line, file=out)
    d = rd.base
    w("## Data")
    w()
    w(
        f"{len(d.set)} decks and {int(d.games.sum())} games from {len(d.sets)} sets "
        f"({', '.join(d.sets)}); game win rate {rd.win_rate:.1%}. "
        f"{d.unfinished} unfinished decks were left out."
    )
    w()
    w("Cards tagged by the app, per set (the rules see only tagged cards):")
    w()
    w("| set | removal | fixing_ramp |")
    w("|---|---|---|")
    for s in d.sets:
        t = rd.tags.get(s, {})
        w(f"| {s} | {t.get('removal', '?')} | {t.get('fixing_ramp', '?')} |")
    w()

    results = {}
    w("## Primary results")
    w()
    w(
        "Per card, in game win rate points (at the overall win rate), with "
        "98.33% intervals: 95% familywise across the "
        "three rules. Each SE is the larger of the model's (widened for "
        "overdispersion) and the set-clustered one. *Rating SDs*: the same "
        "effect as a change in that card's rating, in the format's SDs of GIH WR. "
        "*The rule's size*: what the rule's multiplier does to a card's score, "
        "in the same units."
    )
    w()
    w(
        "| rule | tested claim | sets | decks in region | per card (points) | "
        "interval | rating SDs | the rule's size | verdict |"
    )
    w("|---|---|---|---|---|---|---|---|---|")
    for rule in RULES:
        sets = usable_sets(rd, rule)
        mask = np.isin(d.set, sets)
        labels = list(rule.secondary)
        est, *others = estimates(
            rd, rule, mask, estimands=[rule.estimand] + list(rule.secondary.values())
        )
        region = rule.region(rd.counts)[mask]
        results[rule.name] = {
            "sets": sets,
            "estimate": est,
            "verdict": verdict(rule, est),
            "secondary": dict(zip(labels, others)),
        }
        w(
            f"| {rule.label} | {rule.claim} | {len(sets)} | "
            f"{region.sum()} ({region.mean():.1%}) | {est['pp']:+.2f} | "
            f"{interval(est)} | {est['sd']:+.2f} ± {est['sd_se']:.2f} | "
            f"{rule.implied:+.2f} | {results[rule.name]['verdict']} |"
        )
    w()
    w(
        "*Supported*: the interval excludes zero in the rule's direction. "
        "*Contradicted*: it excludes zero the other way. *Not established*: it "
        "includes zero."
    )
    w()

    w("## Uncertainty and sensitivity")
    w()
    w(
        "Per card, in game win rate points (SE). *Model* and *set-clustered* SEs "
        "of the primary fit; *with counts*: lands, creatures and colors added as "
        f"controls; *strong drafters*: skill bucket {STRONG:.0%} or more."
    )
    w()
    w("| rule | primary | model SE | set-clustered SE | with counts | strong drafters |")
    w("|---|---|---|---|---|---|")
    for rule in RULES:
        sets = results[rule.name]["sets"]
        mask = np.isin(d.set, sets)
        est = results[rule.name]["estimate"]
        counts = estimate(rd, rule, mask, extra=True)
        strong = estimate(rd, rule, mask & (rd.skill >= STRONG))
        results[rule.name]["with_counts"] = counts
        results[rule.name]["strong"] = strong
        cl = f"{est['se_cluster']:.2f}" if est["se_cluster"] is not None else "–"
        w(
            f"| {rule.label} | {est['pp']:+.2f} | {est['se_model']:.2f} | {cl} | "
            f"{counts['pp']:+.2f} ({counts['se']:.2f}) | "
            f"{strong['pp']:+.2f} ({strong['se']:.2f}) |"
        )
    w()

    w("## Other contrasts")
    w()
    w("Per card, in game win rate points (SE), from the primary fit.")
    w()
    w("| rule | contrast | per card |")
    w("|---|---|---|")
    for rule in RULES:
        for label, est in results[rule.name]["secondary"].items():
            w(f"| {rule.label} | {label} | {est['pp']:+.2f} ({est['se']:.2f}) |")
    w()

    w("## By set")
    w()
    w(
        "The primary estimate fit on each set alone, per card in game win rate "
        f"points. Sets with fewer than {MIN_REGION} decks in the rule's region "
        "are marked –."
    )
    w()
    w("| set | " + " | ".join(r.label for r in RULES) + " |")
    w("|---" * (len(RULES) + 1) + "|")
    per_set = {r.name: {} for r in RULES}
    for s in d.sets:
        cells = []
        for rule in RULES:
            mask = d.set == s
            if s not in results[rule.name]["sets"] or (
                rule.region(rd.counts)[mask].sum() < MIN_REGION
            ):
                cells.append("–")
                continue
            est = estimate(rd, rule, mask)
            per_set[rule.name][s] = est
            cells.append(f"{est['pp']:+.2f} ({est['se']:.2f})")
        w(f"| {s} | " + " | ".join(cells) + " |")
    signs = []
    for rule in RULES:
        ests = per_set[rule.name].values()
        agree = sum(np.sign(e["pp"]) == rule.direction for e in ests)
        signs.append(f"{agree}/{len(ests)}")
        results[rule.name]["per_set"] = per_set[rule.name]
    w("| sets in the rule's direction | " + " | ".join(signs) + " |")
    w()

    w("## By count")
    w()
    w(
        "Game win rate points of decks at each count against decks at the "
        "rule's threshold, at the same card quality (SE)."
    )
    w()
    for rule in RULES:
        if rule.name not in DOSE:
            continue
        mask = np.isin(d.set, results[rule.name]["sets"])
        var, rows = dose(rd, rule, mask)
        results[rule.name]["by_count"] = rows
        w(f"**{rule.label}**, {var} spells in the deck:")
        w()
        w("| count | decks | points |")
        w("|---|---|---|")
        for label, n, pp, se in rows:
            cell = "0" if "reference" in label else f"{pp:+.2f} ({se:.2f})"
            w(f"| {label} | {n} | {cell} |")
        w()
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("files", nargs="+", help="From features.py, one per set")
    parser.add_argument("--json", help="Also write the results here")
    args = parser.parse_args(argv)
    files = []
    for path in args.files:
        with open(path, encoding="utf-8") as f:
            files.append(json.load(f))
    results = report(RuleData(files))
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=1, default=float)


if __name__ == "__main__":
    main()

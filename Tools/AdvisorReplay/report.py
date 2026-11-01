"""Compare two replays of the same drafts and write a Markdown report.

    python Tools/AdvisorReplay/report.py results/*.json > summary.md

Each input is a replay.py result labelled base or head. Drafts are paired by
draft_id, so differences between base and head come with paired bootstrap
standard errors.
"""

import argparse
import json
from collections import defaultdict

import numpy as np

LABELS = ("base", "head")

# A drafter counts as strong with a 60%+ game win rate over 50+ games.
STRONG_WIN_RATE = 0.6
STRONG_MIN_GAMES = 50

BOOTSTRAP_SAMPLES = 200

# (column title, which drafters, which picks).
PICK_COLUMNS = [
    ("all drafters", "all", lambda pack, pick: True),
    ("strong drafters", "strong", lambda pack, pick: True),
    ("strong, pack 1", "strong", lambda pack, pick: pack == 1),
    ("strong, pack 3", "strong", lambda pack, pick: pack == 3),
    ("strong, picks 1-4", "strong", lambda pack, pick: pick <= 4),
]


def load(paths):
    """{label: {set: {draft_id: draft}}}, keeping only drafts both labels replayed."""
    runs = {label: defaultdict(dict) for label in LABELS}
    for path in paths:
        with open(path, encoding="utf-8") as f:
            result = json.load(f)
        for draft in result["drafts"]:
            runs[result["label"]][result["set"]][draft["id"]] = draft
    for code in set(runs["base"]) | set(runs["head"]):
        both = runs["base"][code].keys() & runs["head"][code].keys()
        for label in LABELS:
            runs[label][code] = {i: runs[label][code][i] for i in sorted(both)}
    return runs


def flat(runs, label):
    """label's drafts in one list, set by set (the same order for base and head)."""
    return [d for code in sorted(runs[label]) for d in runs[label][code].values()]


def is_strong(draft):
    return (draft["skill"] or 0) >= STRONG_WIN_RATE and (
        draft["games"] or 0
    ) >= STRONG_MIN_GAMES


def is_complete(draft):
    """Finished events only, so wins aren't cut short by the dump date."""
    return draft["wins"] == 7 or draft["losses"] == 3


def agreement(drafts, column, rank_field=2):
    """(top-1 %, top-3 %) of the picks in column, for drafts as a list."""
    _, who, which = column
    ranks = [
        p[rank_field]
        for d in drafts
        if who == "all" or is_strong(d)
        for p in d["picks"]
        if which(p[0], p[1])
    ]
    if not ranks:
        return None
    ranks = np.array(ranks)
    return 100 * (ranks == 0).mean(), 100 * (ranks < 3).mean()


def top1_per_draft(drafts):
    """Each draft's (top-1 matches, picks scored), for bootstrapping."""
    return np.array(
        [[sum(p[2] == 0 for p in d["picks"]), len(d["picks"])] for d in drafts],
        dtype=float,
    )


# --- Event wins ---------------------------------------------------------------


def _dummies(values):
    """Indicator columns for each value but the first."""
    levels = sorted(set(values), key=str)[1:]
    return [np.array([float(v == level) for v in values]) for level in levels]


def controls(drafts, sets):
    """Intercept plus set, skill bucket and games bucket indicators."""
    skill = [
        (
            None
            if d["skill"] is None
            else int((min(max(d["skill"], 0.30), 0.74) - 0.30) // 0.04)
        )
        for d in drafts
    ]
    columns = _dummies(sets) + _dummies(skill) + _dummies([d["games"] for d in drafts])
    return np.column_stack([np.ones(len(drafts)), *columns])


def wins_slope(x, wins, ctrl):
    """Δevent wins per +1 SD of x, controlling for ctrl's columns (least squares)."""
    X = np.column_stack([x / (x.std() or 1.0), ctrl])
    return np.linalg.lstsq(X, wins, rcond=None)[0][0]


def within_set(values, sets):
    """values as z-scores within each set (scores aren't comparable across sets)."""
    out = np.zeros(len(values))
    for code in set(sets):
        idx = [i for i, s in enumerate(sets) if s == code]
        v = values[idx]
        out[idx] = (v - v.mean()) / (v.std() or 1.0)
    return out


def bootstrap(fn, n, samples=BOOTSTRAP_SAMPLES, seed=0):
    """Standard deviation of fn(resampled draft indices) over bootstrap samples."""
    rng = np.random.default_rng(seed)
    return float(np.std([fn(rng.integers(0, n, n)) for _ in range(samples)]))


# --- Report -------------------------------------------------------------------


def _cell(pair):
    return "–" if pair is None else f"{pair[0]:.1f} / {pair[1]:.1f}"


def pick_table(runs):
    base, head = flat(runs, "base"), flat(runs, "head")
    rows = [("base", base, 2), ("head", head, 2), ("highest GIH WR", head, 4)]
    lines = [
        "Cells are top-1 % / top-3 %: how often the card the drafter took was the "
        "advisor's first choice, or among its first three.",
        "",
        "| advisor | " + " | ".join(c[0] for c in PICK_COLUMNS) + " |",
        "|---|" + "---|" * len(PICK_COLUMNS),
    ]
    for name, drafts, field in rows:
        cells = [_cell(agreement(drafts, c, field)) for c in PICK_COLUMNS]
        lines.append(f"| {name} | " + " | ".join(cells) + " |")

    b, h = top1_per_draft(base), top1_per_draft(head)

    def diff(idx):
        return 100 * (
            h[idx, 0].sum() / h[idx, 1].sum() - b[idx, 0].sum() / b[idx, 1].sum()
        )

    all_idx = np.arange(len(base))
    lines += [
        "",
        f"Top-1, head minus base: **{diff(all_idx):+.1f} points** "
        f"(paired bootstrap SE {bootstrap(diff, len(base)):.1f}).",
    ]
    return "\n".join(lines)


def wins_table(runs):
    """Event wins against how closely drafters followed each advisor, and against deck score."""
    sets = [code for code in sorted(runs["base"]) for _ in runs["base"][code]]
    base, head = flat(runs, "base"), flat(runs, "head")
    keep = [
        i
        for i, (b, h) in enumerate(zip(base, head))
        if is_complete(b) and b["picks"] and h["picks"] and b["deck_score"] is not None
    ]
    if len(keep) < 100:
        return "Fewer than 100 complete events; no win statistics."
    sets = [sets[i] for i in keep]
    base, head = [base[i] for i in keep], [head[i] for i in keep]
    wins = np.array([d["wins"] for d in base])
    ctrl = controls(base, sets)

    def mean_regret(drafts):
        return np.array([np.mean([p[3] for p in d["picks"]]) for d in drafts])

    columns = {
        "regret: base": mean_regret(base),
        "regret: head": mean_regret(head),
        "deck score: base": within_set(np.array([d["deck_score"] for d in base]), sets),
        "deck score: head": within_set(np.array([d["deck_score"] for d in head]), sets),
        "pool GIH WR": within_set(np.array([d["pool_gihwr"] for d in base]), sets),
    }

    def slope(name, idx=slice(None)):
        return wins_slope(columns[name][idx], wins[idx], ctrl[idx])

    def row(title, what, better):
        b, h = slope(f"{what}: base"), slope(f"{what}: head")
        se = bootstrap(
            lambda i: slope(f"{what}: head", i) - slope(f"{what}: base", i), len(wins)
        )
        return f"| {title} | {b:+.3f} | {h:+.3f} | **{h - b:+.3f}** ({se:.3f}) | {better} |"

    return "\n".join(
        [
            f"{len(wins)} complete events. Δevent wins per +1 SD of each measure, controlling "
            "for set and the drafter's win rate and games buckets. Differences have paired "
            "bootstrap SEs.",
            "",
            "| measure | base | head | head minus base (SE) | better is |",
            "|---|---|---|---|---|",
            row(
                "regret: how far the drafter's picks fell below the advisor's top choice",
                "regret",
                "more negative",
            ),
            row("final pool's deck score (within set)", "deck score", "more positive"),
            f"| pool GIH WR, a yardstick (within set) | {slope('pool GIH WR'):+.3f} | | | |",
        ]
    )


def per_set_table(runs):
    lines = [
        "| set | drafts | top-1 base | top-1 head | head minus base |",
        "|---|---|---|---|---|",
    ]
    for code in sorted(runs["base"]):
        b = agreement(list(runs["base"][code].values()), PICK_COLUMNS[0])
        h = agreement(list(runs["head"][code].values()), PICK_COLUMNS[0])
        if b and h:
            lines.append(
                f"| {code} | {len(runs['base'][code])} | {b[0]:.1f} | {h[0]:.1f} | {h[0] - b[0]:+.1f} |"
            )
    return "\n".join(lines)


def report(runs):
    return "\n\n".join(
        [
            "## Picks",
            pick_table(runs),
            "## Event wins",
            wins_table(runs),
            "## Top-1 by set (all drafters)",
            per_set_table(runs),
        ]
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("results", nargs="+", help="replay.py results, base and head")
    args = parser.parse_args(argv)
    print(report(load(args.results)))


if __name__ == "__main__":
    main()

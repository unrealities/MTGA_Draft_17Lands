"""Report on lanes.py results: how often each lane rule names the played colors.

    python Tools/AdvisorReplay/lanes_report.py results/*.lanes.json

A lane's pair is its first two colors. At a pick it is "right" when the pair
and the played deck's main colors agree (one holds the other, so a two-color
lane inside a three-color deck counts), "wrong" when it names a pair that
doesn't, and "open" when it names fewer than two colors. Net is right minus
wrong, in points of picks. Differences from the app's rule have paired
bootstrap SEs over drafts. Needs only NumPy.
"""

import argparse
import json

import numpy as np

BOOTSTRAP_SAMPLES = 1000
# Cards in the pool; the app changes rule at 15.
BANDS = [(1, 4), (5, 9), (10, 14), (15, 19), (20, 27), (28, 99)]


def verdict(lane, played):
    """'right', 'wrong' or 'open' for one lane against the played colors."""
    if len(lane) < 2:
        return "open"
    pair, deck = set(lane[:2]), set(played)
    return "right" if pair <= deck or deck <= pair else "wrong"


def tally(runs):
    """Per-draft counts: {"n": [bands, drafts], arm: {"right"|"wrong"|"three"|
    "differs"|"changes": [bands, drafts]}}, with each draft's set."""
    arms = runs[0]["arms"]
    drafts = [(run["set"], d) for run in runs for d in run["drafts"] if d["picks"]]
    shape = (len(BANDS), len(drafts))
    out = {"n": np.zeros(shape), "sets": np.array([s for s, _ in drafts])}
    for arm in arms:
        out[arm] = {
            k: np.zeros(shape) for k in ("right", "wrong", "three", "differs", "changes")
        }
    for j, (_, draft) in enumerate(drafts):
        last = {}
        for _, _, size, lanes in draft["picks"]:
            if not size:  # none of the pool's cards are in the dataset
                continue
            b = next(i for i, (lo, hi) in enumerate(BANDS) if lo <= size <= hi)
            out["n"][b, j] += 1
            for arm, lane in zip(arms, lanes):
                cell = out[arm]
                v = verdict(lane, draft["played"])
                if v != "open":
                    cell[v][b, j] += 1
                    pair = frozenset(lane[:2])
                    cell["changes"][b, j] += last.get(arm, pair) != pair
                    last[arm] = pair
                cell["three"][b, j] += len(lane) >= 3
                cell["differs"][b, j] += frozenset(lane[:2]) != frozenset(lanes[0][:2])
    return arms, out


def bootstrap_se(fn, n, samples=BOOTSTRAP_SAMPLES, seed=0):
    rng = np.random.default_rng(seed)
    return float(np.std([fn(rng.integers(0, n, n)) for _ in range(samples)]))


def pct(x, n):
    return 100.0 * x.sum() / max(1.0, n.sum())


def net(cell, n, rows=slice(None), idx=slice(None)):
    return pct(cell["right"][rows, idx] - cell["wrong"][rows, idx], n[rows, idx])


def overall_table(arms, t):
    n, n_drafts = t["n"], t["n"].shape[1]
    lines = [
        "| rule | names a pair | right | wrong | net | net minus app (SE) | pair differs from app | pair changes a draft | names 3 colors |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for arm in arms:
        c = t[arm]
        if arm == arms[0]:
            diff = ""
        else:
            fn = lambda idx, c=c: net(c, n, idx=idx) - net(t[arms[0]], n, idx=idx)
            diff = f"**{fn(slice(None)):+.2f}** ({bootstrap_se(fn, n_drafts):.2f})"
        lines.append(
            f"| {arm} | {pct(c['right'] + c['wrong'], n):.1f}% | {pct(c['right'], n):.1f}% "
            f"| {pct(c['wrong'], n):.1f}% | {net(c, n):+.1f} | {diff} "
            f"| {pct(c['differs'], n):.1f}% | {c['changes'].sum() / n_drafts:.2f} "
            f"| {pct(c['three'], n):.1f}% |"
        )
    return lines


def band_table(arms, t):
    n, n_drafts = t["n"], t["n"].shape[1]
    lines = [
        "| cards in pool | app: names a pair | app: right | app: wrong | app: net | "
        + " | ".join(f"{a} minus app (SE)" for a in arms[1:])
        + " |",
        "|---|---|---|---|---|" + "---|" * (len(arms) - 1),
    ]
    app = t[arms[0]]
    for b, (lo, hi) in enumerate(BANDS):
        rows = slice(b, b + 1)
        cells = []
        for arm in arms[1:]:
            fn = lambda idx, c=t[arm]: net(c, n, rows, idx) - net(app, n, rows, idx)
            cells.append(f"{fn(slice(None)):+.2f} ({bootstrap_se(fn, n_drafts):.2f})")
        nb = n[rows]
        lines.append(
            f"| {lo}{'+' if hi == 99 else f'-{hi}'} | {pct(app['right'][rows] + app['wrong'][rows], nb):.1f}% "
            f"| {pct(app['right'][rows], nb):.1f}% | {pct(app['wrong'][rows], nb):.1f}% "
            f"| {net(app, n, rows):+.1f} | " + " | ".join(cells) + " |"
        )
    return lines


def set_table(arms, t):
    lines = [
        "| set | drafts | app: net | " + " | ".join(f"{a} minus app" for a in arms[1:]) + " |",
        "|---|---|---|" + "---|" * (len(arms) - 1),
    ]
    for s in sorted(set(t["sets"])):
        idx = np.flatnonzero(t["sets"] == s)
        base = net(t[arms[0]], t["n"], idx=idx)
        cells = [f"{net(t[a], t['n'], idx=idx) - base:+.2f}" for a in arms[1:]]
        lines.append(f"| {s} | {len(idx)} | {base:+.1f} | " + " | ".join(cells) + " |")
    return lines


def report(runs):
    arms, t = tally(runs)
    played = [len(d["played"]) for run in runs for d in run["drafts"] if d["picks"]]
    skipped = {}
    for run in runs:
        for why, k in run.get("skipped", {}).items():
            skipped[why] = skipped.get(why, 0) + k
    shares = ", ".join(
        f"{100 * sum(p == k for p in played) / len(played):.1f}% {name}"
        for k, name in ((1, "one"), (2, "two"), (3, "three"))
    )
    lines = [
        f"{len(played)} drafts, {int(t['n'].sum())} picks. Played decks' main colors: {shares}.",
        f"Left out: {skipped or 'nothing'}.",
        "",
        "## All picks",
        "",
        *overall_table(arms, t),
        "",
        "## Net by cards in the pool",
        "",
        *band_table(arms, t),
        "",
        "## Net by set",
        "",
        *set_table(arms, t),
    ]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("results", nargs="+", help="Results from lanes.py")
    args = parser.parse_args(argv)
    runs = []
    for path in args.results:
        with open(path, encoding="utf-8") as f:
            runs.append(json.load(f))
    print(report(runs))


if __name__ == "__main__":
    main()

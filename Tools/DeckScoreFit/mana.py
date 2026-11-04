"""Test the deck builder's Monte Carlo penalties on draw luck in real games.

    python Tools/DeckScoreFit/mana.py --features features/*.json \
        --hands hands/*.json --json mana.json > mana.md

The inputs are features.py's and hands.py's output for the same decks. Within
a deck, a 7-card keep's chance of screw, flood or color screw is luck, so a
linear probability model with a deck fixed effect measures what each event
costs in win rate. With how much a point of simulate_deck()'s rate raises the
real chance of the event in kept hands, and what card quality is worth per
deck score point, that puts each penalty's claim (so many score points per
point of rate past a threshold) against the data. See README.md.

Needs NumPy.
"""

import argparse
import json
import math
import sys
from math import comb

import numpy as np

from fit import QUALITY, Data
from rules import _varying, fit, keep_or_drop

# Two-sided 98.75% intervals: 95% familywise across the three penalties and
# all three together.
Z = 2.498

# (rate, label, ablation, threshold, points per rate point), from suggest_deck().
PENALTIES = [
    ("color_screw_t3", "Color Screw", "no-mc-color", 10.0, 2.5),
    ("screw_t3", "Mana Screw", "no-mc-screw", 22.0, 1.5),
    ("flood_t5", "Flood Risk", "no-mc-flood", 27.0, 1.5),
]
RATES = [p[0] for p in PENALTIES]
# Columns of hands.py's game rows: on play, mulligans, won, lands in hand,
# then the chance of each event.
CHANCE = {"screw_t3": 4, "flood_t5": 5, "color_screw_t3": 6}
HAND_BINS = ["0-1", "2", "3", "4", "5", "6-7"]
# A dump that records mulligans in fewer games than this (percent) logs most
# of them as 7-card keeps (DMU's: 0.15%, with 6-card hands), so it is left out.
MIN_MULLIGANS = 2.0


def mulligan_rate(hand_file):
    games = [g for deck in hand_file["decks"] for g in deck["games"]]
    return 100.0 * sum(g[1] > 0 for g in games) / max(1, len(games))


class ManaData:
    """fit.Data's decks that hands.py simulated, and their games."""

    def __init__(self, feature_files, hand_files):
        self.base = d = Data(feature_files)
        self.left_out = {f["set"]: mulligan_rate(f) for f in hand_files
                         if mulligan_rate(f) < MIN_MULLIGANS}
        hand_files = [f for f in hand_files if f["set"] not in self.left_out]
        index = {(r["set"], r["id"]): i for i, r in enumerate(d.rows)}
        decks = [
            (index[(f["set"], deck["id"])], deck)
            for f in hand_files
            for deck in f["decks"]
            if (f["set"], deck["id"]) in index
        ]
        self.row = np.array([i for i, _ in decks], dtype=int)
        self.set = d.set[self.row]
        self.sets = sorted(set(self.set))
        self.lands = np.array([deck["lands"] for _, deck in decks], dtype=float)
        self.sim = {
            k: np.array([deck["sim"][k] for _, deck in decks])
            for k in RATES + ["mulligans"]
        }
        self.kept7 = {
            k: np.array([deck["kept7"][k] for _, deck in decks])
            for k in RATES + ["keep"]
        }
        rows = [(j, g) for j, (_, deck) in enumerate(decks) for g in deck["games"]]
        self.g_deck = np.array([j for j, _ in rows], dtype=int)
        g = np.array([[np.nan if v is None else v for v in r] for _, r in rows],
                     dtype=float).reshape(len(rows), 7)
        self.g_play, self.g_mull, self.g_won = g[:, 0], g[:, 1], g[:, 2]
        self.kept = ~np.isnan(g[:, 3])
        self.g_h = g[:, 3]
        self.g_chance = {k: g[:, c] for k, c in CHANCE.items()}
        self.win_rate = self.g_won.mean() if len(rows) else 0.5


def _cluster_cov(X, e, groups, bread):
    S = X * e[:, None]
    _, inv = np.unique(groups, return_inverse=True)
    G = np.zeros((inv.max() + 1, X.shape[1]))
    np.add.at(G, inv, S)
    n = len(G)
    return bread @ (G.T @ G) @ bread * (n / (n - 1) if n > 1 else 1.0)


def within(md, columns, mask=None):
    """Deck fixed-effect LPM of keeps' results: (beta, deck-cluster cov, set-cluster cov)."""
    k = md.kept if mask is None else md.kept & mask
    deck = md.g_deck[k]
    _, deck = np.unique(deck, return_inverse=True)
    n = np.bincount(deck).astype(float)

    def demean(x):
        return x - (np.bincount(deck, x) / n)[deck]

    X = np.column_stack([demean(c[k]) for c in columns])
    y = demean(md.g_won[k])
    bread = np.linalg.pinv(X.T @ X)
    beta = bread @ X.T @ y
    e = y - X @ beta
    return (beta, _cluster_cov(X, e, deck, bread),
            _cluster_cov(X, e, md.set[md.g_deck[k]], bread))


def event_costs(md, mask=None):
    """Each event's cost in win probability (0-1): (beta, cov by deck, cov by set)."""
    cols = [md.g_chance[k] for k in RATES] + [md.g_play]
    beta, by_deck, by_set = within(md, cols, mask)
    return beta[:3], by_deck[:3, :3], by_set[:3, :3]


def kept_means(md, key):
    """Each deck's mean chance of an event over its keeps, in percent, and its keeps."""
    k = md.kept
    n = np.bincount(md.g_deck[k], minlength=len(md.row)).astype(float)
    total = np.bincount(md.g_deck[k], md.g_chance[key][k], minlength=len(md.row))
    return 100 * total / np.maximum(n, 1), n


def calibration(md, key):
    """(slope, var by deck, var by set) of the real chance in keeps on simulate_deck()'s rate."""
    y, w = kept_means(md, key)
    m = w > 0
    sets = sorted(set(md.set[m]))
    D = np.array([[s == t for t in sets[1:]] for s in md.set[m]], dtype=float)
    X = np.column_stack([md.sim[key][m], np.ones(m.sum()), D.reshape(m.sum(), -1)])
    Xw = X * w[m][:, None]
    bread = np.linalg.pinv(X.T @ Xw)
    beta = bread @ Xw.T @ y[m]
    e = y[m] - X @ beta
    by_deck = _cluster_cov(Xw, e, np.arange(m.sum()), bread)
    by_set = _cluster_cov(Xw, e, md.set[m], bread)
    return beta[0], by_deck[0, 0], by_set[0, 0]


def deck_fit(md, hinges=False):
    """fit.py's model of the simulated decks: (beta, model cov, set cov, column index)."""
    d = md.base
    r = md.row
    cols = [d.X[r]]
    index = {k: i for i, k in enumerate(d.names)}
    if hinges:
        for k, _, _, t, _ in PENALTIES:
            past = np.maximum(0.0, md.sim[k] - t)
            if past.any():
                index[k] = sum(c.shape[1] for c in cols)
                cols.append(past[:, None])
    mask = np.zeros(len(d.set), dtype=bool)
    mask[r] = True
    sets = sorted(set(d.set[r]))
    cols.append(np.array([[s == t for t in sets] for s in d.set[r]], dtype=float))
    cols.append(_varying(d.C[r]))
    A = np.hstack(cols)
    beta, model, cluster = fit(A, d.wins[r], d.games[r], d.set[r])
    return beta, model, cluster, index


def _delta(f, theta, cov, eps=1e-6):
    g = np.array([(f(theta + eps * np.eye(len(theta))[i]) - f(theta - eps * np.eye(len(theta))[i]))
                  / (2 * eps) for i in range(len(theta))])
    return float(g @ cov @ g)


def _block(*blocks):
    n = sum(len(b) for b in blocks)
    out, i = np.zeros((n, n)), 0
    for b in blocks:
        out[i:i + len(b), i:i + len(b)] = b
        i += len(b)
    return out


def primary(md):
    """Each penalty's value from the data, in score points per point of rate."""
    d = md.base
    cost, cost_deck, cost_set = event_costs(md)
    cal = [calibration(md, k) for k in RATES]
    beta, model, cluster, index = deck_fit(md)
    q = index[QUALITY]
    scale = d.weights[QUALITY]
    share = md.kept.mean()
    p = md.win_rate
    theta = np.concatenate([cost, [c[0] for c in cal], [beta[q]]])
    covs = [
        _block(cost_deck, np.diag([c[1] for c in cal]), [[model[q, q]]]),
        # fit() has no set-clustered covariance with one set.
        _block(cost_set, np.diag([c[2] for c in cal]),
               [[(model if cluster is None else cluster)[q, q]]]),
    ]

    def values(t):
        return scale * share * t[:3] * t[3:6] / (100 * p * (1 - p) * t[6])

    v = values(theta)
    out = {}
    for i, (k, label, ablation, threshold, weight) in enumerate(PENALTIES):
        se = math.sqrt(max(_delta(lambda t: values(t)[i], theta, c) for c in covs))
        out[k] = {
            "label": label,
            "ablation": ablation,
            "threshold": threshold,
            "weight": weight,
            "cost_pp": 100 * cost[i],
            "cost_se": 100 * math.sqrt(max(cost_deck[i, i], cost_set[i, i])),
            "calibration": cal[i][0],
            "calibration_se": math.sqrt(max(cal[i][1], cal[i][2])),
            "points": float(v[i]),
            "se": se,
            "keep_or_drop": keep_or_drop(-weight, float(v[i]), se, Z),
            "decks_past_threshold": int((md.sim[k] > threshold).sum()),
        }
    past = np.column_stack([np.maximum(0.0, md.sim[k] - t) for k, _, _, t, _ in PENALTIES])
    hit = past.sum(axis=1) > 0
    mean_past = past[hit].mean(axis=0) if hit.any() else np.zeros(3)
    size = -float(sum(w * h for (_, _, _, _, w), h in zip(PENALTIES, mean_past)))

    def total(t):
        return float(values(t) @ mean_past)

    se = math.sqrt(max(_delta(total, theta, c) for c in covs))
    out["all"] = {
        "label": "All three",
        "ablation": "no-mc-all",
        "decks": int(hit.sum()),
        "size": size,
        "points": total(theta),
        "se": se,
        "keep_or_drop": keep_or_drop(size, total(theta), se, Z) if hit.any() else "no decks",
    }
    out["share_kept"] = float(share)
    out["quality_logit"] = float(beta[q])
    return out


def by_hand(md):
    """{bin: (pp, se)}: win rate of keeps by lands in hand against 3, within decks."""
    h = md.g_h
    bins = {"0-1": h <= 1, "2": h == 2, "4": h == 4, "5": h == 5, "6-7": h >= 6}
    cols = [b.astype(float) for b in bins.values()] + [md.g_play]
    beta, by_deck, by_set = within(md, cols)
    return {
        b: (100 * beta[i], 100 * math.sqrt(max(by_deck[i, i], by_set[i, i])),
            int((bins[b] & md.kept).sum()))
        for i, b in enumerate(bins)
    }


def hand_shares(md):
    """Kept 7s' land counts: share observed, if random, if kept as the simulator keeps."""
    k = md.kept
    L = md.lands[md.g_deck[k]].astype(int)
    obs = np.bincount(md.g_h[k].astype(int), minlength=8)[:8] / k.sum()
    rand = np.zeros(8)
    simk = np.zeros(8)
    for lands, n in zip(*np.unique(L, return_counts=True)):
        pmf = np.array([comb(lands, x) * comb(40 - lands, 7 - x) / comb(40, 7)
                        for x in range(8)])
        rand += n * pmf
        keep = pmf.copy()
        keep[[0, 1, 6, 7]] = 0
        simk += n * keep / keep.sum()
    return obs, rand / k.sum(), simk / k.sum()


def rate_table(md, mask):
    """Real and simulated rates (percent) for the decks in mask, weighted by games."""
    games = np.bincount(md.g_deck, minlength=len(md.row)).astype(float)
    kept_n = np.bincount(md.g_deck[md.kept], minlength=len(md.row)).astype(float)
    w, wk = games * mask, kept_n * mask
    out = {"mulligans": (100 * (md.g_mull[mask[md.g_deck]] > 0).mean(),
                         float(md.sim["mulligans"] @ w / w.sum()), None)}
    for k in RATES:
        real, n = kept_means(md, k)
        out[k] = (float(real @ wk / wk.sum()), float(md.kept7[k] @ wk / wk.sum()),
                  float(md.sim[k] @ w / w.sum()))
    return out


def stage_b(md):
    """Deck-level fit on the three rates past their thresholds, in score points."""
    d = md.base
    beta, model, cluster, index = deck_fit(md, hinges=True)
    q, scale = index[QUALITY], d.weights[QUALITY]
    out = {}
    for k, label, _, threshold, weight in PENALTIES:
        if k not in index:
            out[k] = {"points": None, "se": None, "keep_or_drop": "no decks past it"}
            continue
        i = index[k]
        g = np.zeros(len(beta))
        g[i], g[q] = scale / beta[q], -scale * beta[i] / beta[q] ** 2
        se = math.sqrt(max(g @ model @ g, g @ cluster @ g if cluster is not None else 0))
        points = scale * beta[i] / beta[q]
        out[k] = {"points": float(points), "se": se,
                  "keep_or_drop": keep_or_drop(-weight, float(points), se, Z)}
    return out


def _iv(v, se, digits=2):
    return f"{v:+.{digits}f} [{v - Z * se:+.{digits}f}, {v + Z * se:+.{digits}f}]"


def report(md, out=sys.stdout):
    def w(line=""):
        print(line, file=out)

    games = len(md.g_won)
    w(f"{len(md.row)} decks and {games} games from {len(md.sets)} sets; "
      f"{md.kept.sum()} games ({100 * md.kept.mean():.1f}%) are 7-card keeps "
      f"with the hand in the deck. Intervals are {100 * (1 - 2 * (1 - _phi(Z))):.2f}%.")
    w()
    for s, rate in md.left_out.items():
        w(f"Left out: {s}, whose dump records mulligans in {rate:.2f}% of games "
          f"(under {MIN_MULLIGANS:g}%), so its mulligans pass as 7-card keeps.")
        w()
    res = primary(md)
    w("## Primary results")
    w()
    w("Value: what a point of `simulate_deck()`'s rate costs, in deck score points, "
      "from the event's cost within decks and how far the rate moves the real "
      "chance in kept hands. The penalty: its points per point of rate past "
      "its threshold.")
    w()
    w("| penalty | ablation | cost of the event (win rate points) | real chance per simulated point | value (score points per point) | penalty | decks past it | keep or drop |")
    w("|---|---|---|---|---|---|---|---|")
    for k, *_ in PENALTIES:
        r = res[k]
        w(f"| {r['label']} | `{r['ablation']}` | {_iv(r['cost_pp'], r['cost_se'], 1)} "
          f"| {_iv(r['calibration'], r['calibration_se'])} | {_iv(r['points'], r['se'])} "
          f"| {-r['weight']:.1f} past {r['threshold']:.0f}% | {r['decks_past_threshold']} "
          f"| {r['keep_or_drop']} |")
    a = res["all"]
    w(f"| {a['label']} | `{a['ablation']}` | | | {_iv(a['points'], a['se'])} "
      f"| {a['size']:.2f} on average | {a['decks']} | {a['keep_or_drop']} |")
    w()
    w(f"Card quality: {res['quality_logit']:.3f} log-odds per unit "
      f"({md.base.weights[QUALITY]:g} score points).")
    w()

    w("## Calibration")
    w()
    w("Lands in a 7-card keep: share of keeps, against random 7s from the same "
      "decks and random 7s the simulator would keep (2 to 5 lands).")
    w()
    obs, rand, simk = hand_shares(md)
    w("| lands | kept | random | simulator's keeps |")
    w("|---|---|---|---|")
    for x in range(8):
        w(f"| {x} | {100 * obs[x]:.1f}% | {100 * rand[x]:.1f}% | {100 * simk[x]:.1f}% |")
    w()
    w("Rates in percent: real (mulligans in games; events as the mean chance "
      "in kept hands), the simulator's in its own 7-card keeps, and "
      "`simulate_deck()`'s, which the penalties read.")
    w()
    everything = np.ones(len(md.row), dtype=bool)
    rates = {"all sets": rate_table(md, everything)}
    for s in md.sets:
        rates[s] = rate_table(md, md.set == s)
    w("| sets | mulligans: real / sim | screw: real / sim keeps / sim | flood: real / sim keeps / sim | color screw: real / sim keeps / sim |")
    w("|---|---|---|---|---|")
    for s, t in rates.items():
        m = t["mulligans"]
        cells = [f"{m[0]:.1f} / {m[1]:.1f}"] + [
            f"{t[k][0]:.1f} / {t[k][1]:.1f} / {t[k][2]:.1f}"
            for k in ("screw_t3", "flood_t5", "color_screw_t3")
        ]
        w(f"| {s} | " + " | ".join(cells) + " |")
    w()

    w("## Win rate by lands in hand")
    w()
    w("Within decks, against keeps with 3 lands, in win rate points.")
    w()
    w("| lands in a 7-card keep | keeps | win rate against 3 |")
    w("|---|---|---|")
    hands = by_hand(md)
    for b in HAND_BINS:
        if b == "3":
            w(f"| 3 | {int((md.g_h == 3).sum())} | (reference) |")
        else:
            pp, se, n = hands[b]
            w(f"| {b} | {n} | {_iv(pp, se, 1) if n else ''} |")
    w()

    w("## By set")
    w()
    w("Cost of each event within decks, in win rate points.")
    w()
    w("| set | keeps | screw | flood | color screw |")
    w("|---|---|---|---|---|")
    per_set = {}
    for s in md.sets:
        mask = md.set[md.g_deck] == s
        c, cd, cs = event_costs(md, mask)
        se = 100 * np.sqrt(np.maximum(np.diag(cd), np.diag(cs)))
        per_set[s] = {k: (100 * c[i], se[i]) for i, k in enumerate(RATES)}
        cells = [f"{100 * c[RATES.index(k)]:+.1f} ± {se[RATES.index(k)]:.1f}"
                 for k in ("screw_t3", "flood_t5", "color_screw_t3")]
        w(f"| {s} | {int((md.kept & mask).sum())} | " + " | ".join(cells) + " |")
    w()

    w("## Deck-level fit")
    w()
    w("Not used for the verdict. Games won on each rate past its threshold, with "
      "fit.py's controls, in score points per point of rate.")
    w()
    w("| penalty | value | penalty | keep or drop |")
    w("|---|---|---|---|")
    b = stage_b(md)
    for k, label, _, threshold, weight in PENALTIES:
        value = "" if b[k]["points"] is None else _iv(b[k]["points"], b[k]["se"])
        w(f"| {label} | {value} | {-weight:.1f} | {b[k]['keep_or_drop']} |")
    res["calibration_rates"] = rates
    res["by_hand"] = hands
    res["per_set"] = per_set
    res["deck_level"] = b
    return res


def _phi(z):
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--features", nargs="+", required=True, help="From features.py")
    parser.add_argument("--hands", nargs="+", required=True, help="From hands.py")
    parser.add_argument("--json", help="Also write the results here")
    args = parser.parse_args(argv)
    load = lambda p: json.load(open(p, encoding="utf-8"))
    md = ManaData([load(p) for p in args.features], [load(p) for p in args.hands])
    results = report(md)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=1, default=float)


if __name__ == "__main__":
    main()

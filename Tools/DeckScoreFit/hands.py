"""Each sampled deck's simulated mana rates, and each kept hand's chance of them.

    python Tools/DeckScoreFit/hands.py --src . --decks decks.json.gz \
        --games games.json.gz --dataset FRA_PremierDraft_All_Data.json.gz \
        --set FRA --out FRA.json

For each deck from decks.py, simulate_deck() in the copy of the app at --src
gives the rates the deck builder penalizes. For each 7-card keep from
games.py, the rest of the library is in random order, so the hand fixes each
event's chance: by turn 3 (9 cards seen) fewer than 3 lands is screw; by
turn 5 (11 cards) 6 or more is flood; 3+ lands and a 3-drop by turn 3 with
no 3-drop castable is color screw. Screw and flood are exact; color screw
runs SHUFFLES shufflings of the library through the simulator's castability
code. The simulator's rate for its own 7-card keeps (it keeps 2 to 5 lands)
comes from the same code, for calibration. See README.md.
"""

import argparse
import gzip
import json
import os
import sys
from collections import Counter
from math import comb

import numpy as np

from features import App

SHUFFLES = 1000
KEPT7_SHUFFLES = 10000
DECK_SIZE = 40
HAND = 7


def hypergeom_cdf(k, N, K, n):
    """P(X <= k) for X lands among n cards drawn from N holding K lands."""
    return sum(comb(K, x) * comb(N - K, n - x) for x in range(0, min(k, n) + 1)) / comb(N, n)


def screw_chance(hand_lands, deck_lands):
    """Fewer than 3 lands in the first 9 cards, given the 7 in hand."""
    need = 3 - hand_lands
    if need <= 0:
        return 0.0
    return hypergeom_cdf(need - 1, DECK_SIZE - HAND, deck_lands - hand_lands, 2)


def flood_chance(hand_lands, deck_lands):
    """6 or more lands in the first 11 cards, given the 7 in hand."""
    need = 6 - hand_lands
    if need <= 0:
        return 1.0
    return 1.0 - hypergeom_cdf(need - 1, DECK_SIZE - HAND, deck_lands - hand_lands, 4)


def make_kernels(sim):
    """The two Monte Carlo kernels, built on the simulator's castability code."""
    from numba import njit

    castable = sim._castable_on_turn
    max_sources = sim.MAX_SOURCES

    @njit(cache=False)
    def color_screw_chance(hand, library, shuffles, seed, is_land, is_ramp,
                           is_filter, costs, mana_produced, pips, pip_count, generic):
        np.random.seed(seed)
        src_masks = np.zeros(max_sources, dtype=np.int32)
        land_masks = np.zeros(max_sources, dtype=np.int32)
        cover = np.zeros(32, dtype=np.int32)
        order = np.empty(len(hand) + len(library), dtype=np.int64)
        order[: len(hand)] = hand
        lib = library.copy()
        hits = 0
        for _ in range(shuffles):
            np.random.shuffle(lib)
            order[len(hand):] = lib
            lands = 0
            for j in range(9):
                lands += is_land[order[j]]
            if lands < 3:
                continue
            has, ok = castable(order, 0, 9, 3, is_land, is_ramp, is_filter, costs,
                               mana_produced, pips, pip_count, generic, src_masks,
                               land_masks, cover)
            if has and not ok:
                hits += 1
        return hits / shuffles

    @njit(cache=False)
    def kept7_rates(shuffles, seed, is_land, is_ramp, is_filter, costs,
                    mana_produced, pips, pip_count, generic):
        np.random.seed(seed)
        src_masks = np.zeros(max_sources, dtype=np.int32)
        land_masks = np.zeros(max_sources, dtype=np.int32)
        cover = np.zeros(32, dtype=np.int32)
        order = np.arange(len(is_land))
        kept = screw = flood = color = 0
        for _ in range(shuffles):
            np.random.shuffle(order)
            h = 0
            for j in range(7):
                h += is_land[order[j]]
            if h < 2 or h > 5:
                continue
            kept += 1
            t3 = h
            for j in range(7, 9):
                t3 += is_land[order[j]]
            t5 = t3
            for j in range(9, 11):
                t5 += is_land[order[j]]
            if t3 < 3:
                screw += 1
            if t5 >= 6:
                flood += 1
            if t3 >= 3:
                has, ok = castable(order, 0, 9, 3, is_land, is_ramp, is_filter, costs,
                                   mana_produced, pips, pip_count, generic, src_masks,
                                   land_masks, cover)
                if has and not ok:
                    color += 1
        return kept, screw, flood, color

    return color_screw_chance, kept7_rates


def _sim_args(a):
    return (a.is_land, a.is_ramp, a.is_filter, a.costs, a.mana_produced, a.pips,
            a.pip_count, a.generic)


def positions(cards):
    """{name: [indices]} in the order the simulator lays out the deck."""
    out, i = {}, 0
    for name, count in cards.items():
        out[name] = list(range(i, i + count))
        i += count
    return out


def hand_indices(hand, where):
    """The deck indices of the hand's cards, or None if they don't fit the deck."""
    idx = []
    for name, count in hand.items():
        spots = where.get(name)
        if spots is None or count > len(spots):
            return None
        idx += spots[:count]
    return idx if len(idx) == HAND else None


def deck_hands(app, sim, kernels, decks, hands, shuffles=SHUFFLES,
               kept7_shuffles=KEPT7_SHUFFLES):
    """A row per deck with its rates and its games, and why any were skipped."""
    color_screw_chance, kept7_rates = kernels
    by_deck = {}
    for key, on_play, mulligans, won, hand in hands:
        by_deck.setdefault(key, []).append((on_play, mulligans, won, hand))
    rows, skipped = [], Counter()
    seed = 0
    for d in decks:
        if sum(d["cards"].values()) != DECK_SIZE:
            skipped["not 40 cards"] += 1
            continue
        deck = app.deck(d["cards"])
        if deck is None or len(deck) != len(d["cards"]):
            skipped["card not in dataset"] += 1
            continue
        arrays = sim._parse_deck_to_arrays(deck)
        stats = sim.simulate_deck(deck)
        if arrays is None or stats is None:
            skipped["not simulated"] += 1
            continue
        args = _sim_args(arrays)
        lands = int(arrays.is_land.sum())
        kept, screw, flood, color = kept7_rates(kept7_shuffles, len(rows), *args)
        where = positions(d["cards"])
        games = []
        for on_play, mulligans, won, hand in by_deck.get(d["id"], []):
            row = [int(on_play), mulligans, int(won), None, None, None, None]
            idx = hand_indices(hand, where) if mulligans == 0 else None
            if mulligans == 0 and idx is None:
                skipped["hand not in deck"] += 1
            if idx is not None:
                h = int(arrays.is_land[idx].sum())
                library = np.array(sorted(set(range(DECK_SIZE)) - set(idx)))
                seed += 1
                p_color = color_screw_chance(np.array(idx), library, shuffles, seed,
                                             *args)
                row[3:] = [h, screw_chance(h, lands), flood_chance(h, lands), p_color]
            games.append(row)
        if not games:
            skipped["no games"] += 1
            continue
        rows.append({
            "id": d["id"],
            "lands": lands,
            "sim": {k: stats[k] for k in
                    ("screw_t3", "flood_t5", "color_screw_t3", "mulligans")},
            "kept7": {
                "keep": 100.0 * kept / kept7_shuffles,
                "screw_t3": 100.0 * screw / max(1, kept),
                "flood_t5": 100.0 * flood / max(1, kept),
                "color_screw_t3": 100.0 * color / max(1, kept),
            },
            "games": games,
        })
    return rows, skipped


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--src", required=True, help="The copy of the app to use")
    parser.add_argument("--decks", required=True, help="From decks.py (.json.gz)")
    parser.add_argument("--games", required=True, help="From games.py (.json.gz)")
    parser.add_argument("--dataset", required=True, help="The app's set data")
    parser.add_argument("--set", required=True, help="Set code, for the report")
    parser.add_argument("--out", required=True, help="Where to write them (.json)")
    parser.add_argument("--shuffles", type=int, default=SHUFFLES)
    args = parser.parse_args(argv)

    sys.path.insert(0, os.path.abspath(args.src))
    from src.advisor import simulator as sim

    app = App(args.dataset)
    with gzip.open(args.decks, "rt", encoding="utf-8") as f:
        decks = json.load(f)
    with gzip.open(args.games, "rt", encoding="utf-8") as f:
        hands = json.load(f)["hands"]
    rows, skipped = deck_hands(app, sim, make_kernels(sim), decks, hands,
                               args.shuffles)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"set": args.set, "skipped": dict(skipped), "decks": rows}, f)
    print(f"{args.set}: {len(rows)} decks, skipped {dict(skipped)}")


if __name__ == "__main__":
    main()

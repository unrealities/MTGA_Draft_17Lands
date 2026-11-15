"""How well the advisor's lane predicts the colors a drafter ends up playing.

    python Tools/AdvisorReplay/lanes.py --src . \
        --drafts drafts.json.gz --games game_data_public.FRA.PremierDraft.csv.gz \
        --dataset FRA_PremierDraft_All_Data.json.gz --set FRA --out FRA.lanes.json

At every pick, each version of the lane rule (ARMS) names the pool's main
colors, and the harness records them next to the main colors of the deck the
drafter played most. See experiments/2026-11-15-lane-accuracy/PROTOCOL.md.
"""

import argparse
import csv
import gzip
import json
import os
import sys
from collections import Counter

from replay import App

COLORS = "WUBRG"

# name -> how the lane is chosen. "app" must match DraftAdvisor exactly; the
# run stops if it doesn't.
ARMS = {
    "app": {},
    "no-recency": {"recency": False},
    "no-switch": {"switch": False},
    "neither": {"recency": False, "switch": False},
    "column-order": {"column_order": True},
    "most-cards": {"most_cards": True},
}


def lane(pool, mean, std, recency=True, switch=True):
    """DraftAdvisor._identify_main_colors, with two of its parts optional.

    recency: later picks count for up to three times the first one.
    switch: from 15 cards on, colors qualify by their share of the pool's
    cards instead of by their weight.
    """
    weights = {c: 0.0 for c in COLORS}
    counts = {c: 0 for c in COLORS}
    for idx, card in enumerate(pool):
        try:
            colors = card.get("colors", [])
            wr = float(card.get("deck_colors", {}).get("All Decks", {}).get("gihwr", 0.0))
            if "Land" not in card.get("types", []):
                for color in colors:
                    counts[color] += 1
            if wr < mean - std:
                continue
            points = max(0.2, 1.0 + 2.0 * ((wr - mean) / std))
            if recency:
                points *= 1.0 + 2.0 * (idx / max(1, len(pool)))
            for color in colors:
                if color in weights:
                    weights[color] += points
        except Exception:  # as the app does
            continue
    by_weight = sorted(weights.items(), key=lambda x: x[1], reverse=True)
    total = sum(counts.values())
    if switch and len(pool) >= 15 and total > 5:
        leaders = [
            c
            for c, n in sorted(counts.items(), key=lambda x: x[1], reverse=True)[:2]
            if n > 0
        ]
        main = [c for c, _ in by_weight if c in leaders or counts[c] >= total * 0.15]
    else:
        main = [c for c, w in by_weight if w >= 2.5]
    return main[:3]


def most_cards(pool):
    """A yardstick: the two colors with the most nonland cards."""
    counts = Counter(
        color
        for card in pool
        if "Land" not in card.get("types", [])
        for color in card.get("colors", [])
    )
    return [c for c, _ in counts.most_common(2)]


def played_colors(lines, draft_ids):
    """{draft_id: main colors of the build with the most games (the later on ties)}."""
    lines = iter(lines)
    header = next(csv.reader([next(lines)]))
    col = {name: i for i, name in enumerate(header)}
    i_id, i_build, i_colors = col["draft_id"], col["build_index"], col["main_colors"]
    games = {}  # (draft_id, build) -> [games, colors]
    for line in lines:
        fields = (
            next(csv.reader([line])) if '"' in line else line.rstrip("\r\n").split(",")
        )
        if fields[i_id] in draft_ids:
            key = (fields[i_id], int(float(fields[i_build] or 0)))
            games.setdefault(key, [0, fields[i_colors]])[0] += 1
    best = {}
    for (draft_id, build), (n, colors) in games.items():
        if (n, build) > best.get(draft_id, ((-1, -1), ""))[0]:
            best[draft_id] = ((n, build), colors)
    return {d: "".join(c for c in COLORS if c in colors) for d, (_, colors) in best.items()}


def lanes_of_draft(app, draft, skipped):
    """[pack, pick, cards in the pool, [each arm's lane]] for every pick with a pool."""
    DraftAdvisor = app.DraftAdvisor
    rows, taken_so_far = [], []
    for pack_no, pick_no, taken, _, pool_names in draft["picks"]:
        in_order, taken_so_far = list(taken_so_far), taken_so_far + [taken]
        if not pool_names:
            continue
        # The dump lists the pool by card, not by pick; the app holds it in
        # pick order, which recency needs.
        if Counter(in_order) != Counter(pool_names):
            skipped["pool doesn't match the earlier picks"] += 1
            continue
        pool, by_column = app.cards(in_order), app.cards(pool_names)
        advisor = DraftAdvisor(app.metrics, pool)
        mean, std = advisor.global_mean, advisor.global_std
        lanes = []
        for name, arm in ARMS.items():
            if arm.get("most_cards"):
                found = most_cards(pool)
            elif arm.get("column_order"):
                found = lane(by_column, mean, std)
            else:
                found = lane(pool, mean, std, **arm)
            lanes.append("".join(found))
        if lanes[0] != "".join(advisor.main_colors):
            raise SystemExit(
                f"lane() is out of step with the app: {lanes[0]!r} against "
                f"{''.join(advisor.main_colors)!r} in draft {draft['id']}"
            )
        rows.append([pack_no, pick_no, len(pool), lanes])
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--src", default=".", help="Folder holding the app's src/")
    parser.add_argument("--drafts", required=True, help="Drafts from sample.py")
    parser.add_argument("--games", required=True, help="17Lands game data (.csv.gz)")
    parser.add_argument("--dataset", required=True, help="The app's dataset for the set")
    parser.add_argument("--set", default="", help="Set code, for the report")
    parser.add_argument("--out", required=True, help="Where to write the results (.json)")
    args = parser.parse_args(argv)

    sys.path.insert(0, os.path.abspath(args.src))
    app = App(args.dataset)
    with gzip.open(args.drafts, "rt", encoding="utf-8") as f:
        drafts = json.load(f)
    opener = gzip.open if args.games.endswith(".gz") else open
    with opener(args.games, "rt", newline="", encoding="utf-8") as f:
        played = played_colors(f, {d["id"] for d in drafts})

    skipped, results = Counter(), []
    for draft in drafts:
        if not played.get(draft["id"]):
            skipped["draft has no games"] += 1
            continue
        results.append(
            {
                "id": draft["id"],
                "skill": draft["skill"],
                "played": played[draft["id"]],
                "picks": lanes_of_draft(app, draft, skipped),
            }
        )
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(
            {
                "set": args.set,
                "arms": list(ARMS),
                "skipped": dict(skipped),
                "drafts": results,
            },
            f,
        )
    print(f"Lanes for {len(results)} of {len(drafts)} drafts ({args.set})")


if __name__ == "__main__":
    main()

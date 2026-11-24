"""Rebuild the app's dataset from a game dump, with and without the sampled drafts.

    python Tools/AdvisorReplay/holdout.py --games game_data_public.FRA.PremierDraft.csv.gz \
        --drafts drafts.json.gz --dataset FRA_PremierDraft_All_Data.json.gz \
        --rebuilt rebuilt.json.gz --heldout heldout.json.gz

The two datasets differ only in their win rates: --rebuilt counts every game in
the dump, and --heldout leaves out the games of the drafts in --drafts. A rate
exists where the card has MIN_SAMPLES games in hand in the whole dump, as 17Lands
hides thinner ones from the app, and samples is that whole-dump count, which
reads no results. So both datasets have the same cards rated and the same
shrinkage. Cards the app has no data for, such as basic lands, stay unrated. GIH WR, GNS WR and IWD are replaced; the other fields stay the app's,
which the advisor doesn't read for scoring, except ALSA, which reads no results.
--also names more drafts whose games --heldout leaves out too, without replaying
them: with the replayed drafts fixed, a new --also varies only the ratings.
Standard library only.
"""

import argparse
import copy
import gzip
import json
import os
import sys

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "DeckScoreFit")
)

from games import ALL, read_games  # noqa: E402

MIN_SAMPLES = 500
GROUP_ZERO = [0, 0, 0, 0]


def read_counts(lines, held):
    """(held, rest): read_games' {colors: {card: counts}} for games of drafts in
    held and for all the others."""
    _, folds = read_games(
        lines, set(), fold_of=lambda key: 0 if key.rsplit(":", 1)[0] in held else 1
    )
    return folds[0], folds[1]


def merged(a, b):
    """The sum of two {colors: {card: counts}}."""
    out = {}
    for counts in (a, b):
        for colors, cards in counts.items():
            group = out.setdefault(colors, {})
            for name, c in cards.items():
                group[name] = [x + y for x, y in zip(group.get(name, GROUP_ZERO), c)]
    return out


def rebuilt(data, counts, whole):
    """A copy of the dataset with win rates from counts, rated as whole says.

    The dump names double-faced cards by their front face only.
    """
    out = copy.deepcopy(data)
    for card in out["card_ratings"].values():
        if not card.get("deck_colors", {}).get(ALL, {}).get("samples"):
            continue
        name = card.get("name", "").split(" // ")[0]
        for colors, stats in card.get("deck_colors", {}).items():
            samples = whole.get(colors, {}).get(name, GROUP_ZERO)[0]
            seen, won, unseen, unseen_won = counts.get(colors, {}).get(name, GROUP_ZERO)
            rated = samples >= MIN_SAMPLES and seen
            gihwr = round(100.0 * won / seen, 2) if rated else 0.0
            gnswr = round(100.0 * unseen_won / unseen, 2) if rated and unseen else 0.0
            stats.update(
                gihwr=gihwr,
                gnswr=gnswr,
                iwd=round(gihwr - gnswr, 2) if gnswr else 0.0,
                samples=samples,
            )
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--games", required=True, help="17Lands game data (.csv.gz)")
    parser.add_argument("--drafts", required=True, help="From sample.py (.json.gz)")
    parser.add_argument("--dataset", required=True, help="The app's dataset (.json.gz)")
    parser.add_argument("--rebuilt", required=True, help="Every game (.json.gz)")
    parser.add_argument("--heldout", required=True, help="Without --drafts (.json.gz)")
    parser.add_argument("--also", help="More drafts to leave out of --heldout (.json.gz)")
    args = parser.parse_args(argv)

    with gzip.open(args.drafts, "rt", encoding="utf-8") as f:
        held_ids = {d["id"] for d in json.load(f)}
    if args.also:
        with gzip.open(args.also, "rt", encoding="utf-8") as f:
            held_ids |= {d["id"] for d in json.load(f)}
    with gzip.open(args.dataset, "rt", encoding="utf-8") as f:
        data = json.load(f)
    with gzip.open(args.games, "rt", encoding="utf-8", newline="") as f:
        held, rest = read_counts(f, held_ids)
    if not held:
        raise SystemExit("None of the sampled drafts are in the game data")

    whole = merged(held, rest)
    for path, counts in ((args.rebuilt, whole), (args.heldout, rest)):
        with gzip.open(path, "wt", encoding="utf-8") as f:
            json.dump(rebuilt(data, counts, whole), f)
    share = sum(c[0] for c in held[ALL].values()) / sum(
        c[0] for c in whole[ALL].values()
    )
    print(f"Sampled drafts hold {100 * share:.1f}% of the dump's games in hand")


if __name__ == "__main__":
    main()

"""Read a 17Lands game dump again: the sampled decks' hands, other games' win rates.

    python Tools/DeckScoreFit/games.py --games game_data_public.FRA.PremierDraft.csv.gz \
        --decks decks.json.gz --out games.json.gz

For each game of a deck from decks.py, it keeps whether the player was on the
play, their mulligans, the result and the opening hand. Every deck in the dump
falls in one of FOLDS folds by its draft's ID, so all builds of one pool are
in the same fold. For each fold it counts, for each card and for the deck's
main colors and all decks, the games it was in hand (opening hand or drawn)
and won, and the games it was in the deck but not drawn and won. A deck can
then be rated from the other folds' counts, so no deck's results, nor those
of its pool's other builds, are in its own ratings, and every set's ratings
come from most of its dump. Standard library only.
"""

import argparse
import csv
import gzip
import json

from decks import deck_hash

ALL = "All Decks"
FOLDS = 5


def fold_of(key):
    """The fold a deck's games are counted in: its draft's.

    key is the deck's ID, draft_id:build_index. Rebuilds of a pool share the
    player, the cards and the event, so they must not be split across folds.
    """
    draft = key.rsplit(":", 1)[0]
    return deck_hash(draft, "ratings") % FOLDS


def _count(text):
    # Some dumps (DMU, EOE, LTR, PIO) write counts as "1.0".
    return int(float(text)) if text else 0


def read_games(lines, ids, fold_of=fold_of):
    """(hands, folds) from the dump's lines, header first.

    hands: [deck id, on play, mulligans, won, {card: count in opening hand}]
    for each game of a deck in ids. folds: for each fold, {colors: {card:
    [games in hand, won, games not drawn, won]}} over its decks' games. fold_of
    says which of FOLDS folds a deck's ID falls in.
    """
    lines = iter(lines)
    header = next(csv.reader([next(lines)]))
    col = {name: i for i, name in enumerate(header)}
    cards = [
        (name[len("deck_") :], i, col.get(f"opening_hand_{name[5:]}"),
         col.get(f"drawn_{name[5:]}"))
        for i, name in enumerate(header)
        if name.startswith("deck_")
    ]
    hand_cols = [(c, oh) for c, _, oh, _ in cards if oh is not None]
    folds = [{} for _ in range(FOLDS)]
    fold = {}
    hands = []
    for line in lines:
        if '"' in line:
            fields = next(csv.reader([line]))
        else:
            fields = line.rstrip("\r\n").split(",")
        key = f"{fields[col['draft_id']]}:{fields[col['build_index']]}"
        won = fields[col["won"]] == "True"
        sampled = key in ids
        f = fold.get(key)
        if f is None:
            f = fold[key] = fold_of(key)
        ratings = folds[f]
        groups = [ratings.setdefault(ALL, {})]
        colors = fields[col["main_colors"]]
        if colors:
            groups.append(ratings.setdefault(colors, {}))
        for name, d, oh, dr in cards:
            if not _count(fields[d]):
                continue
            seen = (oh is not None and _count(fields[oh])) or (
                dr is not None and _count(fields[dr])
            )
            for group in groups:
                s = group.get(name)
                if s is None:
                    s = group[name] = [0, 0, 0, 0]
                if seen:
                    s[0] += 1
                    s[1] += won
                else:
                    s[2] += 1
                    s[3] += won
        if sampled:
            hands.append([
                key,
                fields[col["on_play"]] == "True",
                _count(fields[col["num_mulligans"]]),
                won,
                {c: n for c, oh in hand_cols if (n := _count(fields[oh]))},
            ])
    return hands, folds


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--games", required=True, help="17Lands game data (.csv.gz)")
    parser.add_argument("--decks", required=True, help="From decks.py (.json.gz)")
    parser.add_argument("--out", required=True, help="Where to write them (.json.gz)")
    args = parser.parse_args(argv)

    with gzip.open(args.decks, "rt", encoding="utf-8") as f:
        ids = {d["id"] for d in json.load(f)}
    with gzip.open(args.games, "rt", encoding="utf-8", newline="") as f:
        hands, folds = read_games(f, ids)
    with gzip.open(args.out, "wt", encoding="utf-8") as f:
        json.dump({"hands": hands, "folds": folds}, f)
    sizes = [sum(s[0] + s[2] for s in r.get(ALL, {}).values()) for r in folds]
    print(f"Kept {len(hands)} games of sampled decks; card-games by fold: {sizes}")


if __name__ == "__main__":
    main()

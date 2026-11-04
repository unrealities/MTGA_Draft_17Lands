"""Read a 17Lands game dump again: the sampled decks' hands, other games' win rates.

    python Tools/DeckScoreFit/games.py --games game_data_public.FRA.PremierDraft.csv.gz \
        --decks decks.json.gz --out games.json.gz

For each game of a deck from decks.py, it keeps whether the player was on the
play, their mulligans, the result and the opening hand. From every other game
it counts, for each card and for the deck's main colors and all decks, the
games it was in hand (opening hand or drawn) and won, and the games it was in
the deck but not drawn and won: the card win rates the sampled decks didn't
make. Games in hand are counted over every game too, for shrinkage, which
needs no results. Standard library only.
"""

import argparse
import csv
import gzip
import json

ALL = "All Decks"


def _count(text):
    # Some dumps (DMU, EOE, LTR, PIO) write counts as "1.0".
    return int(float(text)) if text and text not in ("0", "0.0") else 0


def read_games(lines, ids):
    """(hands, ratings) from the dump's lines, header first.

    hands: [deck id, on play, mulligans, won, {card: count in opening hand}]
    for each game of a deck in ids. ratings: {colors: {card: [games in hand,
    won, games in hand in every game, games not drawn, won]}}, counting the
    games of decks not in ids, except the third.
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
    ratings = {}
    hands = []
    for line in lines:
        if '"' in line:
            fields = next(csv.reader([line]))
        else:
            fields = line.rstrip("\r\n").split(",")
        key = f"{fields[col['draft_id']]}:{fields[col['build_index']]}"
        won = fields[col["won"]] == "True"
        sampled = key in ids
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
                    s = group[name] = [0, 0, 0, 0, 0]
                if seen:
                    s[2] += 1
                if sampled:
                    continue
                if seen:
                    s[0] += 1
                    s[1] += won
                else:
                    s[3] += 1
                    s[4] += won
        if sampled:
            hands.append([
                key,
                fields[col["on_play"]] == "True",
                _count(fields[col["num_mulligans"]]),
                won,
                {c: n for c, oh in hand_cols if (n := _count(fields[oh]))},
            ])
    return hands, ratings


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--games", required=True, help="17Lands game data (.csv.gz)")
    parser.add_argument("--decks", required=True, help="From decks.py (.json.gz)")
    parser.add_argument("--out", required=True, help="Where to write them (.json.gz)")
    args = parser.parse_args(argv)

    with gzip.open(args.decks, "rt", encoding="utf-8") as f:
        ids = {d["id"] for d in json.load(f)}
    with gzip.open(args.games, "rt", encoding="utf-8", newline="") as f:
        hands, ratings = read_games(f, ids)
    with gzip.open(args.out, "wt", encoding="utf-8") as f:
        json.dump({"hands": hands, "ratings": ratings}, f)
    others = sum(s[0] + s[3] for s in ratings.get(ALL, {}).values())
    print(f"Kept {len(hands)} games of sampled decks; {others} card-games from the rest")


if __name__ == "__main__":
    main()

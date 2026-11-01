"""Sample decks from a 17Lands game data dump, with their game results.

    python Tools/DeckScoreFit/decks.py \
        --games game_data_public.FRA.PremierDraft.csv.gz --decks 20000 \
        --out decks.json.gz

A deck is one build of one draft (draft_id and build_index); each row of the
dump is one game played with it. The sample keeps the decks whose IDs hash
lowest, so it is repeatable, and a different --salt picks different decks.
Standard library only.
"""

import argparse
import csv
import gzip
import hashlib
import heapq
import json


def deck_hash(key, salt):
    return int(hashlib.sha1(f"{salt}{key}".encode()).hexdigest()[:15], 16)


def read_decks(lines, n, salt=""):
    """The n sampled decks from the dump's lines (header first), by ID."""
    lines = iter(lines)
    header = next(csv.reader([next(lines)]))
    col = {name: i for i, name in enumerate(header)}
    deck_cols = [
        (i, name[len("deck_") :])
        for i, name in enumerate(header)
        if name.startswith("deck_")
    ]
    kept, heap = {}, []  # heap holds (-hash, id) of the kept decks
    for line in lines:
        if '"' in line:  # quoted fields: parse properly
            fields = next(csv.reader([line]))
        else:
            fields = line.rstrip("\r\n").split(",")
        key = f"{fields[col['draft_id']]}:{fields[col['build_index']]}"
        deck = kept.get(key)
        if deck is None:
            # A deck's hash never changes and the cutoff only falls, so a deck
            # that is dropped or skipped here would never have been kept.
            h = deck_hash(key, salt)
            if len(heap) < n:
                heapq.heappush(heap, (-h, key))
            elif h < -heap[0][0]:
                del kept[heapq.heapreplace(heap, (-h, key))[1]]
            else:
                continue
            deck = kept[key] = {
                "id": key,
                "main_colors": fields[col["main_colors"]],
                "splash_colors": fields[col["splash_colors"]],
                "skill": fields[col["user_game_win_rate_bucket"]],
                "experience": fields[col["user_n_games_bucket"]],
                "cards": {
                    name: int(fields[i])
                    for i, name in deck_cols
                    if fields[i] not in ("", "0")
                },
                "games": 0,
                "wins": 0,
            }
        deck["games"] += 1
        deck["wins"] += fields[col["won"]] == "True"
    return sorted(kept.values(), key=lambda d: d["id"])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--games", required=True, help="17Lands game data (.csv.gz)")
    parser.add_argument("--decks", type=int, default=20000, help="Decks to keep")
    parser.add_argument("--salt", default="", help="Changes which decks are kept")
    parser.add_argument("--out", required=True, help="Where to write them (.json.gz)")
    args = parser.parse_args(argv)

    with gzip.open(args.games, "rt", encoding="utf-8", newline="") as f:
        decks = read_decks(f, args.decks, args.salt)
    with gzip.open(args.out, "wt", encoding="utf-8") as f:
        json.dump(decks, f)
    games = sum(d["games"] for d in decks)
    print(f"Kept {len(decks)} decks with {games} games")


if __name__ == "__main__":
    main()

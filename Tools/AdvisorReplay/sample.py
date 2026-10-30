"""Sample drafts from a 17Lands public draft dump.

    python Tools/AdvisorReplay/sample.py \
        --dump draft_data_public.FRA.PremierDraft.csv.gz \
        --drafts 3000 --out drafts.json.gz

Drafts are chosen by a hash of their draft_id, so the same dump, size and salt
always give the same drafts, and a new --salt gives an independent sample.
"""

import argparse
import csv
import gzip
import hashlib
import heapq
import json


def draft_priority(draft_id, salt=""):
    """A draft's place in the sample order; the lowest values are kept."""
    return int(hashlib.md5((salt + draft_id).encode("utf-8")).hexdigest()[:15], 16)


def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _names(row, columns):
    """Card names from count columns: [(index, name)] -> name repeated count times."""
    return [
        name
        for i, name in columns
        if row[i] not in ("", "0")
        for _ in range(int(row[i]))
    ]


def sample_drafts(lines, n_drafts, salt=""):
    """The n_drafts drafts with the lowest priority, in draft_id order.

    lines is the dump's CSV text, one line per pick. Each draft has the
    drafter's "skill" (game win rate bucket) and "games" (games played bucket),
    the event's "wins" and "losses", and its "picks": [pack, pick, taken card,
    cards in the pack, cards already taken], with pack and pick from 1.
    """
    reader = csv.reader(lines)
    header = next(reader)
    col = {name: i for i, name in enumerate(header)}
    pack_cols = [
        (i, c[len("pack_card_") :])
        for i, c in enumerate(header)
        if c.startswith("pack_card_")
    ]
    pool_cols = [
        (i, c[len("pool_") :]) for i, c in enumerate(header) if c.startswith("pool_")
    ]

    # Max-heap of the kept drafts' priorities, as (-priority, draft_id).
    kept, drafts = [], {}
    current_id, keep = None, False
    for row in reader:
        draft_id = row[col["draft_id"]]
        if draft_id != current_id:
            current_id = draft_id
            priority = draft_priority(draft_id, salt)
            keep = draft_id in drafts or len(kept) < n_drafts or priority < -kept[0][0]
            if keep and draft_id not in drafts:
                if len(kept) == n_drafts:
                    drafts.pop(heapq.heappop(kept)[1])
                heapq.heappush(kept, (-priority, draft_id))
                drafts[draft_id] = {
                    "id": draft_id,
                    "skill": _number(row[col["user_game_win_rate_bucket"]]),
                    "games": _number(row[col["user_n_games_bucket"]]),
                    "wins": _number(row[col["event_match_wins"]]),
                    "losses": _number(row[col["event_match_losses"]]),
                    "picks": [],
                }
        if keep:
            drafts[draft_id]["picks"].append(
                [
                    int(row[col["pack_number"]]) + 1,
                    int(row[col["pick_number"]]) + 1,
                    row[col["pick"]],
                    _names(row, pack_cols),
                    _names(row, pool_cols),
                ]
            )
    return [drafts[d] for d in sorted(drafts)]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--dump", required=True, help="17Lands draft dump (.csv or .csv.gz)"
    )
    parser.add_argument(
        "--drafts", type=int, required=True, help="How many drafts to keep"
    )
    parser.add_argument("--salt", default="", help="Changes which drafts are kept")
    parser.add_argument(
        "--out", required=True, help="Where to write the drafts (.json.gz)"
    )
    args = parser.parse_args(argv)

    opener = gzip.open if args.dump.endswith(".gz") else open
    with opener(args.dump, "rt", newline="", encoding="utf-8") as f:
        drafts = sample_drafts(f, args.drafts, args.salt)
    with gzip.open(args.out, "wt", encoding="utf-8") as f:
        json.dump(drafts, f)
    print(f"Sampled {len(drafts)} drafts from {args.dump}")


if __name__ == "__main__":
    main()

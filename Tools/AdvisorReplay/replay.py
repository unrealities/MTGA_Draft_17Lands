"""Replay sampled drafts through one copy of the app's advisor.

    python Tools/AdvisorReplay/replay.py --src . \
        --drafts drafts.json.gz --dataset FRA_PremierDraft_All_Data.json.gz \
        --label head --out head.json

At every pick, the advisor sees the pack and the cards taken so far, as it
would in the app, and the harness records where it ranked the card the drafter
took. Each final pool also gets the app's deck score. --src picks which copy of
the app to import, so a pull request and its base can replay the same drafts.
"""

import argparse
import gzip
import itertools
import json
import os
import shutil
import statistics
import sys
import tempfile
import time
from collections import Counter

DECK_SIZE = 23


class App:
    """The advisor, deck builder and card data, from the src/ on sys.path."""

    def __init__(self, dataset_path):
        from src import card_logic, constants
        from src.advisor.engine import DraftAdvisor
        from src.dataset import Dataset
        from src.set_metrics import SetMetrics

        self.card_logic, self.constants, self.DraftAdvisor = (
            card_logic,
            constants,
            DraftAdvisor,
        )
        self.dataset = Dataset()
        with tempfile.TemporaryDirectory() as tmp:
            # Dataset.open_file reads plain JSON only.
            plain = os.path.join(tmp, "dataset.json")
            opener = gzip.open if dataset_path.endswith(".gz") else open
            with opener(dataset_path, "rb") as src, open(plain, "wb") as dst:
                shutil.copyfileobj(src, dst)
            self.dataset.open_file(plain)
        if not self.dataset.get_card_ratings():
            raise SystemExit(f"Could not load dataset {dataset_path}")
        self.metrics = SetMetrics(self.dataset)

        # The dump names double-faced cards by their front face only.
        self.full_names = {}
        for card in self.dataset.get_card_ratings().values():
            name = card.get(constants.DATA_FIELD_NAME, "")
            self.full_names.setdefault(name.split(" // ")[0], name)
        self.unmatched = Counter()

    def cards(self, names):
        """Card dicts for dump names; names missing from the dataset are dropped."""
        out = []
        for name in names:
            found = self.dataset.get_data_by_name([self.full_names.get(name, name)])
            if found:
                out.append(found[0])
            else:
                self.unmatched[name] += 1
        return out

    def gihwr(self, card):
        """The card's GIH WR over all decks (0 if unrated)."""
        c = self.constants
        stats = card.get(c.DATA_FIELD_DECK_COLORS, {}).get(
            c.FILTER_OPTION_ALL_DECKS, {}
        )
        return float(stats.get(c.DATA_FIELD_GIHWR) or 0.0)

    def advise(self, pack, pool, pack_no, pick_no):
        """{card name: advisor score}, best first."""
        recs = self.DraftAdvisor(self.metrics, pool).evaluate_pack(
            pack, pick_no, current_pack=pack_no
        )
        scores = {}
        for r in recs:
            scores.setdefault(r.card_name, r.contextual_score)
        return scores

    def deck_score(self, pool):
        """The best score among the app's quick deck builds for this pool."""
        cl = self.card_logic
        builds = []
        for pair in cl.identify_top_pairs(pool, self.metrics):
            builds.append(
                (cl.build_variant_consistency(pool, pair, self.metrics), pair)
            )
            builds.append((cl.build_variant_curve(pool, pair, self.metrics), pair))
            deck, splash = cl.build_variant_greedy(pool, pair, self.metrics)
            builds.append((deck, pair + [splash] if splash else pair))
        deck, colors = cl.build_variant_soup(pool, self.metrics)
        builds.append((deck, colors[:3] if colors else ["All Decks"]))
        return max(
            (
                cl.calculate_holistic_score(deck, colors, len(pool), self.metrics)[0]
                for deck, colors in builds
                if deck
            ),
            default=0.0,
        )

    def pool_gihwr(self, pool):
        """Mean GIH WR of the best 23 cards castable in one color pair (a yardstick)."""
        c = self.constants
        best = 0.0
        for pair in itertools.combinations(c.CARD_COLORS, 2):
            rates = sorted(
                (
                    self.gihwr(card)
                    for card in pool
                    if set(card.get(c.DATA_FIELD_COLORS, [])) <= set(pair)
                ),
                reverse=True,
            )
            best = max(best, sum(rates[:DECK_SIZE]) / DECK_SIZE)
        return best


def rank_of(scores, name):
    """0-based rank of name when scores are sorted best first (ties keep order)."""
    return sorted(scores, key=lambda n: -scores[n]).index(name)


def regret(scores, name):
    """How far below the top-scored card name is, in standard deviations of the pack."""
    sd = statistics.pstdev(scores.values()) or 1.0
    return (max(scores.values()) - scores[name]) / sd


def replay_draft(app, draft, skipped):
    """The draft's scored picks and final pool scores."""
    picks = []
    for pack_no, pick_no, taken, pack_names, pool_names in draft["picks"]:
        pack, pool = app.cards(pack_names), app.cards(pool_names)
        taken = app.cards([taken])
        if not taken:
            skipped["taken card not in dataset"] += 1
            continue
        taken = taken[0][app.constants.DATA_FIELD_NAME]
        if len({c[app.constants.DATA_FIELD_NAME] for c in pack}) < 2:
            skipped["fewer than 2 different cards in pack"] += 1
            continue
        scores = app.advise(pack, pool, pack_no, pick_no)
        if taken not in scores:
            skipped["taken card missing from advice"] += 1
            continue
        by_gihwr = {c[app.constants.DATA_FIELD_NAME]: app.gihwr(c) for c in pack}
        picks.append(
            [
                pack_no,
                pick_no,
                rank_of(scores, taken),
                round(regret(scores, taken), 4),
                rank_of(by_gihwr, taken),
            ]
        )

    deck_score = pool_gihwr = None
    if draft["picks"]:
        _, _, taken, _, pool_names = draft["picks"][-1]
        final_pool = app.cards(pool_names + [taken])
        if len(final_pool) >= DECK_SIZE:
            deck_score = round(app.deck_score(final_pool), 4)
            pool_gihwr = round(app.pool_gihwr(final_pool), 4)

    return {k: draft[k] for k in ("id", "skill", "games", "wins", "losses")} | {
        "picks": picks,
        "deck_score": deck_score,
        "pool_gihwr": pool_gihwr,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--src", default=".", help="Folder holding the app's src/ to replay"
    )
    parser.add_argument("--drafts", required=True, help="Drafts from sample.py")
    parser.add_argument(
        "--dataset",
        required=True,
        help="The app's dataset for the set (.json or .json.gz)",
    )
    parser.add_argument("--set", default="", help="Set code, for the report")
    parser.add_argument("--label", required=True, help="base or head")
    parser.add_argument(
        "--out", required=True, help="Where to write the results (.json)"
    )
    args = parser.parse_args(argv)

    sys.path.insert(0, os.path.abspath(args.src))
    app = App(args.dataset)
    with gzip.open(args.drafts, "rt", encoding="utf-8") as f:
        drafts = json.load(f)

    start, skipped = time.time(), Counter()
    results = [replay_draft(app, d, skipped) for d in drafts]
    seconds = time.time() - start
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(
            {
                "set": args.set,
                "label": args.label,
                "seconds": round(seconds),
                "skipped": dict(skipped),
                "unmatched": dict(app.unmatched.most_common(10)),
                "drafts": results,
            },
            f,
        )
    print(
        f"Replayed {len(results)} drafts in {seconds:.0f}s ({args.label}, {args.src})"
    )


if __name__ == "__main__":
    main()

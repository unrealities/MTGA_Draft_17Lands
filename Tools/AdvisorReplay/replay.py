"""Replay sampled drafts through one copy of the app's advisor.

    python Tools/AdvisorReplay/replay.py --src . \
        --drafts drafts.json.gz --dataset FRA_PremierDraft_All_Data.json.gz \
        --label head --out head.json

At every pick, the advisor sees the pack and the cards taken so far, as it
would in the app, and the harness records where it ranked the card the drafter
took. Each final pool also gets the app's deck score. --src picks which copy of
the app to import, so a pull request and its base can replay the same drafts.
With --simulate, replay the head first and give the base --judge with the head's
results, so one deck score grades both copies' simulated decks.
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

import simulate

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
        from src.advisor import deck_builder, deck_scorer

        # Suggest Deck's simulator stats and sideboards are only shown in the
        # app; they don't rank its decks. Skipping them leaves the decks and their
        # order as they were and makes Suggest Deck about twenty times faster.
        deck_builder.simulate_deck = lambda *args, **kwargs: {}
        deck_builder.get_sideboard = lambda *args, **kwargs: []
        self.deck_builder, self.scorer = deck_builder, deck_scorer

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
        return self.quick_build(pool)[0]

    def quick_build(self, pool):
        """(score, deck, colors) of the best of the app's quick deck builds."""
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
                (
                    cl.calculate_holistic_score(deck, colors, len(pool), self.metrics)[0],
                    deck,
                    colors,
                )
                for deck, colors in builds
                if deck
            ),
            key=lambda build: build[0],
            default=(0.0, [], []),
        )

    def suggest(self, pool):
        """Suggest Deck's decks for the pool, best first, as the app shows them."""
        self.deck_builder.clear_deck_cache()
        return self.deck_builder.suggest_deck(pool, self.metrics, None, "PremierDraft")

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


def in_pick_order(earlier, pool_names):
    """pool_names with the cards of earlier first, in that order, then the rest.

    The dump lists a pool by card, not by pick. The app holds it in pick order,
    and the advisor weights later picks more. Passing each pick's result as the
    next pick's earlier keeps the order, with no need for a row for every pick.
    """
    left = Counter(pool_names)
    kept = []
    for name in earlier:
        if left[name] > 0:
            left[name] -= 1
            kept.append(name)
    return kept + list(left.elements())


def replay_draft(app, draft, skipped, sim=None, drafter_deck=False):
    """The draft's scored picks and final pool scores.

    sim, a Counter, also has the advisor draft the packs itself (simulate.py);
    drafter_deck also scores the drafter's own pool the same way."""
    picks, pool_names = [], []
    for pack_no, pick_no, taken, pack_names, by_card in draft["picks"]:
        pool_names = in_pick_order(pool_names, by_card)
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
        taken = draft["picks"][-1][2]
        final_pool = app.cards(pool_names + [taken])
        if len(final_pool) >= DECK_SIZE:
            deck_score = round(app.deck_score(final_pool), 4)
            pool_gihwr = round(app.pool_gihwr(final_pool), 4)

    out = {k: draft[k] for k in ("id", "skill", "games", "wins", "losses")} | {
        "picks": picks,
        "deck_score": deck_score,
        "pool_gihwr": pool_gihwr,
    }
    if sim is not None:
        out["sim"] = simulate.simulate_draft(app, draft, sim)
        if out["sim"] and drafter_deck:
            # The drafter's own pool through the same Suggest Deck, for comparison.
            final_pool = app.cards(pool_names + [draft["picks"][-1][2]])
            score = simulate.deck_rating(app, final_pool)[0]
            out["sim"]["drafter_win"] = round(simulate.win_rate(score, app.scorer), 4)
    return out


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
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Also let the advisor draft each draft's packs itself (simulate.py)",
    )
    parser.add_argument(
        "--judge",
        help="Another copy's --simulate results: also grade its decks with this "
        "copy's deck score (the base judges the head)",
    )
    args = parser.parse_args(argv)
    if args.judge and not args.simulate:
        parser.error("--judge needs --simulate")

    sys.path.insert(0, os.path.abspath(args.src))
    app = App(args.dataset)
    with gzip.open(args.drafts, "rt", encoding="utf-8") as f:
        drafts = json.load(f)

    start, skipped = time.time(), Counter()
    sim = Counter() if args.simulate else None
    # Every copy replays the same drafters' pools; the base alone scores them.
    drafter_deck = args.simulate and args.label == "base"
    results = [replay_draft(app, d, skipped, sim, drafter_deck) for d in drafts]
    if args.judge:
        with open(args.judge, encoding="utf-8") as f:
            theirs = {d["id"]: d.get("sim") for d in json.load(f)["drafts"]}
        for result in results:
            if result["sim"] and theirs.get(result["id"]):
                result["sim"]["head_win"] = simulate.grade(app, theirs[result["id"]])
                sim["decks graded for the other copy"] += 1
    seconds = time.time() - start
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(
            {
                "set": args.set,
                "label": args.label,
                "seconds": round(seconds),
                "skipped": dict(skipped),
                "simulation": dict(sim) if sim is not None else None,
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

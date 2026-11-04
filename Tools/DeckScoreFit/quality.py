"""Each sampled deck's card quality under versions of the engine's card rating.

    python Tools/DeckScoreFit/quality.py --src . --decks decks.json.gz \
        --games games.json.gz --dataset FRA_PremierDraft_All_Data.json.gz \
        --set FRA --out FRA.json

The win rates are games.py's: a deck is rated from the counts of the folds
other than its own, so no deck's results are in the ratings it is scored
with, and shrinkage reads games in hand over every fold, which needs no
results. The app's
dataset only says which cards are spells. Each version follows
_calculate_weighted_score() and the power bonus in evaluate_pack() in
src/advisor/engine.py, with the archetype the deck's main colors and the
format's mean and SD for the pack's; a deck's quality is the average of its
spells' values. See README.md.
"""

import argparse
import gzip
import json
import os
import statistics
import sys

from features import App
from games import FOLDS, fold_of

ALL = "All Decks"
# Games in hand a rating needs: overall, and in a pair (the engine's minimum).
MIN_OVERALL = 200
MIN_PAIR = 10
# Games not drawn that IWD needs.
MIN_NOT_DRAWN = 50
SHRINK_SAMPLES = 1000.0
IWD_PREMIUM = 1.15
IWD_THRESHOLD = 4.5
# The engine's blend weight averaged over a pack's 14 picks: 0.6 + 0.7 * 7.5 / 15.
ENGINE_WEIGHT = 0.6 + 0.7 * 7.5 / 15

# name: (blend weight, shrink, IWD premium, power bonus)
VERSIONS = {
    "engine": (ENGINE_WEIGHT, True, True, True),
    "no-archetype": (0.0, True, True, True),
    "no-shrinkage": (ENGINE_WEIGHT, False, True, True),
    "no-iwd": (ENGINE_WEIGHT, True, False, True),
    "weight-0.65": (0.65, True, True, True),
    "weight-1.3": (1.3, True, True, True),
    "no-power-bonus": (ENGINE_WEIGHT, True, True, False),
    "overall-only": (0.0, True, False, False),
}
# The deck score's own blend (get_card_rating() in deck_scorer.py).
DECK_SCORE = "deck-score-blend"


def training(folds, f):
    """Counts for rating fold f's decks: [in hand, won, in hand in every fold,
    not drawn, won], from the other folds except the third."""
    out = {}
    for i, ratings in enumerate(folds):
        for colors, cards in ratings.items():
            group = out.setdefault(colors, {})
            for name, (seen, won, unseen, unseen_won) in cards.items():
                s = group.setdefault(name, [0, 0, 0, 0, 0])
                s[2] += seen
                if i != f:
                    s[0] += seen
                    s[1] += won
                    s[3] += unseen
                    s[4] += unseen_won
    return out


class Ratings:
    """Win rates from games.py's counts."""

    def __init__(self, counts):
        self.counts = counts
        overall = [self.overall(name) for name in counts.get(ALL, {})]
        rated = [wr for wr in overall if wr is not None]
        self.mean = statistics.mean(rated)
        self.std = statistics.pstdev(rated) or 4.0

    def overall(self, name):
        s = self.counts.get(ALL, {}).get(name)
        return 100.0 * s[1] / s[0] if s and s[0] >= MIN_OVERALL else None

    def iwd(self, name):
        s = self.counts[ALL][name]
        if s[3] < MIN_NOT_DRAWN:
            return 0.0
        return 100.0 * s[1] / s[0] - 100.0 * s[4] / s[3]

    def pair(self, name, colors):
        """(win rate, games in hand over every game), or (None, 0)."""
        s = self.counts.get(colors, {}).get(name)
        if not s or s[0] < MIN_PAIR:
            return None, 0
        return 100.0 * s[1] / s[0], s[2]

    def score(self, wr):
        return max(0.0, 50.0 + (wr - self.mean) / max(0.1, self.std) * 15.0)

    def value(self, name, colors, version):
        """A card's value under a version, or None if it has no overall rating."""
        g = self.overall(name)
        if g is None:
            return None
        if version == DECK_SCORE:
            a, _ = self.pair(name, colors)
            return self.score(0.7 * a + 0.3 * g if a is not None else g)
        weight, shrink, premium, bonus = VERSIONS[version]
        wr = g
        a, samples = self.pair(name, colors)
        if a is not None and weight:
            confidence = min(1.0, samples / SHRINK_SAMPLES) if shrink else 1.0
            trusted = a * confidence + g * (1.0 - confidence)
            wr = g * (1.0 - weight) + trusted * weight
        value = self.score(wr)
        if bonus:
            z = (g - self.mean) / self.std
            mult = IWD_PREMIUM if premium and self.iwd(name) > IWD_THRESHOLD and z > 1 else 1.0
            value += max(0.0, z * 10 * mult) if z > 0.5 else 0.0
        return value


def deck_quality(app, ratings, decks):
    """{deck id: {version: quality}} for decks with a rated spell.

    ratings: one Ratings, or one per fold to rate each deck by its fold's.
    """
    out = {}
    names = list(VERSIONS) + [DECK_SCORE]
    for d in decks:
        deck = app.deck(d["cards"])
        if deck is None:
            continue
        spells = [
            (name, count)
            for (name, count), card in zip(d["cards"].items(), deck)
            if "Land" not in card.get("types", [])
        ]
        r = ratings[fold_of(d["id"])] if isinstance(ratings, list) else ratings
        values = {}
        for version in names:
            got = [
                (v, count)
                for name, count in spells
                if (v := r.value(name, d["main_colors"], version)) is not None
            ]
            n = sum(c for _, c in got)
            if n:
                values[version] = sum(v * c for v, c in got) / n
        if len(values) == len(names):
            out[d["id"]] = values
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--src", required=True, help="The copy of the app to use")
    parser.add_argument("--decks", required=True, help="From decks.py (.json.gz)")
    parser.add_argument("--games", required=True, help="From games.py (.json.gz)")
    parser.add_argument("--dataset", required=True, help="The app's set data")
    parser.add_argument("--set", required=True, help="Set code, for the report")
    parser.add_argument("--out", required=True, help="Where to write them (.json)")
    args = parser.parse_args(argv)

    sys.path.insert(0, os.path.abspath(args.src))
    app = App(args.dataset)
    with gzip.open(args.decks, "rt", encoding="utf-8") as f:
        decks = json.load(f)
    with gzip.open(args.games, "rt", encoding="utf-8") as f:
        folds = json.load(f)["folds"]
    ratings = [Ratings(training(folds, i)) for i in range(FOLDS)]
    quality = deck_quality(app, ratings, decks)
    mean = statistics.mean(r.mean for r in ratings)
    std = statistics.mean(r.std for r in ratings)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"set": args.set, "mean": mean, "std": std, "decks": quality}, f)
    print(f"{args.set}: {len(quality)} decks; format mean {mean:.2f}, SD {std:.2f}")


if __name__ == "__main__":
    main()

"""Each sampled deck's card quality under versions of the engine's card rating.

    python Tools/DeckScoreFit/quality.py --src . --decks decks.json.gz \
        --games games.json.gz --dataset FRA_PremierDraft_All_Data.json.gz \
        --set FRA --out FRA.json

The win rates are games.py's, and each deck gets one quality per version for
each of horse.py's splits. In split t the test decks are fold t's, and every
win rate behind that split, for its training decks as much as its test decks,
leaves out fold t's results. So a test deck is rated from the other folds, and
a training deck from the other folds but its own. Shrinkage reads games in hand
over every fold, which needs no results. The app's dataset only says which
cards are spells.

Only decks with two main colors are rated: for them the deck's pair is the
archetype the advisor looks up. It uses All Decks with fewer than two main
colors, and only two of three, so a deck's final colors would stand for
something else. Each version follows _calculate_weighted_score() and the power
bonus in evaluate_pack() in src/advisor/engine.py, with the format's mean and SD
for the pack's; a deck's quality is the average of its spells' values. See
experiments/2026-11-03-rating-parts/PROTOCOL.md.
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
# Games in hand over every fold a rating needs: 17Lands shows the app no rate
# with fewer.
MIN_SAMPLES = 500
# Games not drawn that IWD needs.
MIN_NOT_DRAWN = 50
SHRINK_SAMPLES = 1000.0
IWD_PREMIUM = 1.15
IWD_THRESHOLD = 4.5
# The engine's blend weight averaged over a pack's 14 picks: 0.6 + 0.7 * 7.5 / 15.
ENGINE_WEIGHT = 0.6 + 0.7 * 7.5 / 15

# Historical rating-parts/pair-parts experiments use the pre-4.32 engine as
# their baseline. Keep these names and definitions stable for reproduction;
# the live advisor stopped shrinking pair rates in #259 (4.32).
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
NAMES = list(VERSIONS) + [DECK_SCORE]
# A card's value split for parts.py, in score points: no-archetype's value, then
# what the pair's rates add to it at weight 1, split into the pair's level and
# the card's fit. fit-few and fit-many are fit by the pair's games in hand.
PARTS = ["overall", "level", "fit", "fit-few", "fit-many"]
FEW_GAMES = 3000


def training(folds, left_out):
    """Counts for rating decks: [in hand, won, in hand in every fold, not drawn,
    won]. Only the third reads the folds in left_out."""
    out = {}
    for i, ratings in enumerate(folds):
        for colors, cards in ratings.items():
            group = out.setdefault(colors, {})
            for name, (seen, won, unseen, unseen_won) in cards.items():
                s = group.setdefault(name, [0, 0, 0, 0, 0])
                s[2] += seen
                if i not in left_out:
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
        # A small set can have no card with enough games in these folds.
        self.mean = statistics.mean(rated) if rated else 0.0
        self.std = (statistics.pstdev(rated) if rated else 0.0) or 4.0
        self.values = {}

    def overall(self, name):
        s = self.counts.get(ALL, {}).get(name)
        return 100.0 * s[1] / s[0] if s and s[2] >= MIN_SAMPLES and s[0] else None

    def iwd(self, name):
        s = self.counts[ALL][name]
        if s[3] < MIN_NOT_DRAWN:
            return 0.0
        return 100.0 * s[1] / s[0] - 100.0 * s[4] / s[3]

    def pair(self, name, colors):
        """(win rate, games in hand over every game), or (None, 0)."""
        s = self.counts.get(colors, {}).get(name)
        if not s or s[2] < MIN_SAMPLES or not s[0]:
            return None, 0
        return 100.0 * s[1] / s[0], s[2]

    def score(self, wr):
        return max(0.0, 50.0 + (wr - self.mean) / max(0.1, self.std) * 15.0)

    def pair_gain(self, name, colors):
        """How far the engine's shrunk pair rate is from the card's overall rate,
        in win rate points, or None if it lacks either rate."""
        g = self.overall(name)
        a, samples = self.pair(name, colors)
        if g is None or a is None:
            return None
        return min(1.0, samples / SHRINK_SAMPLES) * (a - g)

    def level(self, colors):
        """The mean pair_gain of the pair's rated cards, by games in hand."""
        key = ("level", colors)
        if key not in self.values:
            total = weight = 0.0
            for name, s in self.counts.get(colors, {}).items():
                gain = self.pair_gain(name, colors)
                if gain is not None:
                    total += s[0] * gain
                    weight += s[0]
            self.values[key] = total / weight if weight else 0.0
        return self.values[key]

    def parts(self, name, colors):
        """A card's PARTS, or None if it has no overall rating."""
        value = self.value(name, colors, "no-archetype")
        if value is None:
            return None
        gain = self.pair_gain(name, colors)
        if gain is None:
            return [value, 0.0, 0.0, 0.0, 0.0]
        points = 15.0 / max(0.1, self.std)
        level, fit = points * self.level(colors), points * (gain - self.level(colors))
        few = self.pair(name, colors)[1] < FEW_GAMES
        return [value, level, fit, fit if few else 0.0, 0.0 if few else fit]

    def value(self, name, colors, version):
        """A card's value under a version, or None if it has no overall rating."""
        key = (name, colors, version)
        if key not in self.values:
            self.values[key] = self._value(name, colors, version)
        return self.values[key]

    def _value(self, name, colors, version):
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


class Splits:
    """The Ratings of each pair of a deck's fold and horse.py's split."""

    def __init__(self, folds):
        self.folds = folds
        self.ratings = {}

    def of(self, fold, split):
        key = frozenset((fold, split))
        if key not in self.ratings:
            self.ratings[key] = Ratings(training(self.folds, key))
        return self.ratings[key]


def deck_quality(app, splits, decks):
    """{deck id: for each split, each of NAMES' quality}, for two-color decks
    with a rated spell under every version in every split."""
    out = {}
    for d in decks:
        if len(d["main_colors"]) != 2:
            continue
        deck = app.deck(d["cards"])
        if deck is None:
            continue
        spells = _spells(d, deck)
        fold = fold_of(d["id"])
        rows = [
            _qualities(splits.of(fold, split), spells, d["main_colors"])
            for split in range(FOLDS)
        ]
        if all(rows):
            out[d["id"]] = rows
    return out


def _spells(d, deck):
    return [
        (name, count)
        for (name, count), card in zip(d["cards"].items(), deck)
        if "Land" not in card.get("types", [])
    ]


def deck_parts(app, splits, decks, keep):
    """{deck id: for each split, the average of PARTS over its spells}, for the
    decks in keep. It averages over the spells with an overall rating, as
    no-archetype's quality does."""
    out = {}
    for d in decks:
        if d["id"] not in keep:
            continue
        spells = _spells(d, app.deck(d["cards"]))
        fold = fold_of(d["id"])
        rows = []
        for split in range(FOLDS):
            ratings = splits.of(fold, split)
            total, n = [0.0] * len(PARTS), 0
            for name, count in spells:
                parts = ratings.parts(name, d["main_colors"])
                if parts is not None:
                    n += count
                    total = [t + count * p for t, p in zip(total, parts)]
            rows.append([round(t / n, 3) for t in total])
        out[d["id"]] = rows
    return out


def _qualities(ratings, spells, colors):
    """Each of NAMES' average over the spells, or None if a version rates none."""
    row = []
    for version in NAMES:
        got = [
            (v, count)
            for name, count in spells
            if (v := ratings.value(name, colors, version)) is not None
        ]
        n = sum(c for _, c in got)
        if not n:
            return None
        row.append(round(sum(v * c for v, c in got) / n, 3))
    return row


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
    splits = Splits(folds)
    quality = deck_quality(app, splits, decks)
    parts = deck_parts(app, splits, decks, quality)
    pairs = {d["id"]: d["main_colors"] for d in decks if d["id"] in quality}
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"set": args.set, "versions": NAMES, "decks": quality,
                   "part_names": PARTS, "parts": parts, "pairs": pairs}, f)
    print(f"{args.set}: rated {len(quality)} of {len(decks)} decks")


if __name__ == "__main__":
    main()

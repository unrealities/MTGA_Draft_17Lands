"""Compute the app's deck score features for sampled decks.

    python Tools/DeckScoreFit/features.py --src . --decks decks.json.gz \
        --dataset FRA_PremierDraft_All_Data.json.gz --set FRA --out FRA.json

Each deck goes through deck_features() in the copy of the app at --src, with
that copy's card data, so the fit uses the same features as the app.
"""

import argparse
import gzip
import json
import os
import shutil
import sys
import tempfile
from collections import Counter

# A full draft pool, so a finished deck is never short of spells for its pool.
POOL_SIZE = 45
BASICS = {"Plains": "W", "Island": "U", "Swamp": "B", "Mountain": "R", "Forest": "G"}


class App:
    """The deck scorer and card data, from the src/ on sys.path."""

    def __init__(self, dataset_path):
        from src.advisor import deck_scorer
        from src.advisor.mana_base import create_basic_lands
        from src.card_utils import get_functional_cmc
        from src.dataset import Dataset
        from src.set_metrics import SetMetrics

        self.scorer, self.create_basic_lands = deck_scorer, create_basic_lands
        self.get_functional_cmc = get_functional_cmc
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
            name = card.get("name", "")
            self.full_names.setdefault(name.split(" // ")[0], name)
        self.unmatched = Counter()

    def deck(self, cards):
        """Card dicts with counts for {name: count}, or None if a card is missing."""
        deck = []
        for name, count in cards.items():
            if name in BASICS:
                deck += [
                    dict(land, count=count)
                    for land in self.create_basic_lands(BASICS[name], 1)
                ]
                continue
            found = self.dataset.get_data_by_name([self.full_names.get(name, name)])
            if not found:
                self.unmatched[name] += count
                return None
            deck.append(dict(found[0], count=count))
        return deck

    def extra(self, deck, colors):
        """Plain counts that aren't features, for the LightGBM yardstick."""
        spells = [c for c in deck if "Land" not in c.get("types", [])]
        n = sum(c["count"] for c in spells) or 1
        return {
            "lands": sum(c["count"] for c in deck if "Land" in c.get("types", [])),
            "spells": n,
            "creatures": sum(
                c["count"] for c in spells if "Creature" in c.get("types", [])
            ),
            "cheap_spells": sum(
                c["count"] for c in spells if self.get_functional_cmc(c) <= 2
            ),
            "mean_mana_value": sum(
                self.get_functional_cmc(c) * c["count"] for c in spells
            )
            / n,
            "colors": len(colors),
        }


def deck_rows(app, decks):
    """A row of features and results for each deck, and why any were skipped."""
    rows, skipped = [], Counter()
    for d in decks:
        deck = app.deck(d["cards"])
        if deck is None:
            skipped["card not in dataset"] += 1
            continue
        colors = list(d["main_colors"] + d["splash_colors"])
        features = app.scorer.deck_features(deck, colors, POOL_SIZE, app.metrics)
        if features is None:
            skipped["no spells"] += 1
            continue
        rows.append(
            {
                "id": d["id"],
                "wins": d["wins"],
                "games": d["games"],
                "skill": d["skill"],
                "experience": d["experience"],
                "features": features,
                "extra": app.extra(deck, colors),
            }
        )
    return rows, skipped


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--src", required=True, help="The copy of the app to use")
    parser.add_argument("--decks", required=True, help="From decks.py (.json.gz)")
    parser.add_argument("--dataset", required=True, help="The app's set data")
    parser.add_argument("--set", required=True, help="Set code, for the report")
    parser.add_argument("--out", required=True, help="Where to write them (.json)")
    args = parser.parse_args(argv)

    sys.path.insert(0, os.path.abspath(args.src))
    app = App(args.dataset)
    with gzip.open(args.decks, "rt", encoding="utf-8") as f:
        rows, skipped = deck_rows(app, json.load(f))

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(
            {
                "set": args.set,
                "base_score": app.scorer.BASE_SCORE,
                "weights": app.scorer.WEIGHTS,
                "skipped": dict(skipped),
                "unmatched": dict(app.unmatched.most_common(10)),
                "rows": rows,
            },
            f,
        )
    print(f"{args.set}: {len(rows)} decks, skipped {dict(skipped)}")


if __name__ == "__main__":
    main()

# The card prior (assets/models/card_prior_z_table.npz)

## What it is

A per-card prior quality score, in **z units of the set's GIH win rate**
(17Lands terminology), for 38,542 cards. The advisor uses it as the
shrinkage target in `card_wr_posteriors` (`src/advisor/deck_scorer.py`):
for a card with little observed data, the rating is pulled toward
`set_mean + z * set_std` instead of the bare set mean — a bomb and a filler
with three games are no longer indistinguishable.

The table is a dict lookup at runtime: normalized card name (plus a
face-name index for split/DFC cards) to a float32 z clamped to the bounds
in the manifest (`z_clamps`, ±5.5). Cards outside the table fall back to
the v1 live-extractor path, then to the set mean.

## How it was built (provenance)

Two components, composed as `combined_z = max(statistical_z, floor)`:

1. **Statistical prior (v5 level-1).** LightGBM on Scryfall-oracle-derived
   regex features plus deck-embedding features, trained on per-set card
   targets computed from 17Lands public game data across 34 sets, with two
   sets frozen out for honest evaluation (FRA spearman 0.6653 / DFT 0.6149,
   cards of the frozen sets excluded from training). The deck embeddings are
   word2vec over ~3.5M public draft deck lists.
2. **Structural floors.** Narrow hand-derived rules over parsed Forge card
   scripts (mana / draw-3-at-cmc<=1 / extra-turn / any-card-tutor economics
   with strict access gating — costs, conditions, delays and resource
   dependencies disqualify), value-calibrated on measured cube anchors
   (Umezawa's Jitte z=+5.44 in TMT, Wurmcoil Engine z=+3.96 in BRO). 28
   cards carry floors; they exist because no premier training set contains
   a Black Lotus, and an in-distribution model prices one at the bottom.
   The floor classes and their regressions were hardened through a
   multi-round independent review.

## Data sources and licenses

- **17Lands public datasets** (game/draft data, CC BY 4.0,
  https://www.17lands.com/public_datasets): per-set card win-rate targets,
  deck lists for embeddings. Derived values are transformations; credit to
  17Lands is required and given; the license link and changes are described
  here and in the project README.
- **Scryfall** oracle text (https://scryfall.com/docs/api): regex card
  features. Snapshot on disk at training time; Scryfall's terms and
  attribution apply to the source data.
- **Forge card scripts** (https://github.com/Card-Forge/forge, GPL-3.0):
  parsed locally to derive the structural floors. No Forge code or script
  text is redistributed in this repository or its assets; the shipped
  numbers are the output of our own computation on our own inputs
  (see the GNU FAQ on program output).
- Magic: the Gathering and its card names are property of Wizards of the
  Coast. This project is unofficial and not endorsed by Wizards; card names
  appear factually as identifiers.

## Regeneration

The training/export pipeline lives outside this repository (17Lands bulk
data, Scryfall and Forge snapshots, ~1.8GB). The export contract is:

- `card_prior_z_table.npz`: `names` (unicode array), `z` (float32, clamped
  to the manifest bounds), `feature_names` (documentation only).
- `card_prior_z_table_manifest.json`: schema, provenance notes, `n_cards`,
  `n_lifted`, `z_clamps`. The loader refuses to publish the table if the
  manifest is missing or malformed; the fallback chain then runs v1
  live-extractor models (if their assets load) and finally the set mean.

## Precedence and fallback

`combined = max(statistical, floor)` per card; lookup miss -> v1
live-extractor model (if its assets load) -> set mean (z = 0). Split-card
faces resolve through the face index; a face name that exists as its own
card keeps its own row.

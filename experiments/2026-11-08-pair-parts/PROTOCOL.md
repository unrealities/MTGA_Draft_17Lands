# Why the whole-deck test and the replay disagree about pair win rates

Written before any result in this folder was seen.

## Why

Two tests, on results held out from the ratings, disagree about the engine's
blend of a card's overall win rate with its win rate in the lane's pair:

- **Whole decks** (`experiments/2026-11-03-rating-parts`): a deck's average
  rating predicts its games better with no blend, by 27.6% of card quality's
  worth.
- **Picks** (`experiments/2026-11-08-heldout-replay`): within a pack, the blend's
  top card is more closely tied to event wins, by a regret slope of 0.0063
  (SE 0.0020).

The earlier protocols name one difference: a pair's overall level cancels within
a pack but not across decks. The whole-deck model has one slope and no color-pair
terms, so it prices that level like card quality.

The slope is why that could matter. The deck score's win curve (0.0387 log-odds a
point, 12 points per SD of card quality, an SD near 4 win rate points) makes one
point of average card rating worth about 2.9 points of deck win rate. But a pair
whose decks win one point more has cards rated about one point higher: there the
ratio is near 1.

## The split

`quality.py` splits what the pair's rates add to each card, at weight 1:

- **gain:** the engine's shrunk pair rate less the overall rate;
- **level:** the games-weighted mean gain of the cards rated in that pair, in the
  ratings for that split;
- **fit:** the card's gain less the level.

A card with no pair rate adds nothing to either. A deck's parts are averages over
its spells, in score points, so a deck's engine rating is its no-archetype rating
plus 0.95 x (level + fit). The ratings, folds, 500-game minimum and two-color
decks are those of the rerun in the held-out replay's results.

## What runs

The Pair parts workflow, on all 20 sets, up to 50,000 decks each, salt `""`, the
same decks as before. `parts.py` fits `fit.py`'s logistic regression, controlling
for the set, the player's buckets and the other deck features:

- **Weights:** each deck rated from the four folds that aren't its own, with the
  overall rating, level and fit each given their own slope. A part's weight is
  its slope over the overall rating's slope, so 0.95 is what the engine assumes
  and 0 is no blend. Fit both without and with color-pair-by-set terms (pairs with
  under 50 decks in a set share its baseline). With those terms, every deck of a
  pair shares a level, so only fit has a weight. SEs are clustered by set, and
  intervals are 95% with t on 19 degrees of freedom (2.09).
- **Held-out log loss:** `horse.py`'s five splits, against the overall rating:
  the engine's rating, *fit only* (0.95 x fit), *level only* (0.95 x level), and
  free slopes. All but level only again with pair terms, against the overall
  rating with pair terms. Intervals are 1.96 per-draft SEs.

## How it is read

The primary measure is **fit's weight with the pair terms**:

- **Its interval includes zero or is below it: not the level.** Within a pair,
  whole-deck results don't see the card fit that the blend adds. Whatever the
  replay sees, it isn't this value in a finished deck.
- **Its interval is above zero, and fit only beats the overall rating in held-out
  log loss (interval above zero): the level explains it.** The whole-deck
  objection is to the pair's level, not to the card's fit, and the two tests no
  longer disagree about the fit.
- **Its interval is above zero, but fit only doesn't beat the overall rating:
  partly.** The fit is real but worth less than the 0.95 the engine gives it. The
  weight's interval says how much less.

**Prediction, made here so that it can fail:** level's weight is well below fit's,
and near a third (2.9 to 1, the ratio above).

## Also reported, not deciding

- Fit's weight by the pair's games in hand, under and from 3,000. If noise is
  holding it down, it should be larger with many games.
- Fit's weight for strong drafters (58% or more, as in the rule tests) and the rest.
- Weights per set. The Cube is shown but not counted: it has 131 decks here.

## What it can't show

- It values cards in finished decks. A result on fit says nothing about whether
  following the blend changes what a drafter ends up with.
- The pair is the deck's final pair, the best case. During a draft the engine
  guesses the lane.
- Level also cancels only among cards rated in the pair. A card with no pair rate
  keeps its overall rate, so in a pack the level still moves on-lane cards against
  off-lane ones. This test can't measure that; a replay can.
- It's observational. Pair terms remove what a pair's drafters share, but not what
  makes a deck with well-fitting cards different in other ways.

## Running it

Actions → Pair parts → Run workflow. Locally, for each set, follow the rating
test's protocol, then:

```sh
poetry run python Tools/DeckScoreFit/parts.py --features results/*.json --quality results/quality/*.json --json parts.json
```

Tests: `poetry run pytest Tools/DeckScoreFit/tests`.

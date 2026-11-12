# Which card rating predicts results: protocol

`Tools/DeckScoreFit/horse.py` tests three things the engine does to a card's
rating before anything else in a pick (`_calculate_weighted_score()` and the
power bonus in `evaluate_pack()` in `src/advisor/engine.py`):

- **Archetype weighting** (`no-archetype`): the card's win rate in the lane's
  pair is blended in with weight 0.6 + 0.7 x pick / 15.
- **Shrinkage** (`no-shrinkage`): the pair's win rate is first shrunk toward
  the overall one by `min(1, samples / 1000)`.
- **The IWD premium** (`no-iwd`): the bonus for a card well above the pack (10
  points per SD above the pack's mean, from 0.5 SD) is 1.15x for a card more
  than 1 SD above with IWD over 4.5.

Each version of the rating gives a deck a quality: the average, over its
spells, of the card's value on the engine's scale (50 at the format mean, 15
points per SD) plus its power bonus, taking the format's mean and SD for the
pack's. The blend weight is 0.95, its average over a pack's picks. A version
is better if its deck quality predicts held-out decks' results better.

## Which decks

Only decks with two main colors. For them the deck's pair is the archetype the
advisor looks up. The advisor uses All Decks with fewer than two main colors,
and only two of three, so for those decks the final colors would name a blend
the advisor doesn't use. A test compares a two-color deck's value with
`DraftAdvisor._calculate_weighted_score()`.

## Keeping results out of the ratings

17Lands' ratings come from the same games as the results, which would favor
whatever fits them most closely: pair win rates from few games most of all. So
`games.py` computes the win rates again. Every draft in the dump falls in one
of five folds by a hash of its ID, with all of its builds.

Those folds are also the test's splits. In split *t*, the test decks are fold
*t*'s and the model is fit on the others. Every win rate behind that split
leaves out fold *t*'s results:

- a test deck is rated from the four other folds;
- a training deck is rated from the three folds that are neither its own nor
  *t*.

So a split's test games are in neither the ratings nor the fit, and no deck's
results are in its own ratings. A card's overall rating needs 200 such games and
a pair rating 10 (the engine's own minimum). Shrinkage counts games in hand in
every fold, which needs no results. A deck is kept only if every version rates
it in every split.

## Decided before this run

- **Model:** `fit.py`'s logistic regression with card quality replaced by each
  version, fit on four fifths of the drafts and scored on the other fifth, five
  times.
- **Primary result:** the engine's version against each ablation, in held-out
  log loss per game, with 98.33% intervals (95% familywise across the three).
  SEs come from per-draft differences, so a draft with two builds counts once.
  The gain is also given as a share of what card quality is worth: the log loss
  without any card quality less the engine's version.
- **Verdict:** *engine's predicts better* or *ablation predicts better* if the
  interval excludes zero. *No difference* if the whole interval is within 2% of
  what card quality is worth. Otherwise *can't tell*.
- **Also reported, without verdicts:** blend weights 0.65 and 1.3, no power
  bonus, overall GIH WR alone, the deck score's own blend (0.7 pair, 0.3
  overall, no shrinkage), and each comparison per set.

## Limits

- It tests whole decks, not the order of cards in a pack. A pair's overall level
  cancels out within a pack but not across decks. So a result here can't justify
  changing pick order without a replay of picks.
- The archetype is the deck's final pair, the best case. During a draft the
  engine has to guess the lane.
- One average weight stands for a blend weight that changes during the draft.
- Training decks are rated from three fifths of the dump and test decks from
  four fifths, so the fit sees noisier qualities than it scores. Noisier ratings
  favor shrinkage and overall win rates, which is the direction of some of the
  comparisons.
- It's observational, and the model has no color-pair terms.

## Earlier runs

Runs from the closed #244 aren't comparable and shouldn't be cited. They had
these faults, found in review:

- **Leak.** Test decks' results were in the training decks' ratings, because the
  splits used a different hash from the rating folds. So the earlier result
  against archetype weighting (−27% of card quality's worth) came from a leaky
  version.
- **Archetype.** Mono- and three-color decks were scored by an archetype the
  advisor wouldn't have used.
- **Intervals.** SEs treated a draft's builds as independent.

The earlier runs also mean this comparison isn't blind: the versions and the
verdict rule are unchanged from them, but their results were seen before these
fixes were made.

## Running it

Actions → Card ratings → Run workflow runs it on every set with Premier Draft
game data and Premier Draft ratings: 20 sets. MID, STX and VOW are left out
because their dumps have no `draft_id` or `build_index` to group games into
decks.

Locally, for each set, after `decks.py` and `features.py` as in
[the tool's README](../../Tools/DeckScoreFit/README.md):

```sh
poetry run python Tools/DeckScoreFit/games.py --games games.csv.gz --decks decks.json.gz --out games.json.gz
poetry run python Tools/DeckScoreFit/quality.py --src . --decks decks.json.gz --games games.json.gz --dataset dataset.json.gz --set FRA --out results/quality/FRA.json
```

Then, for all of them:

```sh
poetry run python Tools/DeckScoreFit/horse.py --features results/*.json --quality results/quality/*.json --json horse.json
```

Tests: `poetry run pytest Tools/DeckScoreFit/tests`.

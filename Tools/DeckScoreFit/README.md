# Deck score fit

Sets the weights in `src/advisor/deck_scorer.py` from real results. It takes
decks from 17Lands' public Premier Draft game data, computes each deck's
features with the app's own `deck_features()`, and fits how many games each
feature won.

It is separate from the app: nothing in `src/` imports it, and the app doesn't
need it to run. The weights it prints are pasted into `deck_scorer.py` by hand.
They are meant to hold across sets, so there is no need to refit for each new
set. Refit when a feature is added or changed, or to check that the weights
still hold.

CI runs the tool's own tests on every pull request, so a change to the deck
scorer that breaks the tool fails there.

## How the fit works

The deck score is `75 + sum of weight × feature`. Card quality (the deck's
average rating, in standard deviations) is the main feature, and its weight of
12 points sets the scale.

The fit is a logistic regression of each deck's game wins on its features.
Each feature's weight comes out in score points: a weight of +3 means the
feature was worth as many wins as a quarter of a standard deviation of card
quality.

It also takes the player into account, with the 17Lands win rate and
experience buckets, and the set. Without that, a feature that good players
happen to pick would look better than it is.

Card ratings come from the same games that are fitted. Features measured on top
of card quality aren't affected much, but the fit can't say whether card
quality itself is worth more or less than the ratings imply.

## What it reports

- **Weights:** the current and fitted weight of each feature, with a standard
  error, and the share of decks the feature applies to. A weight within two
  standard errors of 0 is marked `~0`. Features that no deck sets off are
  listed and left out.
- **Weights fit on each set alone:** if these agree, one set of weights serves
  every set.
- **On sets the fit didn't see:** each set is scored by weights fit on the
  others, comparing card quality alone, the current weights and the fitted
  weights. If LightGBM is installed, a LightGBM model on the same features is
  also shown. It isn't a candidate for the app; it shows how much a flexible
  model could gain over a weighted sum.
- **Records:** the game win rate and expected Premier Draft wins at each score.
- **For deck_scorer.py:** the fitted `WEIGHTS`, ready to paste, and the two
  numbers that turn a score into a win rate.

## On GitHub

Actions → Deck score fit → Run workflow. Set:

- `sets`: a JSON list of set codes, for example `["FRA", "TDM"]`; empty means
  all ten;
- `decks`: decks per set (default 50000);
- `salt`: any text, to sample different decks.

The run takes about 10 minutes. The report is on the run's summary page.

## Locally

```sh
SET=FRA
curl -fsSLo games.csv.gz "https://17lands-public.s3.amazonaws.com/analysis_data/game_data/game_data_public.$SET.PremierDraft.csv.gz"
curl -fsSLo dataset.json.gz "https://unrealities.github.io/MTGA_Draft_17Lands/${SET}_PremierDraft_All_Data.json.gz"

poetry run python Tools/DeckScoreFit/decks.py --games games.csv.gz --decks 5000 --out decks.json.gz
poetry run python Tools/DeckScoreFit/features.py --src . --decks decks.json.gz --dataset dataset.json.gz --set $SET --out results/$SET.json
poetry run python Tools/DeckScoreFit/fit.py results/*.json
```

Repeat all but the last line for each set. With one set, the report leaves out
the check on unseen sets.

Tests: `poetry run pytest Tools/DeckScoreFit/tests`.

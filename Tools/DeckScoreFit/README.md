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
  numbers that turn a score into a win rate. `missing_fixing` keeps the app's
  weight: game results can't fit it, so it is fit to drafters' builds instead
  (`NOT_FROM_GAMES` in `fit.py`).

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

## Testing pick rules on game results

`rules.py` uses the same decks to test three of the advisor's pick rules (in
`_calculate_composition_bonus()` in `src/advisor/engine.py`). Each rule
reweights a card by what the pool already has. If the rule is right, that
condition should show up in registered decks: decks where it holds should win
more or less often than the average rating of their spells predicts.

| rule | multiplier | tested on decks | the rule is supported if |
|---|---|---|---|
| Removal Saturated | 0.8x for removal once the pool has 7+ | each removal spell past the sixth, against a spell of the same rating | it's worth less |
| Curve Too Heavy | 0.7x for 5+ mana spells once the pool has 4+ | each 5+ mana spell past the fourth, against a spell of the same rating | it's worth less |
| Critical: Needs Fixing | 1.4x for fixing from pack 2 while fixing ≤ off-color playables | in decks with off-color spells, a fixing card while fixing ≤ off-color spells, against one once fixing is more | it's worth more |

Cards are counted the way the engine counts them: removal and fixing by the
app's Scryfall tags, plus multicolored lands for fixing, and heavy drops by
`get_functional_cmc()`. Off-color spells are the ones whose cost the deck's two
main colors can't pay. In a deck with 3+ main colors, the two with the most
pips count as main.

The model is fit.py's logistic regression: card quality, the app's other deck
features, the set, and the player's buckets. `missing_fixing` is left out of
the fixing model, because it measures the same shortfall. Removal and heavy
drops each get a slope and a change of slope at the rule's threshold. Fixing
gets a slope overall, a slope in decks with off-color spells, the off-color
count, and the shortfall `off-color + 1 - fixing` while it's positive.

Decided before the first run:

- **Primary result:** the effect per card, in game win rate points, with a
  98.33% interval (95% familywise across the three rules). The SE is the
  larger of the model's, widened for overdispersion, and the set-clustered
  sandwich.
- **Verdict:** *supported* if the interval excludes zero in the rule's
  direction, *contradicted* if it excludes zero the other way, otherwise *not
  established*. This is not evidence of equivalence.
- **Size:** the effect is also shown in rating SDs: the change in the card's
  GIH WR, in the format's SDs, that would move card quality as much. That
  makes it comparable with the rule's own size, its multiplier on the
  engine's score scale (removal and heavy drops taken at +1 SD, fixing at the
  mean).
- **Also reported** but not used for the verdict: per-set fits, added counts
  as controls (lands, creatures, colors), strong drafters only, and win rate
  by count against decks at the threshold.
- Sets whose decks never reach a rule's region (as when the dataset has no
  tags) are left out of that rule.

Limits:

- It tests registered decks, not pools: the rules count the pool, and decks
  are what drafters built from it.
- It's observational. Drafters who end up with eight removal spells or seven
  big spells may differ in ways that skill buckets don't capture.
- It measures what a card is worth relative to its rating, not the effect of
  switching the advisor's policy. Only a randomized trial can measure that.

Actions → Rule targets → Run workflow runs it on every set with Premier Draft
game data and Premier Draft ratings: 20 sets. MID, STX and VOW are left out
because their dumps have no `draft_id` or `build_index` to group games into
decks.

Locally, after the steps above:

```sh
poetry run python Tools/DeckScoreFit/rules.py results/*.json --json rules.json
```

Tests: `poetry run pytest Tools/DeckScoreFit/tests`.

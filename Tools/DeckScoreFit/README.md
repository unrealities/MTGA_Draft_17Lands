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

`rules.py` uses the same decks to test six of the advisor's pick rules (in
`_calculate_composition_bonus()` in `src/advisor/engine.py`). Each rule
reweights a card by what the pool already has. If the rule is right, that
condition should show up in registered decks: decks where it holds should win
more or less often than the average rating of their spells predicts.

| rule | multiplier | tested on decks | the rule is supported if |
|---|---|---|---|
| Removal Saturated | 0.8x for removal once the pool has 7+ | each removal spell past the sixth, against a spell of the same rating | it's worth less |
| Curve Too Heavy | 0.7x for 5+ mana spells once the pool has 4+ | each 5+ mana spell past the fourth, against a spell of the same rating | it's worth less |
| Critical: Needs Fixing | 1.4x for fixing from pack 2 while fixing ≤ off-color playables | in decks with off-color spells, a fixing card while fixing ≤ off-color spells, against one once fixing is more | it's worth more |
| Critical: Needs Creatures | 1.25x for creatures from pack 2 while the pool is on course for fewer than 13 | each creature while the deck has fewer than 13, against a spell of the same rating | it's worth more |
| Critical: Needs Removal | 1.3x for removal from pack 2 while the pool has fewer than 3 | each removal spell while the deck has fewer than 3, against a spell of the same rating | it's worth more |
| Critical: Needs 2-Drops | up to 1.5x (0.15x per one short) for creatures and removal of mana value ≤ 2, from pack 2, while the pool is on course for fewer than 7 | each such card while the deck has fewer than 7, against a spell of the same rating | it's worth more |

The first three were run first (results in
`experiments/2026-11-03-rule-targets/`). The last three, the keep-or-drop
reading and the deck score terms below were added afterwards. They were
written down before their first run, and every interval is now 95%
familywise across all six rules.

Cards are counted the way the engine counts them: removal and fixing by the
app's Scryfall tags, plus multicolored lands for fixing, and heavy drops and
2-drops by `get_functional_cmc()`. The engine's thresholds are for pools of up
to 45 cards; they are applied to decks unchanged. Off-color spells are the ones whose cost the deck's two
main colors can't pay. In a deck with 3+ main colors, the two with the most
pips count as main.

The model is fit.py's logistic regression: card quality, the app's other deck
features, the set, and the player's buckets. `missing_fixing` is left out of
the fixing model, because it measures the same shortfall. Removal and heavy
drops each get a slope and a change of slope at the rule's threshold. Fixing
gets a slope overall, a slope in decks with off-color spells, the off-color
count, and the shortfall `off-color + 1 - fixing` while it's positive.
Creatures and 2-drops each get a slope and a change of slope below the rule's
threshold; removal for Needs Removal gets both of its thresholds (below 3 and
past 6).

Decided before the first run:

- **Primary result:** the effect per card, in game win rate points, with a
  99.17% interval (95% familywise across the six rules). The SE is the
  larger of the model's, widened for overdispersion, and the set-clustered
  sandwich.
- **Verdict:** *supported* if the interval excludes zero in the rule's
  direction, *contradicted* if it excludes zero the other way, otherwise *not
  established*. This is not evidence of equivalence.
- **Size:** the effect is also shown in rating SDs: the change in the card's
  GIH WR, in the format's SDs, that would move card quality as much. That
  makes it comparable with the rule's own size, its multiplier on the
  engine's score scale (removal and heavy drops taken at +1 SD, cards a rule
  boosts at the mean; Needs 2-Drops at the average multiplier of the decks
  short of 2-drops).
- **Keep or drop:** with the rule a card is valued at the rule's size off its
  rating, without it at zero. *Drop* if the whole interval in rating SDs is
  on zero's side of half the rule's size, so the card is valued better
  without the rule. *Keep* if it is all on the rule's side. Otherwise *can't
  tell*. This is the answer to "does the rule cost strength". It weighs how
  wrong a card's value is, not how often the rule changes a pick.
- **Deck score terms:** the deck score's other terms (`two_colors`,
  `domain_supported`, `missing_fixing`) from one fit of every set without any
  rule terms, in score points with the same interval, read the same way
  against the app's weights.
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

Not covered: the rest of the one-factor ablations in the fork's
`exp/ablation-results-20261103`.

- The three synergy rules: no snapshot has `synergy_*` tags.
- Enables Bomb Splash and Premium Fixing: they value a fixing card against
  its own rating, and lands' ratings aren't in card quality.
- Relative power, the IWD premium, the lane boost, archetype weighting,
  shrinkage and castability: these shape the order of picks, not something
  a finished deck has. Archetype weighting, shrinkage and the IWD premium
  are tested as ratings below.
- The deck builder's Monte Carlo penalties: tested below on draw luck.

Actions → Rule targets → Run workflow runs it on every set with Premier Draft
game data and Premier Draft ratings: 20 sets. MID, STX and VOW are left out
because their dumps have no `draft_id` or `build_index` to group games into
decks.

Locally, after the steps above:

```sh
poetry run python Tools/DeckScoreFit/rules.py results/*.json --json rules.json
```

Tests: `poetry run pytest Tools/DeckScoreFit/tests`.

## Mana luck and the deck builder's penalties

`mana.py` tests the deck builder's three Monte Carlo penalties
(`suggest_deck()` in `src/advisor/deck_builder.py`). The builder simulates
each candidate deck 10,000 times with `simulate_deck()` and takes points off
its score for each point of a rate above a threshold:

| penalty | rate (`simulate_deck()`) | threshold | points per rate point | ablation |
|---|---|---|---|---|
| Color Screw | `color_screw_t3`: 3+ lands and a 3-drop by turn 3, but no 3-drop castable | 10% | 2.5 | `no-mc-color` |
| Mana Screw | `screw_t3`: fewer than 3 lands by turn 3 | 22% | 1.5 | `no-mc-screw` |
| Flood Risk | `flood_t5`: 6+ lands by turn 5 | 27% | 1.5 | `no-mc-flood` |

(`no-mc-all` drops all three.) The simulator draws a random 7, mulligans 0-1
or 6-7 land hands, and counts turns on the play: by turn 3 it has seen 9
cards, by turn 5 11.

17Lands records each game's opening hand. For a 7-card keep, the rest of
the library is in random order, so given the hand, the chance of each event
is known: exactly for screw and flood (from the lands left in the library),
and from 1,000 shuffles of the library through the simulator's own castability
code for color screw. Two hands of the same deck differ only by luck, so
within a deck, win rate against these chances measures what each event
costs. Draws during the game aren't used: how many cards a player draws
depends on how long the game lasts, so on whether it was won.

`hands.py` computes, per sampled deck, `simulate_deck()`'s rates and, per
game, the kept hand's lands and the three chances. Decks that aren't exactly
40 cards are skipped (the simulator takes the first 40). A set whose dump records
mulligans in under 2% of games is left out: DMU's records them in 0.15%,
with 6-card hands, so its mulligans pass as 7-card keeps.

Decided before the first run:

- **Cost of each event:** a linear probability model of each 7-card keep's
  result on its three chances and being on the play, with a deck fixed
  effect, in win rate points. The SE is the larger of the deck-clustered
  and the set-clustered sandwich.
- **Calibration:** the slope, across decks, of the real chance of each event
  in the deck's 7-card keeps on `simulate_deck()`'s rate for the deck (with
  set effects, weighted by keeps). Arena smooths Bo1 opening hands and
  players choose what to keep, so real keeps needn't match the simulator's.
  Also reported: kept hands' land counts against random hands, the mulligan
  rate against the simulator's, and each event's real rate in keeps against
  the simulator's rate in its own 7-card keeps.
- **Primary result:** what a point of `simulate_deck()`'s rate costs, in deck
  score points: the event's cost times the calibration slope times the share
  of games that are 7-card keeps, turned into log-odds at the average win
  rate and divided by card quality's log-odds per score point (from fit.py's
  deck-level model on the same decks). SEs by the delta method, taking the
  three parts as independent.
- **Keep or drop:** as for the pick rules, against the penalty's points per
  rate point above its threshold, with 98.75% intervals (95% familywise
  across the three penalties and all three together). For all three
  together (`no-mc-all`), the size is the average penalty of the decks with
  any penalty, and the value is what their rates above the thresholds cost
  by the primary result.
- **Also reported** but not used for the verdict: win rate by lands in a
  7-card keep against 3 lands, within decks; and a deck-level fit, like the
  rule tests', of games won on the three rates past their thresholds, in
  score points.

Limits:

- Keeps are chosen. A 2-land hand that a player kept probably had cheap
  spells; hands they mulliganed aren't seen. That likely makes screw look
  cheaper than it is in a hand the simulator keeps.
- The cost per point of rate is assumed the same at every rate; the penalty
  only starts past its threshold. If the data say rates below the threshold
  cost wins too, that is reported, not used for the verdict.

## Which rating predicts results

`horse.py` tests three things the engine does to a card's rating before
anything else in a pick (`_calculate_weighted_score()` and STEP 2 of
`evaluate_pack()` in `src/advisor/engine.py`):

- **Archetype weighting** (`no-archetype`): the card's win rate in the lane's
  pair is blended in with weight 0.6 + 0.7 x pick / 15.
- **Shrinkage** (`no-shrinkage`): the pair's win rate is first shrunk toward
  the overall one by `min(1, samples / 1000)`.
- **The IWD premium** (`no-iwd`): the bonus for a card well above the pack
  (`power_bonus`, 10 points per SD above the pack's mean, from 0.5 SD) is
  1.15x for a card more than 1 SD above with IWD over 4.5.

Each version of the rating gives a deck a quality: the average, over its
spells, of the card's value on the engine's scale (50 at the format mean,
15 points per SD) plus its power bonus, taking the format's mean and SD for
the pack's. The archetype is the deck's main colors, and the blend weight is
0.95, its average over a pack's 14 picks. A version is better if its deck
quality predicts held-out decks' results better.

17Lands' ratings come from the same games, which would favor whatever
fits them most closely: pair win rates from few games most of all. So
`games.py` computes the win rates again, cross-fitted: every deck in the
dump falls in one of five folds by a hash of its ID, and a sampled deck is
rated from the games of the other four: GIH WR (opening hand or drawn), IWD
(GIH WR less the win rate when not drawn), overall and per main colors. So
no deck's results are in its own ratings, and every set's ratings come from
four fifths of its dump, however much of it the sample is. A card's overall
rating needs 200 such games, a pair rating 10 (the engine's own minimum);
shrinkage counts games in hand in every fold, which needs no results.
`quality.py` computes each version's deck quality.

Decided before the first run:

- **Model:** fit.py's logistic regression with card quality replaced by each
  version, fit on four fifths of the decks (by a hash of the ID) and
  scored on the other fifth, five times.
- **Primary result:** the engine's version against each ablation, in
  held-out log loss per game, with 98.33% intervals (95% familywise across
  the three) from the per-deck differences. Also given as a share of what
  card quality is worth: the log loss without any card quality less the
  engine's version.
- **Verdict:** *keep* if the engine's version predicts better (the interval
  excludes zero), *drop* if the ablation does. *No difference* if the whole
  interval is within 2% of what card quality is worth. Otherwise *can't
  tell*.
- **Also reported:** blend weights 0.65 and 1.3, no power bonus, overall GIH
  WR alone, the deck score's own blend (0.7 pair, 0.3 overall, no
  shrinkage), and each comparison per set.

Limits:

- It tests what a rating says about a finished deck, not the pick it makes:
  a better predictor of results is better information to pick by, but how
  much that changes picks isn't measured.
- The blend weight changes during the draft; one average weight stands for
  it.

Actions → Mana and ratings → Run workflow runs both on the 20 sets.

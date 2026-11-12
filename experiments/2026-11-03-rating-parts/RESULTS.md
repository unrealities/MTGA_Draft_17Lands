# Which card rating predicts results: results

Run [42515119509](https://github.com/JamesYouL2/MTGA_Draft_17Lands/actions/runs/42515119509)
at `39a1a78` (`4fdc259` plus a push trigger): 716,435 two-main-color decks and
3.29M games from all 20 sets with Premier Draft game data and Premier Draft
ratings. The protocol is in [PROTOCOL.md](PROTOCOL.md), written before this run.
The full report is [horse.md](horse.md) and the numbers are in
[horse.json](horse.json).

## Verdicts

Gain is the engine's version against the ablation, in held-out log loss per
game. Positive means the engine's version predicts better. It's also given as a
share of what card quality is worth: 1.63 [1.56, 1.70] millinats a game, measured
against no card quality at all. Intervals are 98.33%, which is 95% familywise
across the three comparisons.

| what the engine does | ablation | gain (millinats a game) | share of card quality's worth | verdict |
|---|---|---|---|---|
| Archetype weighting | `no-archetype` | −0.439 [−0.473, −0.404] | −26.9% [−29.1%, −24.8%] | **ablation predicts better** |
| Shrinkage | `no-shrinkage` | +0.017 [+0.008, +0.025] | +1.0% [+0.5%, +1.6%] | engine's predicts better |
| IWD premium | `no-iwd` | +0.033 [+0.031, +0.034] | +2.0% [+1.9%, +2.1%] | engine's predicts better |

The verdict rule looks at zero first. So shrinkage and the IWD premium get
"predicts better" even though their gains are small: shrinkage's whole interval
is below the protocol's 2% margin, and the IWD premium's sits on it.

## What else the data says

These readings are not verdicts.

- **Archetype weighting makes a deck's rating predict worse.** At the engine's
  average weight of 0.95, blending in the card's win rate in the deck's pair
  loses about a quarter of what card quality is worth.
  - **By set:** 16 of 20 sets agree, 15 of them by more than two SEs. SOS leans
    the same way, and DMU is level. PIO and TDM read the other way by more than
    two SEs, and so does the Cube, on only 131 decks.
  - **By weight:** less is better. Weight 0.65, the engine's at pick 1, beats
    0.95 by 10.6% of card quality's worth, and 0.95 beats 1.3 by 11.3%.
  - **Pair strength:** the model has no color-pair terms, so a pair's own
    strength was free to help the archetype version, and it still loses.
- **The power bonus helps:** +18.1% of card quality's worth. That's why the two
  overall-rating versions differ: the overall GIH WR with no blend and no bonus
  still beats the engine's version by 15.8%, and `no-archetype`, which keeps the
  bonus, beats it by 26.9%.
- **Shrinkage barely matters here.** 14 of 20 sets lean its way, 7 by more than
  two SEs. BLB and MH3 read the other way by more than two SEs.
- **The IWD premium is small but consistent.** 19 of 20 sets lean its way, 18 by
  more than two SEs. PIO is the exception.
- **The deck score's blend** in `get_card_rating()` (0.7 pair, 0.3 overall,
  unshrunk) is worse than the engine's version, by 9.1%.

Other versions, not used for a verdict:

| version | gain of the engine's version (millinats a game) | share of card quality's worth |
|---|---|---|
| blend weight 0.65 | −0.173 [−0.182, −0.165] | −10.6% |
| blend weight 1.3 | +0.185 [+0.176, +0.193] | +11.3% |
| no power bonus | +0.294 [+0.282, +0.307] | +18.1% |
| overall GIH WR alone (no blend, no bonus) | −0.257 [−0.291, −0.223] | −15.8% |
| the deck score's blend | +0.149 [+0.136, +0.162] | +9.1% |

## What the fixes changed

The closed #244 reported these comparisons without the protocol's fixes: results
kept out of every split's ratings, two-color decks only, and SEs by draft. Those
earlier numbers aren't evidence, but a reviewer who saw them may want to know
what moved:

| comparison | #244 | this run |
|---|---|---|
| Archetype weighting | −26.7% | −26.9% |
| Shrinkage | +8.6% | +1.0% |
| IWD premium | +2.1% | +2.0% |
| No power bonus | +19.7% | +18.1% |
| The deck score's blend | +16.2% | +9.1% |

So the fixes didn't change the archetype result, and they removed most of
shrinkage's apparent value. This run changed several things at once, so it can't
say which fix did which.

## Limits

These are the protocol's limits, plus those found in the run:

- **It tests whole decks, not pick order.** Within a pack a pair's overall level
  cancels out, and what matters is whether pair win rates order the cards better.
  So this result shows the blended rating is a worse measure of a deck. It can't
  justify changing pick order without a replay of picks.
- The archetype is the deck's final pair, the best case. During a draft the
  engine has to guess the lane.
- One average weight stands for a blend weight that changes during the draft.
- Training decks are rated from three fifths of the dump and test decks from four
  fifths, and the app has all of it. Noisier ratings favor shrinkage and overall
  win rates, so pair win rates may do better on the full dump than here.
- Only two-color decks are tested, 78% of the 914,784 decks in the rule tests. A
  set with many three-color decks has fewer here: TDM has 10,479 decks.
- Sets disagree. The intervals are from per-draft differences and don't widen for
  that, unlike the rule tests' set-clustered SEs. The Cube's card quality
  doesn't predict at all on its 131 decks (−0.66 millinats a game).
- The versions and the verdict rule were fixed before this run, but #244's results
  were seen before they were.

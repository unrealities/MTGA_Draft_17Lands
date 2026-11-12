# Why the whole-deck test and the replay disagree: results

Run [42551931889](https://github.com/JamesYouL2/MTGA_Draft_17Lands/actions/runs/42551931889)
at `6e48023` (`bd87f25` plus a push trigger): 716,435 two-main-color decks and
3.29M games from all 20 sets, the same decks as the rating test's rerun. The
protocol is in [PROTOCOL.md](PROTOCOL.md), written before this run. The full report
is [parts.md](parts.md) and the numbers are in [parts.json](parts.json).

## Verdict

**The pair's level explains it.** By the protocol's rule, fit's weight with
color-pair-by-set terms is above zero, +1.29 [+1.20, +1.39], and fit only beats the
overall rating in held-out log loss, +0.346 millinats a game [+0.328, +0.363], or
21% of card quality's worth.

The whole-deck objection is to how good the pair is, not to how well a card fits
it. Among decks of the same pair, the blend predicts better than the overall rating:

| rating, against the overall rating | no pair terms | with pair terms |
|---|---|---|
| the engine's rating | -0.448 [-0.477, -0.419] | +0.456 [+0.433, +0.479] |
| fit only (0.95 x fit) | +0.346 [+0.328, +0.363] | +0.464 [+0.440, +0.487] |
| level only (0.95 x level) | -0.661 [-0.688, -0.633] | – |

The -0.448 is the rating test's 27.6% loss. Only the level is needed to produce it:
level alone does worse than the whole blend.

## The prediction failed

The protocol predicted level's weight would be well below fit's and near a third.
It is well below, but it is **-0.23 [-0.38, -0.08]**, not +0.33. By set, on model
SEs, 13 of 19 are below zero by more than two SEs, 4 are within two SEs of zero, and
DMU (+0.33) and TDM (+0.76) are above it. A negative weight doesn't mean a pair's
strength hurts its decks.

### Why it's negative

This wasn't in the protocol. It was looked at after the result, on 186 pair-by-set
means with only the set controlled ([between_pairs.py](between_pairs.py), from
[pair_means.json](pair_means.json)), so treat it as an explanation to test.

The ratio the prediction rested on holds: between pairs, a point of level goes with
+1.08 (SE 0.08) win rate points. What the prediction missed is that the overall
rating moves with the pair too, correlation 0.69. Cards in a strong pair have high
overall rates because they are mostly played in it. So the one slope misprices the
overall rating between pairs as well:

| a rating point, between pairs | win rate points |
|---|---|
| what the deck score's slope prices it at | 2.9 |
| the overall rating | +1.30 (SE 0.09) |
| the overall rating plus 0.7 x level, about the deck score's blend | +0.95 |

Level then acts as a correction. With overall's slope held near 2.9, it has to pull
down the excess overall carries between pairs. That arithmetic gives a weight of
-0.17, against -0.23 measured.

## Reported, not deciding

- **Fit is worth at least what the engine gives it.** In all 19 counted sets its
  weight is from +1.08 to +1.81. Free slopes add little in log loss, though: +0.492
  against +0.464, so this isn't a case for raising the weight.
- **Noise holds fit down.** Its weight is +0.95 [+0.84, +1.06] for cards under 3,000
  games in the pair and +1.49 [+1.34, +1.63] from 3,000.
- **Skill doesn't change it.** +1.26 [+1.14, +1.38] for strong drafters, +1.31
  [+1.22, +1.41] for the rest.

## What this changes

- **The whole-deck test's "less weight is better" was the level.** Its case for flat
  0.65 goes with it. The replay already scored flat 0.65 as worse, +0.0019 (SE
  0.0008), so both tests now say not to lower the weight.
- **Within a pack the reading stands, with a gap.** Level cancels among cards rated
  in the pair, which is why the replay isn't troubled by it. It doesn't cancel
  against cards with no pair rate, so some of the replay's +0.0063 could still be
  level moving on-lane cards past off-lane ones. Only a replay can separate that.
- **Where level doesn't cancel is the deck score.** `suggest_deck()` ranks builds of
  different pairs by a card quality that uses the blend. Between pairs that prices
  rating at about three times what it delivers. This test didn't measure how often
  that changes the suggested deck.

## What it can't show

As the protocol says: it values cards in finished decks, using each deck's final
pair, and it's observational. Pair terms remove what a pair's drafters share, not
what else may set apart decks with well-fitting cards.

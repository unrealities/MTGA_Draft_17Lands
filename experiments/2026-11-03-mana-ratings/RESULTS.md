# Mana luck and the card rating: results

Run [41752671721](https://github.com/JamesYouL2/MTGA_Draft_17Lands/actions/runs/41752671721)
at `067c22f` (`269f8df` plus a push trigger), on the same decks as the rule
tests: 914,784 registered decks and 4.14M games from all 20 sets with
Premier Draft game data and Premier Draft ratings, up to 50,000 decks a set.

The protocols are in [Tools/DeckScoreFit/README.md](../../Tools/DeckScoreFit/README.md#mana-luck-and-the-deck-builders-penalties).
Both were written down before the first run. The full reports are
[mana.md](mana.md) and [horse.md](horse.md), and the numbers are in
[mana.json](mana.json) and [horse.json](horse.json).

The first run,
[41745035079](https://github.com/JamesYouL2/MTGA_Draft_17Lands/actions/runs/41745035079),
showed two problems in the data, and both were fixed before this run:

- **Ratings.** The first run rated decks only from games played by decks
  outside the sample. TMT's whole dump is under 50,000 decks, so it was
  left with no ratings at all. PIO, FRA, HOB and MSH were left with a
  fraction of theirs, and noisy ratings favor shrinkage. Ratings are now
  cross-fitted: each deck is rated from the four fifths of its set's dump
  that it isn't in.
- **DMU.** DMU's dump records a mulligan in only 0.14% of games, against
  10–13% in every other set, so its mulligans pass as 7-card keeps. The
  mana test now leaves out any dump that records mulligans in under 2% of
  games, which here is only DMU. Its mana estimates in the first run were
  in line with the other sets.

## The deck builder's mana penalties

`suggest_deck()` charges a build so many score points per point of
`simulate_deck()`'s rate past a threshold. The value column below is what a
point of that rate actually costs, in the same score points. It comes from
three measurements:

- what the event costs in the game it happens in, measured within decks;
- how far a point of the simulator's rate moves the real chance of the
  event in kept hands;
- what card quality is worth per score point.

The data cover 798,355 decks and 3.24M 7-card keeps from 19 sets. The
intervals are 98.75%, which is 95% familywise across the four readings.

| penalty | event's cost (win rate points) | value (score points per point of rate) | penalty | decks past its threshold | keep or drop |
|---|---|---|---|---|---|
| Color Screw (`no-mc-color`) | −14.1 [−16.3, −11.9] | −0.17 [−0.20, −0.14] | −2.5 past 10% | 47,816 | **drop** |
| Mana Screw (`no-mc-screw`) | −19.2 [−22.0, −16.3] | −0.37 [−0.45, −0.30] | −1.5 past 22% | 531 | **drop** |
| Flood Risk (`no-mc-flood`) | −13.2 [−14.5, −11.9] | −0.19 [−0.22, −0.16] | −1.5 past 27% | 609,650 | **drop** |
| All three (`no-mc-all`) | | −0.38 [−0.44, −0.33] for the average deck's rates past the thresholds | −3.37 on average | 617,424 | **drop** |

The events are real and costly: a kept hand that ends up screwed by turn 3
loses about 19 points of win rate. But the penalties are 4 to 15 times what
the rates are worth.

- **Size.** Flood's penalty is 8 times its value and color screw's 15
  times. Across the decks with any penalty, the penalties take 3.4 points
  on average, while their rates past the thresholds cost about 0.4.
- **What "drop" means.** It means no penalty at all is closer to the data
  than these penalties are. It does not mean mana luck doesn't matter. The
  data support a penalty of about 0.2 points per point of color screw or
  flood and about 0.4 per point of screw.
- **Flood's threshold.** Flood's 27% threshold sits at the simulator's
  average rate (27.2%), so three quarters of all decks (76%) pay it.
- **Screw's threshold.** Screw's 22% threshold is reached by only 531
  decks, so that penalty almost never applies.
- **Deck-level check.** A deck-level fit, regressing games won on each rate
  past its threshold, agrees. It is not used for the verdict. It finds
  −0.32 [−0.52, −0.13] for color screw and −0.34 [−0.61, −0.07] for flood.
  That is about twice the within-deck values, but still a quarter of the
  penalties or less.

The value is worked out per point of rate. Rates below a threshold cost wins
too; a smaller penalty could start from zero rather than from a threshold.

### What the simulator gets wrong

| | real (in 7-card keeps) | simulator's own keeps | `simulate_deck()` |
|---|---|---|---|
| mulligans | 11.3% | | 12.8% |
| screw by turn 3 | 7.1% | 8.6% | 10.0% |
| flood by turn 5 | 21.3% | 28.3% | 27.2% |
| color screw by turn 3 | 3.6% | 4.1% | 4.2% |

- **Hand smoothing.** Arena's Bo1 hand smoothing makes 3-land keeps 57.5%
  of keeps, against 32.2% for random 7s. That alone makes real flood and
  screw rarer than the simulator says.
- **Calibration.** Across decks, a point of the simulator's color-screw rate
  is a point of real chance (slope 1.00). For screw it is 1.62 and for flood
  1.18. So the simulator overstates the level of screw and flood but
  understates how much decks differ in them.
- **Within decks,** keeps with 2 or 4 lands win about 4 points less than
  3-landers, and keeps with 5 lands about 12 points less.
- **By set,** each event costs wins in every set but the Cube, which has
  only 1,040 keeps. Screw costs from −11 (LTR) to −27 (DFT), flood from −9
  to −17, and color screw from −7 (MH3) to −19.

## Which rating predicts results

Each version of the engine's card rating gives a deck a quality: the average
of its spells' values. Each version was then compared on how well it
predicts held-out decks' results, using 914,784 decks from 20 sets. The
gain is the engine's version against the ablation, in held-out log loss
per game.
Positive means the engine's version predicts better. It is also given as a
share of what card quality is worth: 1.63 [1.57, 1.69] millinats a game,
measured against no card quality at all. The intervals are 98.33%, which is
95% familywise across the three comparisons.

| what the engine does | gain (millinats a game) | share of card quality's worth | verdict |
|---|---|---|---|
| Archetype weighting (`no-archetype`) | −0.434 [−0.472, −0.397] | −26.7% [−29.0%, −24.4%] | **drop** |
| Shrinkage (`no-shrinkage`) | +0.140 [+0.122, +0.158] | +8.6% [+7.5%, +9.7%] | **keep** |
| IWD premium (`no-iwd`) | +0.034 [+0.033, +0.036] | +2.1% [+2.0%, +2.2%] | **keep** (barely matters) |

**Archetype weighting makes the rating worse.**

- **The result.** Blending in the card's win rate in the deck's color pair
  at the engine's average weight (0.95) predicts results worse than the
  overall GIH WR alone. The loss is about a quarter of everything card
  quality adds.
- **Weight.** The less weight, the better. At 0.65 (the engine's pick-1
  weight) the rating predicts better than at 0.95. At 1.3 (its weight from
  pick 15) it predicts worse.
- **By set.** 18 of the 20 sets agree. The exceptions are PIO and the Cube,
  and the Cube rates only 240 decks.
- **Pair strength.** The model has no color-pair terms, so a pair's own
  strength was free to help the archetype version, and it still loses.
  Pair win rates, even shrunk, carry more noise and selection than signal
  about how good the card is.

Two caveats limit what this says about picks:

- **Lane.** The archetype here is the deck's final main colors, the best
  case. During a draft the engine has to guess the lane.
- **Within a pack.** The test ranks whole decks. Within a pack the pair's
  overall level cancels out, and what matters is whether pair win rates
  order the cards better. It shows that the blended rating is a worse
  measure of card strength. It doesn't directly test the pick-order
  effect.

**Shrinkage helps.** It is worth +8.6% of card quality. It helps in 16 of 20 sets;
in LTR, MH3, TDM and the Cube it makes no clear difference.
Since the archetype blend hurts anyway, shrinkage mainly limits the damage.

**The IWD premium** comes out "keep" because its interval excludes zero.
But it is worth 2.1% of card quality, right at the 2% "no difference"
margin. It is harmless and nearly irrelevant.

Other versions, not used for a verdict:

| version | gain of the engine's version | share of card quality's worth |
|---|---|---|
| blend weight 0.65 | −0.203 [−0.213, −0.194] | −12.5% |
| blend weight 1.3 | +0.214 [+0.206, +0.223] | +13.2% |
| no power bonus | +0.321 [+0.309, +0.333] | +19.7% |
| overall GIH WR alone (no blend, no bonus) | −0.257 [−0.294, −0.220] | −15.8% |
| the deck score's blend (0.7 pair, 0.3 overall, no shrinkage) | +0.264 [+0.244, +0.284] | +16.2% |

- **The power bonus** helps a lot: +19.7%. Even without it, the overall GIH
  WR alone beats the engine's blend.
- **The deck scorer's own blend** in `get_card_rating()` (0.7 pair, 0.3
  overall, unshrunk) is worse than the engine's. That makes it the weakest
  rating tested.

## What this suggests

These are suggestions, not part of the tests:

- **Mana penalties.** Cut them to about 0.2 points per point of color screw
  and flood and 0.4 per point of screw. Or drop them: at the right size,
  the average deck with any penalty would lose about 0.4 points.
- **Archetype weighting.** Cut it well below 0.6–1.3, or drop it from the
  card's value. A test of the pick-order effect, such as the replay
  harness, should come before removing it from pick ordering.
- **The deck scorer's blend.** Switch `get_card_rating()` to the overall
  GIH WR, or at least shrink its pair win rates.

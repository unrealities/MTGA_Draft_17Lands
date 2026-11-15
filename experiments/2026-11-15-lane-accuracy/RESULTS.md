# Lane accuracy: results

Protocol: `PROTOCOL.md`. Reports: `first_run.md` (eight sets), `second_run.md` (all
ten, after the amendment). Numbers below are the second run's: 29,632 drafts,
1,213,394 picks.

## The app's lane

It names a pair on 93.9% of picks, right on 82.0% and wrong on 12.0%: net +70.0.

| cards in pool | names a pair | right | wrong |
|---|---|---|---|
| 1-4 | 50.5% | 32.9% | 17.6% |
| 5-9 | 92.0% | 68.2% | 23.8% |
| 10-14 | 97.9% | 75.0% | 22.9% |
| 15-19 | 100.0% | 86.3% | 13.7% |
| 20-27 | 100.0% | 92.6% | 7.4% |
| 28+ | 100.0% | 95.8% | 4.2% |

The weak stretch is 5 to 14 cards, where almost every pick has a pair and nearly a
quarter are wrong. The lane has a third color on 41.7% of picks, and its pair changes
2.20 times a draft.

## The verdicts

| rule | net minus app (SE) | verdict |
|---|---|---|
| `no-recency` | -0.77 (0.08) | keep recency |
| `no-switch` | -3.22 (0.10) | keep the switch |
| `neither` | -3.43 (0.12) | keep both |
| `most-cards` | +3.52 (0.16) | beats the app: gets an advisor replay as a replacement |
| `column-order` | -1.25 (0.10), pair differs on 9.4% of picks | fix `replay.py` |

Every set agrees in sign on the switch, the count and the column order. Recency is
against the sign in one set of ten (FRA, +0.23).

- **Recency** does all its work under 10 cards (-2.25 at 1 to 4, -3.90 at 5 to 9
  without it), mostly by naming a pair sooner: 93.9% of picks against 90.5%. From 10
  cards on, it is within 0.5 points either way. It also costs stability: the pair
  changes 2.20 times a draft with it and 1.28 without.
- **The switch** is worth 4.5 to 5.7 points at every size from 15 cards. Without it the
  lane has a third color on 74.9% of picks.
- **The count** (the two colors with the most nonland cards) beats the app at every
  pool size, by 4.0 to 5.7 points under 10 cards, 10.3 at 10 to 14, and 1.7 to 1.9 from
  15 on. It is one line against the app's forty, and its pair changes 1.53 times a
  draft. It never names a third color, so a replacement needs a rule for that.
- **Column order** changes the lane's pair on 9.4% of picks, over the 5% line. The fix
  is on `fix/replay-pool-order`. Earlier replay results that turn on the lane (on-lane,
  the archetype weight, off-color castability) were measured with a lane 1.25 points
  less accurate than the app's, and are approximate to that extent.

## The predictions

| | predicted | found |
|---|---|---|
| 1 | a pair on 90%+ of picks from 5 cards; right on 55% of all picks; 80%+ from 28 | 92.0%; 82.0%; 95.8%. The lane is much better than I thought |
| 2 | `no-recency` lower by 2+ SEs, under 1 point | -0.77 at 9 SEs: right |
| 3 | `no-switch` within 2 SEs | -3.22 at 32 SEs: wrong |
| 4 | `column-order` differs on 5% to 15% | 9.4%: right |
| 5 | `most-cards` below the app under 15 cards, level after | above it everywhere: wrong |

## What follows

1. `fix/replay-pool-order`, its own pull request.
2. An advisor replay of a lane by count against main, on the fixed harness. Open
   choices: whether a third color is ever named, and whether the count starts at the
   first card or waits for a few.

## Notes on the runs

- The second run's report job failed on seven TMT picks whose pools had no card in the
  dataset. The report now skips them, and `second_run.md` was built from that run's
  artifacts with the fixed script.
- Its "Left out" line lists 12 picks where two cards joined the pool at once. They are
  counted, with the order of those two guessed.
- The eight sets in both runs moved by under 0.1 between them, from the few picks the
  first run skipped and two more drafts.

## What it can't show

As the protocol says: played colors aren't the best colors; these drafters weren't
steered by the lane; and every pick counts alike.

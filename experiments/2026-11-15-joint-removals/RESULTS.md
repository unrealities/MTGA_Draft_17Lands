# The removals together: results

Protocol: `PROTOCOL.md`. Report: `report.md` (30,000 drafts, 22,661 complete events).
A first dispatch failed at checkout, because the workflow's `base` needs a full commit
ID; nothing ran.

## The verdict

The removals stand together. None of the three measures is worse, and two are better.

| measure | before #255 | main | main minus before (SE) |
|---|---|---|---|
| top-1 agreement with drafters | 47.2% | 47.7% | **+0.5** (under 0.05) |
| regret slope (more negative is better) | -0.265 | -0.267 | -0.002 (0.002) |
| deck score slope (more positive is better) | +0.330 | +0.366 | **+0.037** (0.007) |

Top-1 is higher in all ten sets, by 0.2 to 0.8 points. Among strong drafters the gain
is in pack 3 (51.4% to 53.0%); pack 1 is 0.3 points lower.

## The predictions

| | predicted | found |
|---|---|---|
| 1 | top-1 within 0.3 points | +0.5: wrong, it's better |
| 2 | regret slope within 2 SEs | 1 SE: right |
| 3 | deck score slope better by 2+ SEs | 5 SEs: right |

## What it can't show

As the protocol says: it doesn't see which deck the app lists first, and ratings include
the replayed drafts. Both sides also got their pools in the dump's order, not pick
order (`experiments/2026-11-15-lane-accuracy`, on `exp/lane-accuracy`), so both ran
with a lane slightly less accurate than the app's.

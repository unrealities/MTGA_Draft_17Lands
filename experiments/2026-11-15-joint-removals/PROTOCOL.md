# The removals of #255 to #267, replayed together

Written before the run. A 150-draft FRA smoke test was seen first, only to check that
today's harness runs on the old code.

## Why

Ten pull requests took rules out of the advisor and the deck score between 2026-11-09
and 2026-11-13: dead constants (#255), Synergy (#256), Premium Fixing (#257), Enables
Bomb Splash (#258), shrinkage (#259), the simulator's mana penalties (#263), the deck
score's blend of ratings (#264), Curve Too Heavy (#265), Removal Saturated (#266) and
the domain bonus (#267). Each was tested alone, against the app as it was that day.
Nothing was tested together.

## What runs

The Advisor replay workflow, unchanged, on its ten sets at 3,000 drafts a set:

- **base:** `b74d7ca`, the merge before #255;
- **head:** upstream main at `6b6dba9`, plus this file;
- **salt:** `joint-2026-11-15`, which none of the single tests used.

Between the two, `src/` also changed in `ui/windows/download.py` (#261, #262). The
replay doesn't import it.

## The measures

The report's three head-minus-base differences, each with its paired bootstrap SE:

1. top-1 agreement with drafters' picks;
2. the regret slope (event wins per +1 SD of regret; more negative is better);
3. the deck score slope (event wins per +1 SD of the final pool's score; more positive
   is better).

## The decision rule

| | verdict |
|---|---|
| none of the three is worse by 2+ SEs | the removals stand together |
| one is worse by 2+ SEs | replay the merges in between to find which removal, then decide on that one |

A second run with another salt only if a difference lands between 1.5 and 2.5 SEs
against the head.

## The predictions

1. Top-1 within 0.3 points either way.
2. The regret slope within 2 SEs of no change.
3. The deck score slope better by 2+ SEs, from #264.

## What it can't show

The deck score here is the best of the quick builds, so it doesn't see which deck the
app lists first, which is what #263 changed most. Ratings include the replayed drafts.

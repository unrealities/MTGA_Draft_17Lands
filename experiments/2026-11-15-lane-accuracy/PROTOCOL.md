# How well the advisor's lane predicts the colors a drafter plays

Written before any report was read. A 150-draft FRA smoke test ran first to check the
tool; from it I saw one draft's lanes pick by pick and the mix of played colors, and no
rates.

## Why

`DraftAdvisor._identify_main_colors` names the pool's lane. The lane picks the pair
whose win rates the archetype weight blends in, gives on-lane cards their 1.1x, and
decides which cards count as off-color for castability and for Needs Fixing. Every one
of those rules inherits the lane's mistakes, and the lane has never been measured.

It has two parts that could go:

- **Recency:** a card's weight grows with its place in the pool, up to three times for
  the latest pick.
- **The 15-card switch:** under 15 cards a color is in the lane if its weight is 2.5 or
  more. From 15 on, it is in if it is one of the two most common colors or has 15% of
  the pool's colored cards.

One thing came up while writing the tool. The 17Lands dump lists the pool by card, not
by pick, and `Tools/AdvisorReplay/replay.py` hands it to the advisor in that order. So
in every advisor replay so far, recency has weighted cards by their column in the dump.
This tool rebuilds the pool in pick order from one pick's pool to the next.

## What runs

The Lane accuracy workflow on the replay's ten sets, 3,000 drafts a set, salt `""`, on
upstream main at `6b6dba9` plus this branch's tools. For each draft, the played colors
are the main colors of the build with the most games in the 17Lands game data.

At every pick with a pool, each rule names a lane:

| rule | what changes |
|---|---|
| `app` | nothing. The run stops if it ever differs from `DraftAdvisor` |
| `no-recency` | every card counts the same wherever it is in the pool |
| `no-switch` | the weight rule at every pool size |
| `neither` | both |
| `column-order` | the app's rule on the pool in the dump's order, as the replay feeds it |
| `most-cards` | a yardstick: the two colors with the most nonland cards |

## The measures

A lane's pair is its first two colors, which is the archetype the advisor uses. At each
pick it is:

- **right** if the pair and the played main colors agree, one holding the other (a
  two-color lane inside a three-color deck is right);
- **wrong** if it names a pair that doesn't;
- **open** if it names fewer than two colors.

**Net** is right minus wrong, in points of picks. It prices a wrong lane the same as a
missed one. Each rule's net minus the app's has a paired bootstrap SE over drafts.

Also reported: how often each rule's pair differs from the app's, how many times a draft
the pair changes, how often the lane has a third color, and net by cards in the pool
and by set.

## The decision rules

For `no-recency`, `no-switch` and `neither`, each simpler than the app:

| | verdict |
|---|---|
| net falls by 2+ SEs | that part earns its place: keep |
| otherwise | a candidate to remove, pending an advisor replay against main |

Agreeing with what drafters played isn't the same as picking well, so no rule goes on
this alone. A candidate gets an advisor replay with pools in pick order, and the usual
replay rule decides.

`most-cards`: if its net beats the app's by 2+ SEs, it gets the same replay as a
replacement for the whole rule.

`column-order`: if its pair differs from the app's on 5% or more of picks, `replay.py`
is fixed to feed pools in pick order, in its own pull request, and earlier replay
results that turn on the lane are read as approximate.

## The predictions

1. The app names a pair on 90%+ of picks once the pool has 5 cards. It is right on about
   55% of all picks, net about +25, and right on 80%+ from 28 cards.
2. `no-recency` lowers net by 2+ SEs, by under 1 point.
3. `no-switch` is within 2 SEs of the app.
4. `column-order` differs from the app on 5% to 15% of picks.
5. `most-cards` is below the app under 15 cards and level with it after.

## What it can't show

Drafters' played colors aren't the best colors for their pool. Many of these drafters
used no advisor, so the lane didn't steer them; for a user who follows the app, a lane
partly makes itself true. And the measure treats every pick alike, though a wrong lane
at pick 5 costs less than one at pick 30.

## Amendment, after the first run

The first run left out TLA and TMT whole: their dumps have no row for the first pick, so
the tool's check of each pool against the cards taken so far failed at every pick. The
other eight sets lost no picks. The tool now takes the order from the pools themselves,
which needs no row for any pick, and the run is repeated on all ten sets. The first
run's report had been read by then; the rules, measures and predictions are unchanged.

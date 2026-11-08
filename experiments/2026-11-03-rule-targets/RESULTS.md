# Rule targets: results

Run [42514603136](https://github.com/JamesYouL2/MTGA_Draft_17Lands/actions/runs/42514603136)
at `3898b37`: 914,784 registered decks and 4.14M games from all 20 sets
with Premier Draft game data and Premier Draft ratings, up to 50,000 decks
a set. The protocol is in [PROTOCOL.md](PROTOCOL.md), including the amendments
for this second batch of rules. The full report is [rules.md](rules.md) and the
numbers are in [rules.json](rules.json).

The first three rules were written down before their first run. The second
batch wasn't: those rules were first run on these same decks in the closed #244
([run 41737611582](https://github.com/JamesYouL2/MTGA_Draft_17Lands/actions/runs/41737611582)),
so this run doesn't test them on unseen data.

Adding three rules widens every interval, from 98.33% to 99.17%. The first three
rules' sets and verdicts are unchanged, and their estimates moved by at most
0.001 points. The earlier run of those three was
[42394134901](https://github.com/unrealities/MTGA_Draft_17Lands/actions/runs/42394134901).

## Verdicts

The three rules that boost a card while the deck is short of it are supported.
The other three aren't established: their intervals include zero.

| rule | per card, win rate points (99.17%) | in rating SDs (99.17%) | the rule's size | verdict |
|---|---|---|---|---|
| Removal Saturated (0.8x past 6) | +0.09 [−0.05, +0.24] | +0.24 [−0.15, +0.62] | −0.87 | not established |
| Curve Too Heavy (0.7x past 4) | −0.09 [−0.28, +0.10] | −0.24 [−0.72, +0.25] | −1.30 | not established |
| Critical: Needs Fixing (1.4x) | −0.03 [−0.27, +0.20] | −0.08 [−0.68, +0.51] | +1.33 | not established |
| Critical: Needs Creatures (1.25x under 13) | +0.17 [+0.02, +0.32] | +0.42 [+0.04, +0.81] | +0.83 | **supported** |
| Critical: Needs Removal (1.3x under 3) | +0.29 [+0.01, +0.58] | +0.76 [−0.01, +1.53] | +1.00 | **supported** |
| Critical: Needs 2-Drops (up to 1.5x under 7) | +0.35 [+0.15, +0.55] | +0.91 [+0.38, +1.44] | +1.00 at two short | **supported** |

The verdict reads the win-rate interval. Needs Removal's interval in rating SDs
just includes zero because it also carries the uncertainty in what card quality
is worth, so that verdict is at the edge either way.

## What else the data says

These readings are not verdicts. They go beyond the pre-registered decision rule.

- **A verdict of "supported" doesn't show that being short is what matters.**
  It says the card beats a spell of the same rating while the deck is short. But
  creatures and removal beat such a spell about as much once the deck isn't
  short. No test of the difference was pre-registered, so these are just the two
  estimates side by side:

  | rule | while short | past the threshold |
  |---|---|---|
  | Needs Creatures | +0.17 (0.06) | +0.19 (0.04) from the 13th |
  | Needs Removal | +0.29 (0.11) | +0.22 (0.06) from the third to the sixth |
  | Needs 2-Drops | +0.35 (0.08) | +0.16 (0.06) from the 7th |

  Only 2-drops look worth more while short. Creatures show no such step.
- **How consistent the supported rules are:**
  - **Needs 2-Drops** is the strongest. 17 of 20 sets point its way, 12 of them
    by more than two SEs, and it holds with counts as controls (+0.30, SE 0.08)
    and for strong drafters (+0.30, SE 0.08). Win rate rises steadily with the
    count: −1.71 points at 3 or fewer and +0.84 at 10 or more, against decks
    with 7.
  - **Needs Creatures** has 17 of 20 sets its way, but it's weak among strong
    drafters (+0.08, SE 0.06). FRA reads the other way by more than two SEs.
  - **Needs Removal** has few decks in its region (38,874, or 4.3%). 16 of 19 sets
    point its way, but only MSH by more than two SEs.
- **The not-established rules are smaller than their multipliers.** Each
  interval in rating SDs excludes the rule's own size. At the edge of its
  interval, Curve Too Heavy reaches about half its size, Needs Fixing about 40%,
  and Removal Saturated about a fifth.
- **Removal leans against the saturation rule.** Removal past the sixth is, if
  anything, worth slightly more than a spell of the same rating:
  - +0.20 (SE 0.05) with land, creature and color counts as controls.
  - +0.11 (0.06) for strong drafters.
  - Win rate rises steadily with the removal count: −1.09 points at 2 or
    fewer and +0.46 at 10 or more, against decks with 6.
  - The slope does flatten past the sixth: −0.14 (0.06) on a slope of +0.23
    up to it. So extra removal helps less, but still doesn't help less than
    an average card.
  - Only 8 of 19 sets point the rule's way.
- **Heavy drops are flat** from 0 to 6 of them. Decks with 7 or more are
  −0.31 (0.24) against decks with 4. Sets split 11 of 19, and 9 sets differ
  from zero by more than two SEs, in opposite directions.
- **Fixing is worth about the same whether or not the deck is short:** +0.16
  (0.06) while short, +0.19 (0.06) once not short, and +0.15 (0.04) in decks with
  no off-color playables. Strong drafters alone read −0.13 (0.10). Sets split 12
  of 20, and five are more than two SEs from zero: three above (DMU, NEO, TMT)
  and two below (FIN, TLA).

## Limits

These are the protocol's limits, plus those found in the runs:

- The rules count pools, but these are registered decks. The analysis is
  observational, and it values cards relative to their ratings rather than
  measuring a change to the advisor.
- A deck short of creatures or cheap plays may differ in other ways. Skill
  buckets and the app's features are the only adjustment for why it's short,
  for instance a pool of expensive spells or a slower archetype.
- The engine projects a pool of up to 45 cards onto its targets, while a deck is
  23 spells chosen from it. These tests don't say whether the projection is the
  right trigger, or whether 13, 3 and 7 are the right thresholds.
- The engine gives a card only one bonus, in a fixed order. Here a deck short on
  several things counts for each.
- The fixing test counts the condition the 1.4x rule fires on, but not the
  rule's whole reach. Once hungry, the engine scores every land at 1.4x,
  basics included; this test values only the cards the hunger test itself
  counts as fixing, tagged cards and multicolor lands. A verdict on it says
  nothing about what boosting basics does. The rule's pack gate has no
  counterpart either: every registered deck is past pack 2.
- The set-clustered SEs are up to about 3× the model's (about the same for
  Needs Removal). Sets disagree, so the pooled per-card effects hide real
  set-to-set differences.
- Cube_-_Powered has no removal or fixing tags, so it is left out of both removal
  rules and adds only lands to fixing.
- TDM's omen and dragonstorm cards count at their full mana value as heavy
  drops. This follows the engine's `get_functional_cmc()`.

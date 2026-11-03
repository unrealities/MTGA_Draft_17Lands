# Rule targets: results

Run [41734489663](https://github.com/JamesYouL2/MTGA_Draft_17Lands/actions/runs/41734489663)
at `3d945ee`: 914,784 registered decks and 4.14M games from all 20 sets
with Premier Draft game data and Premier Draft ratings, up to 50,000 decks
a set. The protocol is in [Tools/DeckScoreFit/README.md](../../Tools/DeckScoreFit/README.md#testing-pick-rules-on-game-results),
written before the first run. The full report is [rules.md](rules.md) and the numbers are in [rules.json](rules.json).

## Verdicts

None of the three rules is established. Every interval includes zero.

| rule | per card, win rate points (98.33%) | in rating SDs (98.33%) | the rule's size | verdict |
|---|---|---|---|---|
| Removal Saturated (0.8x past 6) | +0.09 [−0.04, +0.23] | +0.24 [−0.11, +0.59] | −0.87 | not established |
| Curve Too Heavy (0.7x past 4) | −0.09 [−0.26, +0.08] | −0.24 [−0.67, +0.20] | −1.30 | not established |
| Critical: Needs Fixing (1.4x) | −0.04 [−0.31, +0.22] | −0.11 [−0.78, +0.56] | +1.33 | not established |

## What else the data says

These readings are not verdicts. They go beyond the pre-registered decision rule.

- **Each rule is several times larger than anything the data allows.** Every
  interval in rating SDs excludes the rule's own size. Even at the edge of
  its interval, the per-card effect is at most about half the size of the
  rule's multiplier. This holds for removal past the sixth, heavy drops past
  the fourth, and fixing while short.
- **Removal leans against its rule.** Removal past the sixth is, if anything,
  worth slightly more than a spell of the same rating:
  - +0.20 (SE 0.05) with land, creature and color counts as controls.
  - +0.11 (0.06) for strong drafters.
  - Win rate rises steadily with the removal count: −1.09 points at 2 or
    fewer and +0.46 at 10 or more, against decks with 6.
  - The slope does flatten past the sixth: −0.14 (0.06) on a slope of +0.23
    up to it. So extra removal helps less, but still doesn't help less than
    an average card.
  - Only 8 of 19 sets point the rule's way.
- **Heavy drops are flat** from 0 to 6 of them. Decks with 7 or more are
  −0.31 (0.24) against decks with 4. Sets split 11 of 19, and 7 sets differ
  from zero in opposite directions.
- **Fixing is worth about the same whether or not the deck is short:** +0.13
  (0.10) while short, +0.17 (0.05) once not short, and +0.18 (0.05) in decks
  with no off-color spells.

## Limits

These are the README's limits, plus two found in this run:

- The rules count pools, but these are registered decks. The analysis is
  observational, and it values cards relative to their ratings rather than
  measuring a change to the advisor.
- The set-clustered SEs are about 3× the model's. Sets disagree, so the
  pooled per-card effects hide real set-to-set differences.
- Cube_-_Powered has no removal or fixing tags, so it is left out of the
  removal rule and adds only lands to fixing.
- TDM's omen and dragonstorm cards count at their full mana value as heavy
  drops. This follows the engine's `get_functional_cmc()`.

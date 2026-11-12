# Testing pick rules on game results: protocol

`Tools/DeckScoreFit/rules.py` uses the decks that `fit.py` fits (see
[the tool's README](../../Tools/DeckScoreFit/README.md)) to test six of
the advisor's pick rules (in `_calculate_composition_bonus()` in
`src/advisor/engine.py`; three were added later, see Amendments). Each rule
reweights a card by what the pool already has. If the rule is right, that
condition should show up in registered decks: decks where it holds should win
more or less often than the average rating of their spells predicts.

| rule | multiplier | tested on decks | the rule is supported if |
|---|---|---|---|
| Removal Saturated | 0.8x for removal once the pool has 7+ | each removal spell past the sixth, against a spell of the same rating | it's worth less |
| Curve Too Heavy | 0.7x for 5+ mana spells once the pool has 4+ | each 5+ mana spell past the fourth, against a spell of the same rating | it's worth less |
| Critical: Needs Fixing | 1.4x for fixing from pack 2 while fixing ≤ off-color playables | in decks with off-color spells, a fixing card while fixing ≤ off-color spells, against one once fixing is more | it's worth more |

Cards are counted the way the engine counts them: removal and fixing by the
app's Scryfall tags, plus multicolored lands for fixing, and heavy drops by
`get_functional_cmc()`. Off-color spells are the ones whose cost the deck's two
main colors can't pay. In a deck with 3+ main colors, the two with the most
pips count as main. (Amended on 2026-11-07; see Amendments.)

The model is fit.py's logistic regression: card quality, the app's other deck
features, the set, and the player's buckets. `missing_fixing` is left out of
the fixing model, because it measures the same shortfall. Removal and heavy
drops each get a slope and a change of slope at the rule's threshold. Fixing
gets a slope overall, a slope in decks with off-color spells, the off-color
count, and the shortfall `off-color + 1 - fixing` while it's positive.

Decided before the first run:

- **Primary result:** the effect per card, in game win rate points, with a
  98.33% interval (95% familywise across the three rules). The SE is the
  larger of the model's, widened for overdispersion, and the set-clustered
  sandwich.
- **Verdict:** *supported* if the interval excludes zero in the rule's
  direction, *contradicted* if it excludes zero the other way, otherwise *not
  established*. This is not evidence of equivalence.
- **Size:** the effect is also shown in rating SDs: the change in the card's
  GIH WR, in the format's SDs, that would move card quality as much. That
  makes it comparable with the rule's own size, its multiplier on the
  engine's score scale (removal and heavy drops taken at +1 SD, fixing at the
  mean).
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

Actions → Rule targets → Run workflow runs it on every set with Premier Draft
game data and Premier Draft ratings: 20 sets. MID, STX and VOW are left out
because their dumps have no `draft_id` or `build_index` to group games into
decks.

Locally, after the README's steps for each set:

```sh
poetry run python Tools/DeckScoreFit/rules.py results/*.json --json rules.json
```

Tests: `poetry run pytest Tools/DeckScoreFit/tests`.

## Amendments

Made on 2026-11-07, after the first two runs and before the third, on review
of whether the fixing-hunger test measured the condition the engine fires on.

- **Off-color playables are counted as the engine counts them.** The first
  runs counted every spell with no face the deck's two main colors could pay.
  The engine's `off_color_playables` counts the cards with colors that
  `is_castable()` says its lane of up to three main colors can't cast (by the
  front face's cost), and only those rated above the format's mean less one
  SD. The count now uses `is_castable()`, the deck's registered main colors
  (the three with the most pips in a deck of 4+) and the same rating bar, so
  the shortfall term is the one the 1.4x rule fires on. Two parts of the rule
  still have no counterpart. The pack gate: every registered deck is past
  pack 2. And the boost's reach: once hungry, the engine scores every land at
  1.4x, basics included, while its hunger test and this analysis count only
  tagged fixing and multicolor lands as fixing.
- **The strong-drafter sensitivity needs decks in the region.** It is now
  reported only when the strong drafters' decks include at least `MIN_REGION`
  (100) in the rule's region, as the per-set fits already required. With
  none, the ridge alone fixed the term at zero with a meaningless SE.

Neither changes the removal or curve tests, whose counts already matched the
engine's.

Made on 2026-11-08, for the second batch of rules.

- **Three more rules are tested.** All three boost a card while the pool is
  short of something:

  | rule | multiplier | tested on decks | the rule is supported if |
  |---|---|---|---|
  | Critical: Needs Creatures | 1.25x for creatures from pack 2 while the pool is on course for fewer than 13 | each creature while the deck has fewer than 13, against a spell of the same rating | it's worth more |
  | Critical: Needs Removal | 1.3x for removal from pack 2 while the pool has fewer than 3 | each removal spell while the deck has fewer than 3, against a spell of the same rating | it's worth more |
  | Critical: Needs 2-Drops | up to 1.5x for creatures and removal of mana value 2 or less, from pack 2, while the pool is on course for fewer than 7 | each such card while the deck has fewer than 7, against a spell of the same rating | it's worth more |

  Each gets a slope and a change of slope at the rule's threshold. Needs
  Removal also keeps the slope change past the sixth.
- **This batch was seen before it was written down here.** These three rules
  were first run on these same decks in the closed #244
  ([run 41737611582](https://github.com/JamesYouL2/MTGA_Draft_17Lands/actions/runs/41737611582)),
  under the same primary estimate and verdict rule, so this run does not test
  them on unseen data.
- **Intervals are now 99.17%,** 95% familywise across all six rules, so the
  first three rules' intervals widen.
- **A rule's size for Needs 2-Drops is taken at two short (1.3x),** since its
  multiplier grows with the shortfall. The size is descriptive; it isn't used
  for the verdict.
- **A set needs decks both in and out of a rule's region.** Under Needs
  Removal every deck of an untagged set would be in the region, and it would
  say nothing about the rule.
- **The engine's thresholds apply to decks unchanged.** The engine projects a
  pool of up to 45 cards onto its targets; a deck is 23 spells picked from
  that pool. So these tests ask whether a deck short of the target gets more
  from each such card, not whether the pool's projection is the right trigger.
  The engine also applies only one bonus to a card, in a fixed order, while
  a short deck here counts for each rule it is short on.

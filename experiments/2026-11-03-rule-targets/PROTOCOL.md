# Testing pick rules on game results: protocol

`Tools/DeckScoreFit/rules.py` uses the decks that `fit.py` fits (see
[the tool's README](../../Tools/DeckScoreFit/README.md)) to test three of
the advisor's pick rules (in `_calculate_composition_bonus()` in
`src/advisor/engine.py`). Each rule
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
pips count as main.

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

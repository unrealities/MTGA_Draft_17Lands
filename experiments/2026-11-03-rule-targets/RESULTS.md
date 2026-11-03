# Rule targets: results

Run [41737611582](https://github.com/JamesYouL2/MTGA_Draft_17Lands/actions/runs/41737611582)
at `5d06abf` (`982c416` plus a push trigger): 914,784 registered decks and 4.14M games from all 20 sets
with Premier Draft game data and Premier Draft ratings, up to 50,000 decks
a set.

The protocol is in [Tools/DeckScoreFit/README.md](../../Tools/DeckScoreFit/README.md#testing-pick-rules-on-game-results).
It was written down before each run. The full report is [rules.md](rules.md)
and the numbers are in [rules.json](rules.json). The first run, which tested
three rules, is
[41734489663](https://github.com/JamesYouL2/MTGA_Draft_17Lands/actions/runs/41734489663).
That run's estimates are unchanged; only their intervals are wider here.

## Which rules cost strength

A rule costs strength if the card it reweights is valued better without
it. That means the card's value from game results lies closer to zero than
to what the rule's multiplier makes it, across the whole interval. The
intervals are 99.17%: 95% familywise across the six rules. Values are per
card, in rating SDs.

| rule | value from games | the rule's size | rule's claim | keep or drop |
|---|---|---|---|---|
| Removal Saturated (0.8x past 6) | +0.24 [−0.15, +0.63] | −0.87 | not established | **drop** |
| Critical: Needs Fixing (1.4x) | −0.11 [−0.85, +0.63] | +1.33 | not established | **drop** |
| Curve Too Heavy (0.7x past 4) | −0.24 [−0.72, +0.25] | −1.30 | not established | can't tell (leans drop) |
| Critical: Needs Creatures (1.25x under 13) | +0.43 [+0.04, +0.81] | +0.83 | supported | can't tell |
| Critical: Needs Removal (1.3x under 3) | +0.76 [−0.01, +1.53] | +1.00 | supported | can't tell |
| Critical: Needs 2-Drops (up to 1.5x under 7) | +0.91 [+0.38, +1.45] | +0.85 | supported | can't tell (on target) |

The deck score's terms get the same reading. Values are in score points
against the app's weights.

| term | value from games | app's weight | keep or drop |
|---|---|---|---|
| two_colors | +3.67 [+2.87, +4.47] | +3.50 | **keep** |
| domain_supported | +0.18 [−0.62, +0.99] | +3.20 | **drop** |
| missing_fixing | −0.43 [−1.32, +0.47] | −2.50 | can't tell (leans drop) |

## Reading

- **Two pick rules cost strength: Removal Saturated and Needs Fixing.**
  - Removal past the sixth is worth slightly more than a spell of the same
    rating, not less: +0.20 (SE 0.05) with land, creature and color counts
    as controls.
  - A fixing card is worth about the same whether or not the deck is short of
    fixing: +0.13 (0.10) while short, +0.17 (0.05) after.
  - In the ablation screen these are also the two single rules whose removal
    raised agreement with drafters' picks the most: +0.36 and +0.86 points of
    top-1 agreement.
- **Curve Too Heavy leans the same way.** Win rate is flat from 0 to 6 heavy
  spells. Its interval only just reaches half the rule's size.
- **The three "Critical: Needs" rules point the right way.** Each card they
  boost is worth more than its rating, and the estimates are near each rule's
  size. For creatures, though, the threshold is not where the value is:
  - A creature is worth +0.19 (0.04) points from the 13th on, the same as
    below 13 (+0.17).
  - So creatures beat their ratings throughout. The rule is right while
    short, and it may be too narrow.
  - 2-drops are worth more while short (+0.35 against +0.16 from the 7th).
- **domain_supported costs strength.** Supported domain decks win about as
  often as other 3+ color decks of the same card quality: +0.18 points
  against the weight's +3.20. In the ablation screen, removing it changed the
  first build of only 0.10% of pools.
- **missing_fixing** is set from which builds drafters chose, not game
  results, so this reading doesn't overrule it.

## Limits

- **The two drops are partly post hoc.** The keep-or-drop reading was written
  down before this run, but after the first run's estimates for those two
  rules had been seen, and both runs use the same decks. Before removing
  either rule from the engine, confirm it on decks this test hasn't seen,
  such as the next set's.
- **It values cards, not pick decisions.** A rule that is wrong in size but
  rarely changes a pick costs little. The ablation screen measured how often
  picks change.
- **The rules count pools; this tests registered decks.** The engine's pool
  thresholds are applied to decks unchanged.
- **It is observational.** It values cards relative to their ratings, rather
  than measuring a change to the advisor.
- **Sets disagree.** The set-clustered SEs are about three times the
  model's.
- **Coverage gaps:**
  - Cube_-_Powered has no removal or fixing tags, so it is left out of the
    removal rules.
  - TDM's omen and dragonstorm cards count at their full mana value, as in
    `get_functional_cmc()`.
- **Ablations not tested here** (reasons in the README): the synergy rules,
  Enables Bomb Splash, Premium Fixing, relative power, the IWD premium, the
  lane boost, archetype weighting, shrinkage, castability, and the deck
  builder's Monte Carlo penalties.

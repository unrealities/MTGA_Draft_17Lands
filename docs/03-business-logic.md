# Business Logic & Scoring Specification: "Compositional Brain" (v5.5 Pro)

**Version:** 5.5 | **Architecture:** Pro-Tour Context Engine & Archetype Gravity

## 1. Introduction

The v5.5 Engine abandons rigid heuristics in favor of a fluid, context-aware model. It simulates high-level drafting by shifting its focus from global card quality to specific archetype performance as the draft progresses, while enforcing a sliding commitment curve to prevent late-draft indecision.

---

## 2. Lane Detection (Sunk Cost Evasion)

The engine does not "lock in" colors based on the first few picks. It uses recency bias to ensure that recent high-quality picks outweigh early mistakes.

- **Formula:** `Score = Base Z-Score * Recency Multiplier`
- **Recency Multiplier:** Scales linearly from `1.0x` (Pick 1) up to `2.5x` (Current Pick).
- **Effect:** If you pivot from Red to Blue in Pack 2, the "Gravity" of your Red picks decays rapidly, allowing the Advisor to suggest the correct Blue cards for your current UX reality.

---

## 3. Archetype Gravity (Pair Performance)

Instead of evaluating a card globally (e.g., its win rate across all 17Lands users), the engine identifies your leading "Color Pair" (e.g., Blue-Black/UB) and prioritizes data for that specific pairing.

- **Gravity Logic:** The engine scores all 10 possible color pairs based on the weighted power of cards in your pool and the presence of "Gold" cards that reward specific pairs.
- **Progressive Weighting:** Once your pool has a leading pair, a card's score is its Global GIHWR plus a weight times how much better (or worse) it does in that pair. The weight rises through each pack, from 0.65 at the first pick to 1.21 at the 13th, the last choice in a 14-card pack; it stops growing at the 15th, at 1.3. In Pick-Two drafts, where each pick takes two cards, pick N weighs like pick 2N − 1, when as many cards have left the pack. Since 4.32, a positive pair win rate with at least 10 samples counts in full; otherwise the overall rate is used. The previous shrinkage toward the overall rate below 1,000 samples is removed. The supporting replay used whole-format data, so it does not establish how this behaves during a new set's first days.
- **Counted once:** The pair's win rate enters the score only through this weighting; there is no separate bonus for cards that do better in the pair than overall. When the weighting moves a card's score by 5 points or more (a third of a standard deviation), its reasons say so, for example **Better in UB (+6.2)** or **Worse in UB (-5.4)**.

---

## 4. Color Commitment and Castability

Since 4.33, Pack 1 has no off-color castability penalty, including late picks
and gold cards. Pair-performance weighting and a flat `1.1x` bonus for cards
castable in the detected lane still influence scores. The larger `1.3x`
on-lane bonus for a short Pack 3 pool is removed.

From Pack 2 onward, the top two lane colors define off-color requirements.
Unsupported off-color cards receive `0.05x` in Pack 2 and `0.01x` in Pack 3.
Double off-color pips with fewer than two fixing cards receive `0.01x`.
Supported single-pip splashes receive `0.3x`; qualifying bombs and premium
removal have separate splash allowances. Hybrid requirements are checked per
symbol, as described in [hybrid-mana.md](hybrid-mana.md).

---

## 5. Compositional Math & Dynamic Needs

Modern Limited is dictated by "Mana Velocity" and "Mana Stability."

- **Removed penalties (4.33):** Curve Too Heavy (`0.7x` after four 5+ mana cards) and Removal Saturated (`0.8x` after six removal spells) no longer affect scores.
- **Creature Quota:** From Pack 2, creatures receive `1.25x` when the projected creature count is below 13.
- **Velocity Target:** 7+ "Early Plays" (CMC <= 2 Creatures or cheap interaction).
- **Velocity Hunger:** The engine projects your final 2-drop count based on your current pool relative to the remaining picks in the draft. If the projection is below 7 entering Pack 2, early plays receive a "Critical: Needs 2-Drops" multiplier (up to 1.5x).
- **Dynamic Fixing Hunger:** The engine actively monitors whether you are drafting a highly synergistic 2-color deck, or moving towards a "Good Stuff" 3/4-color splash strategy. If the number of drafted off-color playables exceeds your dedicated fixing tools (dual lands, treasures, dorks) by Pack 2, fixing cards receive a massive `1.4x` "Critical: Needs Fixing" multiplier. The optional `1.15x` Premium Fixing and `1.3x` Enables Bomb Splash bonuses are removed in 4.32. Castability splash rules, including Greedy Bomb Splash, remain separate.

---

## 6. Wheel Chance (Shown, Not Scored)

The engine estimates each card's chance of coming back from its ALSA and its rank in the pack, and shows it in the Wheel column. It doesn't change the card's score. Packs with fewer than 9 cards, and picks 9 and later, show no chance. The existing curves assume eight-player, one-card picks: Pick-Two and other pod sizes show no percentage until a suitable model exists. This does not disable the scanner's pack-return tracker.

In Pick-Two, archetype weighting uses pick `2N - 1` for passing round `N`,
so weighting advances with cards removed. Pack 1 has no off-color penalty.

Replays of 15,000 17Lands drafts showed that value over replacement, the late-signal bonus, the wheel multiplier, the signal tie-breaker and the pack 3 deck-improvement bonus didn't change the advisor's picks or how following it related to winning, so the engine no longer uses them (v4.28). The Open Lanes panel still shows lane signals.

---

## 7. Semantic Role Analysis (Interaction)

The app parses Scryfall community tags to understand a card's functional role. The artifact, graveyard and counters synergy multipliers and their three ETL tag queries were removed in 4.32 because those tags were absent from the checked datasets. Custom datasets carrying those tags no longer receive the corresponding bonuses.

- **Hard Removal Quota:** Targets 3+ removal spells. If the pool is lacking entering Pack 2, interaction cards receive a `1.3x` panic multiplier.

---

## 8. True Bomb Detection (IWD Injection)

- **Logic:** A card is tagged as a **TRUE BOMB** only if its Z-Score is `> 1.0` AND its **Improvement When Drawn (IWD)** is `> 4.5%`.
- **Effect:** Distinguishes between "Great Filler" and "Game-Warping Power." These cards receive a power bonus that overrides the Sliding Commitment Curve, allowing for late-draft splashes.

---

## 9. Interactive Deck Building & AI Optimization

### A. Frank Karsten Mana Base Engine ("Auto-Lands")

Users can click a single button to perfectly balance their lands using Pro-Tour heuristics:

- **Pip Volume Calculation:** Counts the exact number of specific colored mana symbols.
- **Universal Fixer Detection:** Explicitly identifies Treasure-makers, Fetchlands, and "Any Color" dorks.
- **Hybrid Mana Resolution:** Pays hybrid mana (e.g., `{W/U}`) with a color the deck already plays; `{2/U}` and `{U/P}` never force a color. Castability, splash checks, mana allocation and deck labels share these rules; see [hybrid-mana.md](hybrid-mana.md).
- **Allocation (4.33):** Auto Lands uses the pip-based mana allocation rule directly, without simulating land permutations. It fills `max(0, 40 − spell copies)` land slots, retains nonbasics that fit, moves trimmed nonbasic copies to the sideboard, and replaces the basics. Auto-Optimize is a separate simulation-based action.
- **Splash Starvation Protection:** Strictly caps basic land allocations for splash colors to prevent main-color starvation.

### B. Monte Carlo Simulation

Evaluates the user's custom deck by running a **10,000-game Monte Carlo simulation**.

- Simulates every card copy for decks of 40 cards or more; larger decks are no longer truncated to 40 (4.33). Decks smaller than 40 are not simulated.
- Applies pro-level London mulligan heuristics.
- Calculates probabilities for `cast_t2/t3/t4`, Mana Screw, Mana Flood, and Color Screw.
- **Mana filters** (Prophetic Prism, Chromatic Star), whose mana abilities cost as much mana as they make, count toward the colors a deck can cast but not toward its mana. Signets, Sol Ring, mana dorks and Treasure makers stay ramp.
- **Repeatable results:** Every deck uses the same fixed random seed, and cards are put in a canonical order first, so a deck always gets the same results and card order or names don't change them.

### C. Deck Score & Estimated Record

The deck builder ranks its candidate builds by a deck score:

`75 + 12 × card quality + 3.1 if two colors or fewer − 2.5 per missing fixing card − 10 per missing spell`

- **Card quality** is the mean overall win rate of the deck's spells, in standard deviations from the format mean. A card's win rate in the deck's pair isn't used here: it also carries how the pair does as a whole. The builders still use it to choose cards within a pair.
- **Missing fixing:** for decks of 3+ colors, fixing cards short of one per color beyond the first.
- **Missing spells:** spells short of a full deck for the pool size, less one.

The weights were fit to about 915,000 17Lands Premier Draft decks over twenty sets, comparing players of similar skill (`Tools/DeckScoreFit`). Curve, evasion, tribal and supported-domain adjustments were worth about zero once card quality was counted, so the score leaves them out. In 4.33, the two-color weight changes from +3.5 to +3.1, the +3.2 supported-domain bonus is removed, and the score-to-record calibration is refitted with overall ratings. The missing-fixing weight is fit instead to which candidate builds drafters chose; see [the deck builder's suggestions before and after](logs/deck-builder-before-after.md).

Since 4.33, the Monte Carlo simulation's rates are shown with each build and don't change its score; color screw, mana screw and flood penalties are removed.

Draft suggestions generate Consistent, splash and Domain / Soup candidates; the Tempo candidate is removed in 4.33. The best Safe Core is promoted to first place only when within six score points of the leader; otherwise it stays in score order. There is no longer a separate promotion to second place. Sealed Studio still generates its Aggro/Tempo shell using the quick curve builder.

The **estimated record** (`[Est: 3.5 wins]`) is the expected number of wins for a deck of that score: in Premier Draft, an event that ends at 7 wins or 3 losses; in Traditional Draft, three best-of-three matches.

### D. On-Demand AI Auto-Optimizer

The Auto-Optimize button tries one-card changes to the current deck in a background task.

- It generates variations: **Play 18 Lands** (one more land), **Play 16 Lands** (one land fewer), **Curve Lower**, **Power Up**, **Fix Mana Base** (swapping a colorless utility land for a basic) and **Optimize Mana** (one basic swapped for another).
- It simulates 500 games for each variation, one after another, then 10,000 for the one it picks.
- It picks the variation that maximizes `cast_t2/t3/t4` + `curve_out`, less penalties for `mulligans`, `color_screw`, `mana_screw` and `flood`.

---

## 10. Post-Draft Analysis & Dashboard

Transitions into a Post-Draft Recap tracking:

- **Holistic Pool Grading:** Evaluated on a realistic 100-point scale.
- **Steals & Reaches:** Compares exact Pack/Pick against global ALSA/ATA.
- **Tribal Synergy:** Dynamically queries the MTGA SQLite database for `SubType` enumerators to highlight tribal synergies.

---

## 11. Sealed Studio & Shell Generation

Added in v4.15, the application includes a dedicated workspace for Sealed deckbuilding.

- **AI Shell Generator:** Because Sealed pools contain 90+ cards, it's difficult to find the correct lane manually. The AI evaluates the pool and generates the Top 3 mathematically optimal 40-card shells on demand:
  1. **Safe 2-Color:** The best 2-color pair, built from its strongest playables.
  2. **Greedy Splash:** Automatically forces the best off-color Bomb into the deck, adding the pool's useful fixing lands.
  3. **Aggro/Tempo:** Filters the secondary best color pair through a strict CMC penalty to build a low-to-the-ground deck.
- **Visual Deckbuilder:** A 1-to-1 recreation of the MTGA client's column-based (CMC sorted) drag-and-drop workspace, complete with real-time image caching via the `ThreadPoolExecutor`.


## 12. Evidence and Historical Rating Models

The [six-rule experiment](../experiments/2026-11-03-rule-targets/RESULTS.md)
adds creature, removal and early-play shortfall tests to the original three
rules. Its supported associations do not establish the advisor's multiplier
sizes or show that the thresholds themselves improve picks.

The [rating experiment](../experiments/2026-11-03-rating-parts/RESULTS.md)
compares predictions for held-out two-color decks with folds grouped by draft.
The [pair-parts experiment](../experiments/2026-11-08-pair-parts/RESULTS.md)
separates a pair's overall level from a card's fit within it. Whole-deck
prediction and within-pack ranking answer different questions; these results
do not directly prescribe replacement pick weights.

The tools retain the pre-4.32 shrunk rating under the historical name `engine`
so committed reports remain reproducible. The current advisor's unshrunk pair
rate corresponds to the `no-shrinkage` variant, not that historical baseline.


The [joint-removal replay](../experiments/2026-11-15-joint-removals/RESULTS.md)
compares the combined simplifications with an earlier engine. Its pools used
card-column order, and whole-format ratings include the replayed drafts.
The [lane-accuracy experiment](../experiments/2026-11-15-lane-accuracy/RESULTS.md)
measures agreement with the colors drafters played, not the best possible colors.
It identified the pool-order discrepancy fixed in AdvisorReplay for 4.33.
The live lane rule is unchanged; a stronger card-count yardstick in this
experiment is not a shipped replacement.

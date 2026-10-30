# Business Logic & Scoring Specification: "Compositional Brain" (v5.5 Pro)

**Version:** 5.5 | **Architecture:** Pro-Tour Context Engine & Archetype Gravity

## 1. Introduction

The v5.5 Engine abandons rigid heuristics in favor of a fluid, context-aware model. It simulates high-level drafting by judging cards by their performance in your leading archetype, while enforcing a sliding commitment curve to prevent late-draft indecision.

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
- **Archetype Weighting:** From the first pick, a card's score is 90% its win rate in your leading pair and 10% its Global GIHWR (the pair's win rate is shrunk toward the global one when it has fewer than 1,000 games). Replaying 17Lands drafts, this matched drafters' picks more often than ramping up to the pair over the draft.
- **Synergy Payoff:** If a card performs > 1.5% better in your specific color pair than its global average, it receives an **Archetype Synergy** bonus.

---

## 4. Sliding Commitment Curve (Lane Pressure)

To prevent the engine from suggesting off-color cards too late in the draft, it applies a sliding scale of pressure based on the pick number.

| Phase             | Picks         | Logic Name   | Behavior                                                                                                                  |
| :---------------- | :------------ | :----------- | :------------------------------------------------------------------------------------------------------------------------ |
| **P1 Picks 1-4**  | Stay Open     | Neutral      | No penalties for off-color cards. Encourages taking the best card regardless of color.                                    |
| **P1 Picks 5-15** | Lane Pressure | Linear Decay | Applies a `-0.05` penalty multiplier per pick to off-color cards. By P1P15, off-color cards are significantly suppressed. |
| **Pack 2**        | Soft Lock     | Disciplined  | Severe penalties (up to 85% reduction) for cards outside your top 2-3 colors unless they are massive bombs.               |
| **Pack 3**        | Hard Lock     | Committed    | Total exclusion of off-color cards (95% penalty) to ensure the final pool is playable.                                    |

---

## 5. Value Over Replacement (VOR) & "Glue Cards"

The v5 engine moves beyond raw win rates by pre-calculating the **Format Texture** of a set when it loads.

- **Role Scarcity (VOR):** The engine analyzes the dataset to count how many "Playable" (WR > Baseline) Commons and Uncommons exist for critical roles (e.g., Removal, 2-Drops) in each color.
  - If a user sees a Playable Red 2-Drop, and the engine knows there are only two viable Red 2-drops in the entire set, it applies a `High VOR (+6.0)` bonus.
- **Archetype Glue:** If a Common/Uncommon has a win rate in the user's specific color pair that is `> 1.0%` higher than its global average, it is classified as "Archetype Glue." It receives an aggressive point multiplier to force it to outscore generic Rares.

---

## 6. Semantic Role Analysis (Interaction & Tricks)

The app parses Scryfall community tags to understand a card's functional role.

- **Trick Diminishing Returns:** Combat tricks and Auras (Enhancements) are capped at 3. Beyond this, they receive a severe `0.5x` penalty.

---

## 7. True Bomb Detection (IWD Injection)

- **Logic:** A card is tagged as a **TRUE BOMB** only if its Z-Score is `> 1.0` AND its **Improvement When Drawn (IWD)** is `> 4.5%`.
- **Effect:** Distinguishes between "Great Filler" and "Game-Warping Power." These cards receive a power bonus that overrides the Sliding Commitment Curve, allowing for late-draft splashes.

---

## 8. Interactive Deck Building & AI Optimization

### A. Frank Karsten Mana Base Engine ("Auto-Lands")

Users can click a single button to perfectly balance their lands using Pro-Tour heuristics:

- **Pip Volume Calculation:** Counts the exact number of specific colored mana symbols.
- **Universal Fixer Detection:** Explicitly identifies Treasure-makers, Fetchlands, and "Any Color" dorks.
- **Hybrid Mana Resolution:** Correctly categorizes hybrid mana (e.g., `{W/U}`) towards whichever core color the deck favors.
- **Splash Starvation Protection:** Strictly caps basic land allocations for splash colors to prevent main-color starvation.

### B. Monte Carlo Simulation

Evaluates the user's custom deck by running a **10,000-game Monte Carlo simulation**.

- Applies pro-level London mulligan heuristics.
- Calculates probabilities for `cast_t2/t3/t4`, Mana Screw, Mana Flood, and Color Screw.

### C. On-Demand AI Auto-Optimizer

Users can actively "brute-force" permutations of their current deck configuration via a dedicated background task.

- It generates variations: **Play 18 Lands**, **Play 16 Lands**, **Curve Lower**, **Power Up**, and **Fix Mana Base** (swapping colorless utility lands for core colored basics).
- It simulates thousands of games for each variation simultaneously.
- Selects the deck configuration that maximizes `cast_t2/t3/t4` + `curve_out` while heavily penalizing `color_screw`, `mana_screw`, and `flood`.

---

## 9. Post-Draft Analysis & Dashboard

Transitions into a Post-Draft Recap tracking:

- **Holistic Pool Grading:** Evaluated on a realistic 100-point scale.
- **Steals & Reaches:** Compares exact Pack/Pick against global ALSA/ATA.
- **Tribal Synergy:** Dynamically queries the MTGA SQLite database for `SubType` enumerators to highlight tribal synergies.

---

## 10. Sealed Studio & Shell Generation

Added in v4.15, the application includes a dedicated workspace for Sealed deckbuilding.

- **AI Shell Generator:** Because Sealed pools contain 90+ cards, it's difficult to find the correct lane manually. The AI evaluates the pool and generates the Top 3 mathematically optimal 40-card shells on demand:
  1. **Best 2-Color:** The most consistent 2-color pair based on raw power and curve.
  2. **Greedy Splash:** Automatically forces the best off-color Bomb into the deck, strictly allocating appropriate fixing lands/treasures.
  3. **Aggro/Tempo:** Filters the secondary best color pair through a strict CMC penalty to build a low-to-the-ground deck.
- **Visual Deckbuilder:** A 1-to-1 recreation of the MTGA client's column-based (CMC sorted) drag-and-drop workspace, complete with real-time image caching via the `ThreadPoolExecutor`.

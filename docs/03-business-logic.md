# Business Logic & Scoring Specification: "Compositional Brain" (v5.1 Pro)

**Version:** 5.1 | **Architecture:** Pro-Tour Context Engine & Archetype Gravity

## 1. Introduction

The v5.1 Engine abandons rigid heuristics in favor of a fluid, context-aware model. It simulates high-level drafting by shifting its focus from global card quality to specific archetype performance as the draft progresses, while enforcing a sliding commitment curve to prevent late-draft indecision.

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
- **Progressive Weighting:**
  - **Pack 1:** Evaluates cards primarily (90%) on their Global GIHWR.
  - **Pack 3:** Evaluates cards primarily (80%) on their Archetype-specific win rate.
- **Synergy Payoff:** If a card performs > 1.5% better in your specific color pair than its global average, it receives an **Archetype Synergy** bonus (multiplied by 3.5x the delta).

---

## 4. Sliding Commitment Curve (Lane Pressure)

To prevent the engine from suggesting off-color cards too late in the draft, it applies a sliding scale of pressure based on the pick number.

| Phase             | Picks         | Logic Name   | Behavior                                                                                                                  |
| :---------------- | :------------ | :----------- | :------------------------------------------------------------------------------------------------------------------------ |
| **P1 Picks 1-7**  | Stay Open     | Neutral      | No penalties for off-color cards. Encourages taking the best card regardless of color.                                    |
| **P1 Picks 8-15** | Lane Pressure | Linear Decay | Applies a `-0.05` penalty multiplier per pick to off-color cards. By P1P15, off-color cards are significantly suppressed. |
| **Pack 2**        | Soft Lock     | Disciplined  | Severe penalties (up to 85% reduction) for cards outside your top 2-3 colors unless they are massive bombs.               |
| **Pack 3**        | Hard Lock     | Committed    | Total exclusion of off-color cards (95% penalty) to ensure the final pool is playable.                                    |

---

## 5. Compositional Math (The 2-Drop Rule)

Modern Limited is dictated by "Mana Velocity"—the ability to affect the board early.

- **Velocity Target:** 7+ "Early Plays" (CMC <= 2 Creatures or cheap interaction).
- **Hunger Formula:** The engine projects your final 2-drop count based on your current pool relative to the remaining picks in the draft.
- **Panic Mode:** If the projection is below 7 entering Pack 2, all 2-drop creatures receive a "Critical: Needs 2-Drops" multiplier (up to 1.5x).
- **Top-Heavy Penalty:** If you have 4+ cards costing 5+ mana, expensive cards receive a `0.7x` dampening multiplier to prevent "clunky" hands.

## 6. Value Over Replacement (VOR) & "Glue Cards"

The v5 engine moves beyond raw win rates by pre-calculating the **Format Texture** of a set when it loads.

- **Role Scarcity (VOR):** The engine analyzes the dataset to count how many "Playable" (WR > Baseline) Commons and Uncommons exist for critical roles (e.g., Removal, 2-Drops) in each color.
  - If a user sees a Playable Red 2-Drop, and the engine knows there are only two viable Red 2-drops in the entire set, it applies a `High VOR (+6.0)` bonus.
  - This pushes players to draft scarce resources early, rather than taking a slightly higher win-rate card that has 7 viable replacements later in the draft.
- **Archetype Glue:** Players often fall into the trap of taking a mediocre Rare over a great Common. If a Common/Uncommon has a win rate in the user's specific color pair that is `> 1.0%` higher than its global average, it is classified as "Archetype Glue." It receives an aggressive point multiplier to force it to outscore clunky, generic Rares.

---

## 7. Semantic Role Analysis (Interaction & Tricks)

The app parses Scryfall community tags to understand a card's functional role, preventing deck saturation.

- **Hard Removal Quota:** Targets 3+ removal spells. If the pool is lacking entering Pack 2, interaction cards receive a `1.3x` panic multiplier. Conversely, if you have 6+ removal spells, new ones are penalized (`0.8x`).
- **Trick Diminishing Returns:** Combat tricks and Auras (Enhancements) are capped at 3. Beyond this, they receive a severe `0.5x` penalty to ensure you draft enough creatures to actually use the tricks.
- **Flood Insurance:** "Mana Sinks" (cards with activated abilities) are weighted higher in Pack 2/3 if the deck lacks late-game utility.

---

## 7. Signal Capitalization (Draft Navigation)

The engine reads signals in Pack 1 to identify if a specific color is being "passed" by your neighbors.

- **Trigger:** Pack 1, Pick 5+.
- **Math:** `Lateness = Current Pick - Average Taken At (ATA)`.
- **Application:** If a high-quality card (Z-Score > 0.5) is seen much later than its average take-rate, it receives a flat point bonus.
- **Effect:** This gently nudges the user to pivot into an open lane if a premium card wheels or appears late.

---

## 8. True Bomb Detection (IWD Injection)

A high win rate can be misleading (e.g., an aggressive 1-drop has a high win rate but is not a "bomb").

- **Logic:** A card is tagged as a **TRUE BOMB** only if its Z-Score is `> 1.0` AND its **Improvement When Drawn (IWD)** is `> 4.5%`.
- **Effect:** Distinguishes between "Great Filler" and "Game-Warping Power." These cards receive a power bonus that can override the Sliding Commitment Curve, allowing for late-draft splashes.

---

## 9. Premium Fixing Speculation

- **Pack 1 Speculation:** Multi-color lands (Duals) receive a `1.15x` multiplier to encourage staying open.
- **Splash Enablers:** If you drafted a high-quality bomb early but abandoned its color, the engine logs it as a "Splash Target." Lands that produce that color then receive a `1.3x` multiplier to proactively fix the mana base for that bomb.

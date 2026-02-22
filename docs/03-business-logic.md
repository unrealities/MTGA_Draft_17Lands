# Business Logic & Scoring Specification: "Compositional Brain" (v4)

**Version:** 4.1 | **Architecture:** Formulaic Balance & Context Engine

## 1. Introduction

The v4 "Compositional Brain" replaces strict logic gates with formulaic curves. It treats the draft as a math problem of resource allocation (Creatures vs. Spells) and reads the table relative to the power level of the current pack.

## 2. Dynamic Lane Identification

- **Quality Weighting:** We do not count cards. We count _power_.
- **Formula:** `Score = Sum((Card.GIHWR - 50.0) / 5.0)`.
- **Effect:** A 65% WR Bomb contributes 3 points to color commitment. A 52% Filler card contributes 0.4 points.

## 3. Compositional Math (Role Theory)

Instead of "If < 15 Creatures", we use a continuous supply/demand curve.

### 3.1. Projections

The engine projects your final deck composition based on current draft progress.

- `Projected_Count = Current_Count * (45 / Picks_Made)`

### 3.2. Hunger Formula

- **Creatures:** Target 15.
- **Calculation:** `Ratio = Projected / Target`.
- **Bonus:** If `Ratio < 0.8` (Behind schedule), apply multiplier `1 + (0.8 - Ratio)`.
- **Penalty:** If `Ratio > 1.4` (Oversaturated), apply penalty decay.

## 4. Alien Gold Protection

Strict logic to prevent "Shiny Object Syndrome" with multicolor cards.

- **Rule:** If a card is Multicolor AND shares _zero_ colors with the established main colors:
  - **Score:** **0.0** (Hard Lock).
  - **Reason:** "Alien Gold".
  - _Exception:_ If the pool has 4+ Fixing sources, it is treated as a 5-color soup candidate.

## 5. Pack 2 Discipline (New in v4.1)

To prevent speculative picking from derailing a solid deck, the logic enforces strict penalties for off-color cards once the draft enters Pack 2.

- **Trigger:** Pack >= 2 AND Card is Off-Color.
- **Logic:**
  - If **Fixing Sources <= 1** (Meaning no duals/treasures, just a basic):
    - **Penalty:** Multiplier **0.2** (Severe).
    - **Exception:** If Z-Score > 2.5 (True Bomb), Multiplier is **0.6**.
  - This ensures that a "Good" off-color card (e.g., 61% WR) does not score higher than a "Great" on-color card (e.g., 64% WR) simply due to raw stats.

## 6. Relative Wheel Probability

We do not look at ALSA in a vacuum. We look at the pack texture.

- **Rank Logic:**
  1. Sort Pack by GIHWR.
  2. Identify Rank of Target Card (1 = Best).
- **Algorithm:**
  - If `Rank <= 3`: **Wheel Chance 0%**. (Will be taken).
  - If `Rank >= 8` AND `ALSA > Pick + 7.5`: **High Wheel Chance**.
- **Strategy:** This allows taking the _second_ best card if the _best_ card is weak enough to wheel, netting two cards.

## 7. Wheel Signal Analysis (P1P9)

The signal engine now remembers Pack 1 Pick 1.

- **Trigger:** Pick 9.
- **Logic:** Compare P1P9 contents to P1P1 contents.
- **Quality Retention:** `Sum(GIHWR > 54) of P1P9 / Sum(GIHWR > 54) of P1P1`.
- **Interpretation:**
  - If `Retention > 30%`: The color was passed by 7 players. **OPEN LANE.**
  - If `Retention < 10%`: The good cards were stripped. **CLOSED LANE.**

## 8. Deck Generation Engine (v4)

The v4 Deck Suggester abandons strict hardcoded requirements (e.g., "Must have exactly 15 creatures") in favor of generating distinct strategic archetypes and evaluating them using a holistic scoring matrix.

### 8.1. Archetype Variants

For every viable color pair, the engine attempts to build three variants:

1. **Consistency (Midrange):** Strictly adheres to the 2 main colors. Prioritizes raw Z-Score.
2. **Greedy (Bomb Splash):** Identifies the highest WR off-color card in the pool and forces it into the deck, recalculating the mana base to accommodate it.
3. **Tempo (Aggro):** Applies a weighted modifier to cards based on CMC (+4.0 for CMC 1-2, -8.0 for CMC 5+).

### 8.2. Holistic Power Level

Instead of counting cards, decks are scored on a 0-100 scale using four pillars:

1. **Base Power:** The average Z-score of all non-lands in the deck.
2. **Mana Velocity:** Penalizes the deck if the `(Average CMC * 5.5)` exceeds the number of available mana sources. Rewards ultra-low CMC decks.
3. **Synergy Matrix:** Scans the deck for Tribal overlap (e.g., 6+ matching creature types + 2 payoffs) or Domain enablers.
4. **Playables Deficit:** Severely penalizes the deck if it is forced to run basic lands in spell slots due to a lack of playable cards.

### 8.3. Frank Karsten Mana Bases

Mana bases are dynamically generated using proportional math with safety floors:

- **Primary/Secondary Colors:** Guaranteed a minimum of 6 sources.
- **Splash Colors:** Guaranteed a minimum of 3 sources.
- Remaining lands are distributed proportionally based on pip density. Overflows/underflows are awarded to the color with the highest/lowest pip count to strictly enforce a 40-card deck size.

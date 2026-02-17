# Business Logic & Scoring Specification: "Compositional Brain" (v4)

**Version:** 4.0 | **Architecture:** Formulaic Balance & Context Engine

## 1. Introduction

The v4 "Compositional Brain" replaces strict logic gates with formulaic curves. It treats the draft as a math problem of resource allocation (Creatures vs. Spells) and reads the table relative to the power level of the current pack.

## 2. Dynamic Lane Identification

* **Quality Weighting:** We do not count cards. We count *power*.
* **Formula:** `Score = Sum((Card.GIHWR - 50.0) / 5.0)`.
* **Effect:** A 65% WR Bomb contributes 3 points to color commitment. A 52% Filler card contributes 0.4 points.

## 3. Compositional Math (Role Theory)

Instead of "If < 15 Creatures", we use a continuous supply/demand curve.

### 3.1. Projections

The engine projects your final deck composition based on current draft progress.

* `Projected_Count = Current_Count * (45 / Picks_Made)`

### 3.2. Hunger Formula

* **Creatures:** Target 15.
* **Calculation:** `Ratio = Projected / Target`.
* **Bonus:** If `Ratio < 0.8` (Behind schedule), apply multiplier `1 + (0.8 - Ratio)`.
* **Penalty:** If `Ratio > 1.4` (Oversaturated), apply penalty decay.

## 4. Alien Gold Protection

Strict logic to prevent "Shiny Object Syndrome" with multicolor cards.

* **Rule:** If a card is Multicolor AND shares *zero* colors with the established main colors:
  * **Score:** **0.0** (Hard Lock).
  * **Reason:** "Alien Gold".
  * *Exception:* If the pool has 4+ Fixing sources, it is treated as a 5-color soup candidate.

## 5. Relative Wheel Probability

We do not look at ALSA in a vacuum. We look at the pack texture.

* **Rank Logic:**
    1. Sort Pack by GIHWR.
    2. Identify Rank of Target Card (1 = Best).
* **Algorithm:**
  * If `Rank <= 3`: **Wheel Chance 0%**. (Will be taken).
  * If `Rank >= 8` AND `ALSA > Pick + 7.5`: **High Wheel Chance**.
* **Strategy:** This allows taking the *second* best card if the *best* card is weak enough to wheel, netting two cards.

## 6. Wheel Signal Analysis (P1P9)

The signal engine now remembers Pack 1 Pick 1.

* **Trigger:** Pick 9.
* **Logic:** Compare P1P9 contents to P1P1 contents.
* **Quality Retention:** `Sum(GIHWR > 54) of P1P9 / Sum(GIHWR > 54) of P1P1`.
* **Interpretation:**
  * If `Retention > 30%`: The color was passed by 7 players. **OPEN LANE.**
  * If `Retention < 10%`: The good cards were stripped. **CLOSED LANE.**

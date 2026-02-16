# Business Logic & Scoring Specification: "Pro Tour" Engine

**Version:** 2.0 (Stable) | **Architecture:** Context-Aware Heuristic Engine

## 1. Introduction & Philosophy

The core value proposition of the MTGA Draft Tool is its ability to simulate the decision-making process of a professional player. Unlike simple "Tier List" overlays which provide static grades (e.g., "A-"), this engine generates dynamic scores based on the current context of the draft.

The engine operates on a fundamental principle: **"A card's value is a function of its statistical power, its mana cost relative to the user's mana base, and its strategic fit within the curve."**

### The Master Scoring Formula

The final score presented to the user (0-100) is derived as follows:

$$ Score = \text{Clamp}(0, 100, [(\text{BaseScore} + \text{PowerBonus}) \times \text{CastProbability} \times \text{CurveFit} \times \text{WheelGreed}]) $$

---

## 2. Base Quality: Weighted Archetype Scoring

The foundation of the score is the win rate. However, the relevance of "Global" data diminishes as the draft progresses.

### 2.1. Draft Progress

The engine tracks the "Draft Progress" as a float from `0.0` (Start) to `1.0` (End).

* **Formula:** `Progress = CurrentPickNumber / 45` (Assuming 3 packs of 15 cards).

### 2.2. The Weighted Average

* **Global Win Rate (GWR):** The win rate of the card across all decks.
* **Archetype Win Rate (AWR):** The win rate of the card specifically within the user's current top 2 colors (e.g., "Dimir" or "UB").
* **Calculation:**
    $$ \text{ExpectedWR} = (\text{GWR} \times (1.0 - \text{Progress})) + (\text{AWR} \times \text{Progress}) $$

**Implication:**

* **Pick 1:** The score is 100% based on Global Win Rate (Speculative).
* **Pick 22 (Mid-Pack 2):** The score is a 50/50 blend.
* **Pick 45:** The score is 100% based on Archetype Win Rate (Committed).

### 2.3. Normalization

The `ExpectedWR` is normalized to a 0-100 scale for UI consistency.

* **Baseline:** 45.0% WR = Score 0.
* **Scale:** Every 1.0% above 45% adds 5 points.
* **Max:** Clamped at 100 (65% WR).

### 2.4. Power Bonus (Z-Score)

To highlight bombs in weak packs, we calculate the Z-Score (Standard Deviations above the mean) for the current pack.

* **Condition:** If `Z > 0.5`.
* **Bonus:** `Z * 10`.
* **Effect:** A card that is statistically much better than the rest of the pack gets a visual boost, even if its raw win rate is just "Good".

---

## 3. Mana Analysis: Karsten Probability & Castability

This module determines if the user can actually cast the card. It replaces simple color matching with hypergeometric probability logic.

### 3.1. Pip Density Analysis

The engine parses the `mana_cost` string (e.g., `{2}{U}{U}`) to count colored mana symbols ("Pips").

* `{4}{R}` -> 1 Red Pip (Splashable).
* `{1}{G}{G}` -> 2 Green Pips (Commitment).
* `{W}{W}{W}` -> 3 White Pips (Heavy Commitment).

### 3.2. Fixing Source Detection

The engine scans the user's `TakenCards` pool for fixing sources.

* **Rule:** A card counts as a "Fixing Source" if it has type `Land` (non-basic) or `Artifact` (CMC <= 3), or explicitly generates multiple colors (heuristic text scan).

### 3.3. Castability Multiplier

The engine applies a penalty based on the ability to cast the card "On Curve" (e.g., Turn 2 for a 2-drop).

| Condition | Multiplier | Reasoning |
| :--- | :--- | :--- |
| **On-Color** | **1.0x** | Matches one of the user's Main Colors. |
| **Speculation** | **0.95x** | Pick 1-5 (Pack 1). Low penalty to encourage pivoting. |
| **Splash (1 Pip)** | **0.8x** | If Fixing Sources >= 2. |
| **Splash (1 Pip)** | **0.4x** | If Fixing Sources < 2 (Greedy). |
| **Splash (2+ Pips)**| **0.0x** | **Hard Lock.** Cannot splash double pips. |
| **Exceptions** | **0.4x** | Double Pip splash allowed ONLY if Fixing Sources >= 4 (Treasure Deck). |

---

## 4. Structural Hunger: Dynamic Curve Fitting

The engine analyzes the mana curve of the drafted pool to prioritize missing pieces.

### 4.1. Functional CMC

Cards are categorized by their *playable* turn, not just printed cost.

* **Landcyclers:** Treated as CMC 1 (Land Fetch).
* **Split Cards:** Treated as the lower CMC half.

### 4.2. Hunger Logic

* **2-Drop Hunger:**
  * *Trigger:* Pick > 20 AND `Count(2-Drops) < 4`.
  * *Effect:* **1.15x** Bonus to cards with Functional CMC 2.
* **Top-End Satiety:**
  * *Trigger:* `Count(5+ Drops) >= 5`.
  * *Effect:* **0.6x** Penalty to cards with Functional CMC >= 5.

---

## 5. The "Greed" Factor: Wheel Prediction

To simulate professional drafting, the engine predicts if a card will circle the table (Wheel).

### 5.1. ALSA Analysis

It utilizes the **Average Last Seen At (ALSA)** statistic provided by 17Lands.

* **Pack Size:** Assumed to be 14 cards.
* **Wheel Threshold:** `CurrentPick + 7`.

### 5.2. The Calculation

If `Card.ALSA > (CurrentPick + 7)`:

* **Prediction:** The card is likely to be available when the pack returns.
* **Action:** Apply **0.8x** Penalty to the current score.
* **Result:** The engine will recommend a slightly worse card that *won't* wheel, effectively netting the user two cards instead of one.

---

## 6. Dynamic Deck Construction (The Builder)

When the user requests a deck suggestion, the engine generates **Variants** rather than a single "Best Deck". This acknowledges that deck building is subjective and situational.

### 6.1. The Frank-Karsten Mana Calculator

The engine calculates the optimal land count for every generated deck dynamically.

* **Formula:** `Lands = 17 + Round(AvgCMC - 3.0)`
* **Constraints:** Min 15, Max 18.
* **Distribution:** Colored sources are allocated based on the ratio of total pips in the deck.

### 6.2. Variant A: "The Rock" (Consistency)

* **Philosophy:** Maximum consistency, minimum variance.
* **Constraint:** Strictly 2 Colors (The top 2 open colors).
* **Selection:** Takes the highest rated cards that exactly match the colors.
* **Land Count:** Standard (usually 17).

### 6.3. Variant B: "The Greedy" (Splash Build)

* **Philosophy:** Power over consistency.
* **Constraint:** 2 Main Colors + 1 Splash Color.
* **Inclusion Criteria:**
  * Splash card must be a **Bomb** (Rating > 60).
  * Splash card must be **Single Pip**.
  * Pool must contain **2+ Fixing Sources** for that color.
* **Bonus:** Adds +50 "Cool Points" to the deck rating to highlight the potential power ceiling.

### 6.4. Variant C: "The Curve" (Tempo Build)

* **Philosophy:** Speed kills.
* **Constraint:** Low Curve bias.
* **Scoring:**
  * CMC <= 2: **1.1x** Bonus.
  * CMC >= 5: **0.7x** Penalty.
* **Land Count:** Hard-capped at **16 Lands**.

---

## 7. Data Models (Reference)

### Recommendation Object

The output of the engine passed to the UI.

```json
{
  "card_name": "Sheoldred",
  "contextual_score": 95.5,
  "cast_probability": 0.4,
  "wheel_chance": false,
  "reasoning": [
    "BOMB",
    "Risky Splash (Double Pip)",
    "Curve Too High"
  ]
}
```

### Deck Variant Object

The output of the deck builder.

```json
{
  "type": "Bomb Splash",
  "rating": 1450,
  "colors": ["B", "G", "R"],
  "deck_cards": [...],
  "sideboard_cards": [...]
}
```

```

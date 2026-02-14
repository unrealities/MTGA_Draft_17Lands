# Business Logic & Scoring Engine

**Status:** Implementation Spec | **Source:** `src/advisor/engine.py`

## 1. The Advisor Scoring Formula

The Advisor converts raw statistical data into a context-aware "Score" (0-100). This score represents a card's value to the specific deck being drafted, accounting for power level, color requirements, and deck structure needs.

$$ FinalScore = \text{Clamp}(0, 100, (\text{BaseScore} + \text{PowerBonus}) \times \text{CommitmentMult} \times \text{HungerMult}) $$

### Step 1: Base Quality (Normalized Win Rate)

The raw Games-in-Hand Win Rate (GIHWR) is normalized to a 0-100 scale.

- **Formula:** `Quality = (GIHWR - 45.0) * 5.0`
- **Logic:**
  - 45% WR -> Score 0
  - 55% WR -> Score 50 (Average)
  - 65% WR -> Score 100

### Step 2: The Power Bonus (Z-Score)

Calculates the statistical significance of a card relative to the rest of the pack to identify "Bombs" or "Signals".

- **Mean ($\mu$):** Average GIHWR of valid cards in the current pack.
- **StdDev ($\sigma$):** Standard Deviation of GIHWR in the pack.
- **Z-Score ($z$):** $(GIHWR - \mu) / \sigma$
- **Bonus:** If $z > 0.5$, add `(z * 15)` to the Base Quality.

### Step 3: Professional Lane Commitment (The Sinker)

This logic penalizes cards based on how difficult they are to cast given the current pool ("Active Colors") and the stage of the draft. It utilizes **Pip Analysis** to differentiate between "Splashable" cards and "Hard Cast" requirements.

**Definitions:**

- **Pip Count:** The number of colored mana symbols in the cost (e.g., `{1}{R}{R}` has 2 Red Pips).
- **Fixing:** The number of dual lands or mana rocks currently in the pool.

#### Draft Phases

1. **Speculation Phase (Pick 1-5):**
    - Goal: Accumulate power.
    - Penalty: **0.9x** (Slight bias toward early colors, but open to pivoting).

2. **Establishment Phase (Pick 6 - Pick 20):**
    - Goal: Define the lane.
    - Penalty: **0.4x** for off-color cards.
    - _Exception:_ Speculative Pivot allowed if Z-Score > 1.0 (Multiplier: 0.8x).

3. **Commitment Phase (Pick 21+):**
    - Goal: Fill curve and cement core.
    - Penalty: **0.05x** (Hard Lock). Off-color cards are virtually ignored unless they meet Splash Criteria.

#### The "Splash" Exception

An off-color card mitigates the penalty if it qualifies as a "Splashable Bomb":

1. **Power:** Z-Score > 1.5 (Must be statistically superior).
2. **Cost:** Must have **Single Pip** density (e.g., `{3}{R}` is splashable; `{1}{R}{R}` is not).
3. **Result:** Multiplier becomes **0.7x** instead of 0.05x.

_Note: If the user has >2 fixing sources, Double Pip bombs are considered playable at a 0.4x penalty in late packs._

### Step 4: Structural Hunger (The Fixer)

Adjusts score based on deck composition needs.

1. **Creature Hunger:**
    - _Check:_ `CurrentCreatures < ExpectedForPickNumber`.
    - _Effect:_ +0.25x multiplier.
2. **Curve Hunger (2-Drops):**
    - _Check:_ Pick > 20 AND `Count(2-Drops) < 3`.
    - _Effect:_ +0.2x multiplier.
3. **Interaction Hunger:**
    - _Check:_ Pick > 15 AND `InteractionCount < 5`.
    - _Effect:_ +0.2x multiplier for Instants/Sorceries/Enchantments.
4. **Curve Satiety (Top End):**
    - _Check:_ `CMC >= 5` AND `Count(5+ Drops) >= 4`.
    - _Effect:_ -0.3x penalty (Deck is too heavy).

## 2. Signal Detection Logic

Signal scores quantify "Open Lanes" based on passing patterns.

1. **Baseline:** Set global average win rate (e.g., 54.0%).
2. **Filter:** Ignore cards below baseline (bad cards passing late is not a signal).
3. **Lateness:** `Pick - AverageTakenAt`.
4. **Score:** `Lateness * (GIHWR - Baseline)`.
5. **Aggregation:** Sum scores by color. A score > 20 indicates a strongly open color.

## 3. Deck Building Templates

The application creates hypothetical decks using the user's pool to suggest archetypes.

- **Aggro:** 16 Lands, 17+ Creatures, Avg CMC < 2.40.
- **Midrange:** 17 Lands, 15+ Creatures, Avg CMC < 3.04.
- **Control:** 18 Lands, 10+ Creatures, Avg CMC < 3.68.

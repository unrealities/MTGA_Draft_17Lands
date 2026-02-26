# Business Logic & Scoring Specification: "Compositional Brain" (v5 Pro)

**Version:** 5.0 | **Architecture:** Pro-Tour Context Engine & Velocity Math

## 1. Introduction

The v5 Engine abandons rigid heuristics and emulates the fluid decision-making of a high-level drafter. It interprets draft logs through the lenses of **Sunk Cost Evasion**, **Mana Velocity**, and **Signal Capitalization**.

## 2. Lane Detection (Sunk Cost Evasion)

We do not lock into colors based on Pick 1. We weight recent picks heavier than early picks to detect the *actual* open lane.

- **Formula:** `Score = Base Z-Score * Recency Multiplier`
- **Recency Multiplier:** Scales from `1.0` (P1P1) up to `2.5` (Current Pick).
- **Effect:** If you take 3 Red cards early, but switch to Blue/Black in Pack 2, the engine's "Memory" of Red decays rapidly, correctly aligning the UI filters and Castability math to your *current* UX reality, not your past mistakes.

## 3. Compositional Math (The 2-Drop Rule)

Modern limited is dictated by the 2-drop slot. Counting "15 creatures" is a fatal trap if five of them cost 5 mana.

- **Velocity Target:** 7+ "Early Plays" (CMC <= 2 Creatures or premium Interaction).
- **Hunger Formula:** The engine projects your final 2-drop count based on `(Current Early Plays) * (45 / Picks_Made)`.
- **Panic Mode:** If `Projected < 7` entering Pack 2, 2-drops receive up to a `1.5x` score multiplier.
- **Top-Heavy Penalty:** If you have 4+ cards costing 5+ mana, future expensive cards receive a severe `0.7x` dampening multiplier, regardless of their GIHWR.

## 4. Signal Capitalization (Draft Navigation)

The engine reads signals in Pack 1 to gently push you into open colors.

- **Trigger:** Pack 1, Pick 5+.
- **Math:** `Lateness = Current Pick - ALSA`.
- **Application:** If a card with a positive Z-Score (above average) has a `Lateness >= 2.0`, it receives a flat point bonus equal to `Lateness * Z-Score * 3.0`.
- **Effect:** Seeing a great card at pick 7 that normally goes at pick 3 temporarily overrides the "Alien Gold/Off-Color" penalties, suggesting a strategic pivot.

## 5. True Bomb Detection (IWD Injection)

A high Win-Rate doesn't mean a card is a bomb (e.g., strong 1-drops have high WR but don't win the game alone).

- **Logic:** If a card's Z-Score is `> 1.0` AND its Improvement When Drawn (IWD) is `> 4.5%`, its power bonus is multiplied by `1.15x`.
- **Effect:** Distinguishes between "Great Filler" and "Cards you should abandon your current draft lane to play."

## 6. The Archetype Delta (Synergy Engine)

Cards are evaluated not just globally, but relative to how they perform in your specific lane.

- **Delta Math:** `Archetype_GIHWR - Global_GIHWR`
- **Synergy Payoff:** If a card performs > 2.0% better in your specific color pair than the average, it receives a heavy point bonus.
- **Archetype Trap:** If a globally "Good" card performs significantly worse in your established archetype, its score is heavily penalized.

## 7. Interaction Quotas & Diminishing Returns

The app parses card oracle text to understand the mechanical role of a card, preventing deck saturation.

- **Hard Removal Quota:** The engine actively searches for text like `"destroy target"`, `"exile target"`, or `"damage to target"`. If the pool has fewer than 3 removal spells in Pack 2/3, interaction cards receive a `1.3x` panic multiplier.
- **Diminishing Returns:** Auras, Equipment, and Combat Tricks (parsed via text) receive a strict `0.5x` penalty if the pool already contains 3 or more of them, preventing the drafting of "All tricks, no creatures" decks.

## 8. Premium Fixing Speculation

- **Pack 1:** Dual lands automatically receive a 1.15x multiplier to encourage staying open.
- **Splash Enablers:** If the user drafted a high Z-score bomb early but abandoned its color, the engine logs it as a "Splash Target". Any lands drafted later that produce that color receive a 1.3x multiplier to actively fix the mana base for the abandoned bomb.

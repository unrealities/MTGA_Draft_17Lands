"""
src/advisor/engine.py
Decision Engine.
Implements 0-100 Normalized Scoring, Lane Commitment, Structural Hunger,
and Smart Splash Detection based on pip density.
"""

import statistics
import logging
import re
from typing import List, Dict, Any, Tuple
from src.advisor.schema import Recommendation
from src import constants

logger = logging.getLogger(__name__)


class DraftAdvisor:
    # Professional Targets
    TARGET_CREATURES = 16
    TARGET_REMOVAL = 5
    TARGET_LANDS = 17

    # Thresholds
    BOMB_Z_THRESHOLD = 1.5
    MIN_GAMES_PLAYED = 500

    def __init__(self, set_metrics, taken_cards: List[Dict]):
        self.metrics = set_metrics
        self.pool = taken_cards
        self.pool_metrics = self._analyze_pool()
        self.active_colors = self._identify_main_colors()
        self.fixing_sources = self._count_fixing()

    def evaluate_pack(
        self, pack_cards: List[Dict], current_pick: int
    ) -> List[Recommendation]:
        if not pack_cards:
            return []

        # 1. Pack Statistics for Z-Score
        # Filter out basic lands and very low sample cards from the math to prevent skew
        valid_wrs = []
        for c in pack_cards:
            stats = c.get("deck_colors", {}).get("All Decks", {})
            gihwr = float(stats.get("gihwr", 0.0))
            if gihwr > 0:
                valid_wrs.append(gihwr)

        pack_mean = statistics.mean(valid_wrs) if valid_wrs else 54.0
        pack_std = statistics.pstdev(valid_wrs) if len(valid_wrs) > 1 else 2.0

        recommendations = []
        for card in pack_cards:
            name = card.get("name", "Unknown")
            stats = card.get("deck_colors", {})

            # --- FACTOR 1: Base Quality (Normalized 0-100) ---
            # We map 45% WR to 0 and 65% WR to 100. Clamped.
            base_wr = stats.get("All Decks", {}).get("gihwr", 0.0)
            if base_wr == 0.0:
                # No data available
                recommendations.append(
                    Recommendation(
                        card_name=name,
                        base_win_rate=0.0,
                        contextual_score=0.0,
                        z_score=0.0,
                        reasoning=["Insufficient Data"],
                    )
                )
                continue

            quality_score = max(0, min(100, (base_wr - 45) * 5))

            # --- FACTOR 2: Power Delta (The Z-Score) ---
            z_score = (base_wr - pack_mean) / pack_std if pack_std > 0 else 0
            power_bonus = max(0, z_score * 15) if z_score > 0.5 else 0

            # --- FACTOR 3: Lane Commitment (The Sinker) ---
            color_multiplier, color_reason = self._calculate_color_multiplier(
                card, current_pick, z_score
            )

            # --- FACTOR 4: Structural Hunger (The Fixer) ---
            hunger_multiplier, hunger_reasons = self._calculate_structural_multipliers(
                card, current_pick
            )

            # FINAL CALCULATION (0-100 Scale)
            final_score = (
                (quality_score + power_bonus) * color_multiplier * hunger_multiplier
            )

            # Clamp to 0-100
            final_score = max(0, min(100, final_score))

            all_reasons = []
            if color_reason:
                all_reasons.append(color_reason)
            all_reasons.extend(hunger_reasons)

            recommendations.append(
                Recommendation(
                    card_name=name,
                    base_win_rate=base_wr,
                    contextual_score=round(final_score, 1),
                    z_score=round(z_score, 2),
                    reasoning=all_reasons,
                    is_elite=(z_score >= 1.5),
                    archetype_fit="Neutral",
                )
            )

        return sorted(recommendations, key=lambda x: x.contextual_score, reverse=True)

    def _calculate_color_multiplier(
        self, card: Dict, pick: int, z_score: float
    ) -> Tuple[float, str]:
        """
        Determines the penalty for off-color cards based on:
        1. Draft Phase (Speculation vs Locked)
        2. Pip Density (Splashability)
        3. Power Level (Is it worth the splash?)
        """
        card_colors = set(card.get("colors", []))

        # Colorless / Artifacts -> Always open
        if not card_colors:
            return 1.0, ""

        # Identify overlap with our main colors
        is_on_color = any(c in self.active_colors for c in card_colors)

        # Exact match bonus (e.g. Card is UR, we are UR)
        if is_on_color:
            # If multi-color, check if we can cast both
            if len(card_colors) > 1 and not card_colors.issubset(
                set(self.active_colors)
            ):
                # We are Red, Card is Red/Blue. It's speculative but playable.
                if pick > 20:
                    return 0.5, "Hard Cast Risk"
                return 0.9, "Pivot Potential"
            return 1.1, ""  # Small bonus for being perfectly on-lane

        # --- OFF COLOR LOGIC ---

        # Phase 1: Speculation (Pick 1-5)
        # We are barely committed. Take the best cards.
        if pick <= 5:
            return 0.9, ""

        # Phase 2: Establishment (Pick 6 - Pick 20)
        # We are forming a lane. Off-color needs to be good.
        if pick <= 20:
            if z_score > 1.0:
                return 0.8, "Speculative Pivot"
            return 0.4, "Off-Color"

        # Phase 3: Commitment (Pick 21+)
        # We are locked. Only bombs or simple splashes.

        # SPLASH CHECK
        mana_cost = card.get("mana_cost", "")
        # Count colored pips (e.g., "{1}{R}{R}" -> 2)
        pip_count = sum(1 for c in mana_cost if c in "WUBRG")

        is_bomb = z_score >= self.BOMB_Z_THRESHOLD

        # Condition A: Bomb Rare, Single Pip (Easy Splash)
        if is_bomb and pip_count <= 1:
            # If we have fixing, it's very playable. If not, it's risky but possible.
            return 0.7, "Splashable Bomb"

        # Condition B: Bomb Rare, Double Pip (Hard Splash)
        if is_bomb and pip_count > 1:
            if self.fixing_sources >= 3:
                return 0.4, "Risky Splash (Double Pip)"
            return 0.1, "Uncastable Bomb"

        # Condition C: Average off-color card
        return 0.05, "Off-Color"

    def _calculate_structural_multipliers(
        self, card: Dict, pick: int
    ) -> Tuple[float, List[str]]:
        multiplier = 1.0
        reasons = []
        types = card.get("types", [])
        cmc = int(card.get("cmc", 0))

        total_picks = 45  # 3 packs * 15 cards
        progress = pick / total_picks

        # 1. Creature Hunger
        if "Creature" in types:
            # We want ~15-17 creatures.
            # If we are 60% through draft but only have 20% of creatures, panic.
            expected_creatures = progress * self.TARGET_CREATURES
            if self.pool_metrics["creature_count"] < expected_creatures - 2:
                multiplier += 0.25
                reasons.append("Need Creatures")

            # Curve Logic: 2-Drops
            if cmc == 2 and self.pool_metrics["curve"].get(2, 0) < 3 and pick > 20:
                multiplier += 0.2
                reasons.append("Fill Curve (2-Drop)")

        # 2. Interaction Hunger
        if any(t in types for t in ["Instant", "Sorcery", "Enchantment"]):
            # Simple heuristic for removal detection (not perfect, but effective)
            # We assume most high-rated spells are interaction
            if (
                self.pool_metrics["interaction_count"] < self.TARGET_REMOVAL
                and pick > 15
            ):
                multiplier += 0.2
                reasons.append("Need Interaction")

        # 3. Curve Satiety (Top End)
        if cmc >= 5:
            top_end_count = sum(
                v for k, v in self.pool_metrics["curve"].items() if k >= 5
            )
            if top_end_count >= 4:
                multiplier -= 0.3
                reasons.append("Curve Too High")

        # 4. Land/Fixing Hunger
        if "Land" in types:
            # If card is a dual land
            if any(
                c in "WUBRG" for c in card.get("colors", [])
            ) or "Common" in card.get("rarity", ""):
                if pick > 20 and self.fixing_sources < 3:
                    multiplier += 0.15
                    reasons.append("Fixing Needed")

        return multiplier, reasons

    def _identify_main_colors(self) -> List[str]:
        """Identifies the 2 colors with the most weight in the pool."""
        weights = self.pool_metrics["color_weights"]
        sorted_colors = sorted(weights.items(), key=lambda x: x[1], reverse=True)

        # If we are early (Pick < 5) or have no cards, we might not have 'main' colors yet
        # Require at least 2 cards in a color to consider it 'Active' to reduce noise
        valid_colors = [c[0] for c in sorted_colors if c[1] >= 2]

        return valid_colors[:2]

    def _count_fixing(self) -> int:
        """Counts lands/artifacts that produce mana."""
        count = 0
        for c in self.pool:
            t = c.get("types", [])
            # Heuristic: Lands and Artifacts usually provide fixing in draft
            if "Land" in t or "Artifact" in t:
                # Check if it produces mana (very rough heuristic based on text usually found in name/type)
                # In robust implementation, we would need rules text parsing or specific IDs
                if "Land" in t and "Basic" not in t:
                    count += 1
                elif "Artifact" in t and c.get("cmc", 0) <= 3:  # Mana rocks
                    count += 1
        return count

    def _analyze_pool(self) -> Dict[str, Any]:
        curve = {}
        creature_count = 0
        interaction_count = 0
        weights = {c: 0 for c in constants.CARD_COLORS}

        for c in self.pool:
            cmc = int(c.get("cmc", 0))
            curve[cmc] = curve.get(cmc, 0) + 1

            t = c.get("types", [])
            if "Creature" in t:
                creature_count += 1

            # Simple heuristic for interaction based on type
            if "Instant" in t or "Sorcery" in t:
                interaction_count += 1

            for color in c.get("colors", []):
                if color in weights:
                    weights[color] += 1

        return {
            "curve": curve,
            "creature_count": creature_count,
            "interaction_count": interaction_count,
            "color_weights": weights,
        }

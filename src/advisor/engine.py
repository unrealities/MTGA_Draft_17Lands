"""
src/advisor/engine.py
The Professional Decision Engine.
Implements 0-100 Normalized Scoring, Lane Commitment, and Structural Hunger.
"""

import statistics
import logging
from typing import List, Dict, Any, Tuple
from src.advisor.schema import Recommendation
from src import constants

logger = logging.getLogger(__name__)


class DraftAdvisor:
    # Professional Targets
    TARGET_CREATURES = 16
    TARGET_REMOVAL = 6
    BOMB_Z_THRESHOLD = 2.0  # Statistical outlier

    def __init__(self, set_metrics, taken_cards: List[Dict]):
        self.metrics = set_metrics
        self.pool = taken_cards
        self.pool_metrics = self._analyze_pool()
        self.active_colors = self._identify_main_colors()

    def evaluate_pack(
        self, pack_cards: List[Dict], current_pick: int
    ) -> List[Recommendation]:
        if not pack_cards:
            return []

        # 1. Pack Statistics for Z-Score
        all_wrs = [
            float(c.get("deck_colors", {}).get("All Decks", {}).get("gihwr", 0.0))
            for c in pack_cards
        ]
        pack_mean = statistics.mean(all_wrs) if all_wrs else 54.0
        pack_std = statistics.pstdev(all_wrs) if len(all_wrs) > 1 else 2.0

        recommendations = []
        for card in pack_cards:
            name = card.get("name", "Unknown")
            stats = card.get("deck_colors", {})

            # --- FACTOR 1: Base Quality (Normalized 0-100) ---
            # We map 45% WR to 0 and 65% WR to 100
            base_wr = stats.get("All Decks", {}).get("gihwr", 0.0)
            quality_score = max(0, min(100, (base_wr - 45) * 5))

            # --- FACTOR 2: Power Delta (The Z-Score) ---
            z_score = (base_wr - pack_mean) / pack_std if pack_std > 0 else 0
            # A Z-score of 2.0+ (Bomb) provides a massive boost to the base score
            power_bonus = max(0, z_score * 15) if z_score > 1.0 else 0

            # --- FACTOR 3: Lane Commitment (The Sinker) ---
            color_multiplier = self._calculate_color_multiplier(
                card, current_pick, z_score
            )

            # --- FACTOR 4: Structural Hunger (The Multiplier) ---
            hunger_multiplier, reasons = self._calculate_structural_multipliers(
                card, current_pick
            )

            # FINAL CALCULATION (0-100 Scale)
            # We blend Quality, Power, and Context
            final_score = (
                (quality_score + power_bonus) * color_multiplier * hunger_multiplier
            )

            # Clamp to 0-100
            final_score = max(0, min(100, final_score))

            recommendations.append(
                Recommendation(
                    card_name=name,
                    base_win_rate=base_wr,
                    contextual_score=round(final_score, 1),
                    z_score=round(z_score, 2),
                    reasoning=reasons,
                    is_elite=(z_score >= 1.5),
                    archetype_fit="Neutral",  # Phase 2 integration
                )
            )

        return sorted(recommendations, key=lambda x: x.contextual_score, reverse=True)

    def _calculate_color_multiplier(
        self, card: Dict, pick: int, z_score: float
    ) -> float:
        """Sinks off-color cards as the draft progresses."""
        card_colors = set(card.get("colors", []))
        if not card_colors:
            return 1.0  # Colorless

        # P1P1-P1P7: We stay open. No penalty.
        if pick <= 7:
            return 1.0

        # Check if the card matches our top colors
        is_on_color = any(c in self.active_colors for c in card_colors)

        # BOMB EXCEPTION: If the card is an outlier, we reduce the penalty significantly
        # because the card might justify a pivot.
        if z_score > self.BOMB_Z_THRESHOLD:
            return 0.9 if pick < 25 else 0.5

        if is_on_color:
            return 1.1  # Small bonus for being in-lane

        # Lane Commitment Penalty
        if pick <= 14:
            return 0.7  # End of Pack 1: Sinking
        if pick <= 28:
            return 0.3  # Pack 2: Committed
        return 0.05  # Pack 3: Hard lock. Off-color is a 0.

    def _calculate_structural_multipliers(
        self, card: Dict, pick: int
    ) -> Tuple[float, List[str]]:
        multiplier = 1.0
        reasons = []
        types = card.get("types", [])
        cmc = int(card.get("cmc", 0))

        # 1. Creature Hunger
        if "Creature" in types:
            # We expect roughly 40% of our pool to be creatures at any time
            expected_creatures = (pick / 40) * self.TARGET_CREATURES
            if self.pool_metrics["creature_count"] < expected_creatures:
                multiplier += 0.2
                reasons.append("Structural Need: Creatures")

            if cmc == 2 and self.pool_metrics["curve"].get(2, 0) < 3 and pick > 10:
                multiplier += 0.15
                reasons.append("Curve Fill: 2-Drops")

        # 2. Interaction Hunger
        if any(t in types for t in ["Instant", "Sorcery"]):
            if self.pool_metrics["interaction_count"] < 2 and pick > 15:
                multiplier += 0.3
                reasons.append("Critical Removal Need")

        # 3. Curve Satiety
        if cmc >= 5 and self.pool_metrics["curve"].get(5, 0) > 4:
            multiplier -= 0.2
            reasons.append("Curve Risk: Excessive Top-end")

        return multiplier, reasons

    def _identify_main_colors(self) -> List[str]:
        """Identifies the 2 colors with the most weight in the pool."""
        weights = self.pool_metrics["color_weights"]
        sorted_colors = sorted(weights.items(), key=lambda x: x[1], reverse=True)
        return [c[0] for c in sorted_colors[:2]] if sorted_colors else []

    def _analyze_pool(self) -> Dict[str, Any]:
        curve = {}
        creature_count = 0
        interaction_count = 0
        weights = {c: 0 for c in constants.CARD_COLORS}

        for c in self.pool:
            cmc = int(c.get("cmc", 0))
            curve[cmc] = curve.get(cmc, 0) + 1
            if "Creature" in c.get("types", []):
                creature_count += 1
            if any(t in c.get("types", []) for t in ["Instant", "Sorcery"]):
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

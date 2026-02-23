"""
src/advisor/engine.py
Decision Engine v4.0
Implements Compositional Math, Relative Pack Strength, and Alien Gold Protection.
"""

import statistics
import logging
import math
from typing import List, Dict, Any, Tuple
from src.advisor.schema import Recommendation
from src import constants
from src.card_logic import count_fixing

logger = logging.getLogger(__name__)


class DraftAdvisor:
    # --- Configuration Constants ---
    TOTAL_PICKS = 45

    # Ideal Composition (Based on 23 spells)
    TARGET_CREATURES = 15
    TARGET_INTERACTION = 6

    # Thresholds
    BOMB_Z_SCORE = 2.0

    def __init__(self, set_metrics, taken_cards: List[Dict]):
        self.metrics = set_metrics
        self.pool = taken_cards

        # Base stats
        self.global_mean, self.global_std = self.metrics.get_metrics(
            "All Decks", "gihwr"
        )
        if self.global_mean == 0.0:
            self.global_mean = 54.0
        if self.global_std == 0.0:
            self.global_std = 4.0

        # 1. Calculate Fixing First (Dependency for _analyze_pool)
        self.fixing_map = count_fixing(self.pool)

        # 2. Analyze Pool Metrics (Curve, Counts, etc.)
        self.pool_metrics = self._analyze_pool()

        # 3. Determine our "Lane" (Top 2 Colors weighted by card quality)
        self.main_colors = self._identify_main_colors()
        self.main_archetype = (
            "".join(sorted(self.main_colors)) if self.main_colors else "All Decks"
        )
        self.active_colors = self.main_colors  # For consistency with v3 logic

    def evaluate_pack(
        self, pack_cards: List[Dict], current_pick: int
    ) -> List[Recommendation]:
        if not pack_cards:
            return []

        # 1. Derive Context
        pack_number = math.ceil(current_pick / 15) if current_pick > 0 else 1
        draft_progress = min(1.0, current_pick / self.TOTAL_PICKS)

        # 2. Pre-Calculate Pack Power Ranks (For Relative Wheel Logic)
        # We need to know if a card is the 2nd best or 9th best in the pack
        pack_cards_sorted = sorted(
            pack_cards,
            key=lambda c: float(
                c.get("deck_colors", {}).get("All Decks", {}).get("gihwr", 0.0)
            ),
            reverse=True,
        )
        # Map Card Name -> Rank (0 is best)
        pack_ranks = {c.get("name"): i for i, c in enumerate(pack_cards_sorted)}

        # 3. Calculate Pack Statistics for Z-Score
        pack_wrs = [
            float(c.get("deck_colors", {}).get("All Decks", {}).get("gihwr", 0.0))
            for c in pack_cards
        ]
        valid_wrs = [x for x in pack_wrs if x > 0]
        pack_mean = statistics.mean(valid_wrs) if valid_wrs else self.global_mean
        pack_std = (
            statistics.pstdev(valid_wrs) if len(valid_wrs) > 1 else self.global_std
        )
        if pack_std == 0.0:
            pack_std = self.global_std

        recommendations = []

        for card in pack_cards:
            name = card.get("name", "Unknown")

            # --- STEP 1: Archetype Weighted Scoring ---
            base_score = self._calculate_weighted_score(card, draft_progress)

            # --- STEP 2: Power Bonus (Z-Score) ---
            raw_gihwr = float(
                card.get("deck_colors", {}).get("All Decks", {}).get("gihwr", 0.0)
            )
            z_score = (raw_gihwr - pack_mean) / pack_std if pack_std > 0 else 0
            power_bonus = max(0, z_score * 10) if z_score > 0.5 else 0

            # --- STEP 3: Mana Analysis & Alien Protection (v4) ---
            cast_mult, cast_reason = self._calculate_castability_v4(
                card, pack_number, current_pick, z_score
            )

            # --- STEP 4: Compositional Math (v4) ---
            # Formulaic adjustment for Creatures vs Spells
            role_mult, role_reason = self._calculate_composition_bonus(
                card, pack_number
            )

            # --- STEP 5: Relative Wheel Strength (v4.2) ---
            rank_in_pack = pack_ranks.get(name, 99)
            wheel_mult, wheel_alert, wheel_pct = self._check_relative_wheel(
                card, current_pick, rank_in_pack
            )

            # === MASTER FORMULA ===
            raw_score = base_score + power_bonus
            final_score = raw_score * cast_mult * role_mult * wheel_mult

            # Clamp to 0-100
            final_score = max(0, min(100, final_score))

            # Compile Reasoning
            reasons = []
            if cast_reason:
                reasons.append(cast_reason)
            if role_reason:
                reasons.append(role_reason)
            if wheel_alert:
                reasons.append(f"Rank #{rank_in_pack + 1} in Pack (May Wheel)")
            if z_score >= self.BOMB_Z_SCORE:
                reasons.append("BOMB")

            recommendations.append(
                Recommendation(
                    card_name=name,
                    base_win_rate=raw_gihwr,
                    contextual_score=round(final_score, 1),
                    z_score=round(z_score, 2),
                    cast_probability=cast_mult,
                    wheel_chance=wheel_pct,
                    functional_cmc=self._get_functional_cmc(card),
                    reasoning=reasons,
                    is_elite=(z_score >= 1.5),
                    archetype_fit=(
                        "/".join(self.main_colors) if self.main_colors else "Open"
                    ),
                )
            )

        return sorted(recommendations, key=lambda x: x.contextual_score, reverse=True)

    def _calculate_weighted_score(self, card: Dict, progress: float) -> float:
        """Blends Global WR with Archetype WR."""
        stats = card.get("deck_colors", {})
        global_wr = float(stats.get("All Decks", {}).get("gihwr", 0.0))

        # Determine archetype key. If we are "Open", use Global.
        arch_key = self.main_archetype if self.main_colors else "All Decks"
        arch_wr = float(stats.get(arch_key, {}).get("gihwr", global_wr))
        if arch_wr == 0.0:
            arch_wr = global_wr

        # Sigmoid-like blend: Commit harder to archetype data later in draft
        expected_wr = (global_wr * (1.0 - progress)) + (arch_wr * progress)

        # Scale dynamically based on set average and standard deviation
        score = 50.0 + ((expected_wr - self.global_mean) / self.global_std) * 12.5
        return max(0.0, min(100.0, score))

    def _calculate_castability_v4(
        self, card: Dict, pack: int, pick: int, z_score: float
    ) -> Tuple[float, str]:
        """
        v4 Logic: Alien Gold Protection & Flexible Splashing.
        """
        mana_cost = card.get("mana_cost", "")
        if not mana_cost:
            return 1.0, ""

        card_colors = set(card.get("colors", []))
        is_on_color = any(c in self.main_colors for c in card_colors)

        # --- 1. EARLY SPECULATION (PACK 1) ---
        # Do not eliminate cards early in the draft. Allow pivoting.
        if pack == 1 and pick <= 6:
            if is_on_color:
                return 1.0, ""
            # Penalize slightly so on-color cards win ties, but bombs survive
            if len(card_colors) > 1:
                return 0.8, "Speculative (Gold)"
            return 0.9, "Speculative"

        # --- 2. ALIEN GOLD CHECK (Hard Constraint) ---
        if len(card_colors) > 1 and not is_on_color and self.main_colors:
            # Exception: 5-color soup fixing available
            if (
                len(self.main_colors) >= 2
                and self.pool_metrics.get("fixing_count", 0) < 4
            ):
                return 0.0, "Alien Gold (Uncastable)"

        # --- 3. ON-COLOR ---
        if is_on_color:
            return 1.0, ""

        # --- PRE-CALCULATE FIXING ---
        pips = sum(1 for char in mana_cost if char in "WUBRG")
        splash_colors = [c for c in card_colors if c not in self.main_colors]
        fixing_available = 0
        if splash_colors:
            sources = [self.fixing_map.get(c, 0) for c in splash_colors]
            fixing_available = min(sources) + 1

        # --- 4. PACK 2+ DISCIPLINE ---
        if pack >= 2:
            if fixing_available <= 1:
                if z_score >= self.BOMB_Z_SCORE:
                    return 0.7, "Bomb (Need Fixing)"
                return 0.2, "Off-Color"

        # --- 5. SPLASH ANALYSIS ---
        if z_score >= self.BOMB_Z_SCORE and pips == 1:
            if fixing_available >= 2:
                return 0.85, "Bomb Splash"
            else:
                return 0.5, "Bomb (Needs Fixing)"

        if pips == 1:
            if fixing_available >= 3:
                return 0.8, "Splashable"
            if fixing_available >= 2:
                return 0.6, "Risky Splash"
            return 0.2, "No Fixing"

        return 0.1, "Uncastable (Double Pip)"

    def _calculate_composition_bonus(self, card: Dict, pack: int) -> Tuple[float, str]:
        """
        v4 Logic: Formulaic Role Balancing.
        Uses a supply/demand ratio to curve scores rather than strict cutoffs.
        """
        types = card.get("types", [])
        if "Land" in types:
            return 1.0, ""

        # 1. Creature Calculation
        if "Creature" in types:
            current = self.pool_metrics["creature_count"]
            # Projected finish based on draft progress (e.g. at 50% draft, projected = current * 2)
            # We add a buffer to pick number to avoid divide by zero/huge multipliers early
            picks_made = len(self.pool) + 1
            projected = current * (self.TOTAL_PICKS / picks_made)

            # Ratio < 1.0 means we are behind schedule
            ratio = projected / self.TARGET_CREATURES

            if ratio < 0.8 and pack >= 2:
                # We are behind. Boost creatures.
                # Formula: 1.0 + (Inverse of Ratio scaled)
                bonus = 1.0 + (0.8 - ratio)
                return min(1.4, bonus), "Need Creatures"

            if ratio > 1.4:
                # We have too many. Dampen.
                penalty = 1.0 - ((ratio - 1.4) * 0.5)
                return max(0.6, penalty), "Creature Saturation"

        # 2. Interaction/Spells Calculation
        if "Instant" in types or "Sorcery" in types:
            current = self.pool_metrics["interaction_count"]
            # Interaction often has diminishing returns faster
            if current >= self.TARGET_INTERACTION and pack >= 2:
                # Slight dampening
                return 0.9, "Interaction Satiated"

        return 1.0, ""

    def _check_relative_wheel(
        self, card: Dict, pick: int, rank_in_pack: int
    ) -> Tuple[float, str, float]:
        """
        v4.2 Logic: Polynomial Wheel Math + Contextual Pack Texture.
        Returns: (Score Multiplier, Reason String, Wheel Percentage)
        """
        if pick >= 9:
            return 1.0, "", 0.0  # Impossible to wheel if we are already wheeling

        stats = card.get("deck_colors", {}).get("All Decks", {})
        alsa = float(stats.get("alsa", 0.0))

        if alsa == 0.0 or alsa <= pick:
            return 1.0, "", 0.0

        # 1. Base Probability using Historical Polynomial Curves
        import numpy as np

        # The coefficients matrix only covers up to Pick 6 (index 5)
        pick_idx = min(pick - 1, 5)
        coeffs = constants.WHEEL_COEFFICIENTS[pick_idx]
        base_prob = float(np.polyval(coeffs, alsa))

        # 2. Contextual Adjustment (Pack Texture)
        # ALSA is an average. If this card is the absolute best card in THIS specific pack,
        # it doesn't matter what its ALSA is, the next player will take it.
        context_prob = base_prob
        if rank_in_pack == 0:  # #1 Card in pack
            context_prob *= 0.10
        elif rank_in_pack <= 2:  # #2 or #3 Card
            context_prob *= 0.40
        elif rank_in_pack >= 8:  # Bottom half of pack (Nobody wants this)
            context_prob = min(100.0, context_prob * 1.25)

        final_prob = max(0.0, min(100.0, context_prob))

        # 3. Score Modification (Greed Engine)
        # If it has >75% chance to wheel, reduce its tactical score so the user takes something else now.
        if final_prob >= 75.0 and rank_in_pack >= 4:
            return 0.8, f"Wheels ~{final_prob:.0f}%", final_prob

        return 1.0, "", final_prob

    def _identify_main_colors(self) -> List[str]:
        """
        Identifies main colors based on 'Quality Weight'.
        """
        weights = {c: 0.0 for c in constants.CARD_COLORS}
        playable_threshold = self.global_mean - self.global_std

        for c in self.pool:
            wr = float(c.get("deck_colors", {}).get("All Decks", {}).get("gihwr", 0.0))
            if wr < playable_threshold:
                continue

            # Scale points dynamically. Average card = ~1 point. +1 std = ~3 points.
            points = max(0.2, 1.0 + 2.0 * ((wr - self.global_mean) / self.global_std))

            for color in c.get("colors", []):
                if color in weights:
                    weights[color] += points

        sorted_colors = sorted(weights.items(), key=lambda x: x[1], reverse=True)
        # Return top 2 if they have significant weight (> 2.0 points)
        return [c[0] for c in sorted_colors[:2] if c[1] >= 2.0]

    def _get_functional_cmc(self, card: Dict) -> int:
        raw_cmc = int(card.get("cmc", 0))
        text = card.get("text", "").lower() if "text" in card else ""
        if "landcycling" in text:
            return 1
        return raw_cmc

    def _analyze_pool(self) -> Dict[str, Any]:
        curve = {}
        creature_count = 0
        interaction_count = 0

        for c in self.pool:
            cmc = self._get_functional_cmc(c)
            curve[cmc] = curve.get(cmc, 0) + 1

            t = c.get("types", [])
            if "Creature" in t:
                creature_count += 1
            if "Instant" in t or "Sorcery" in t:
                interaction_count += 1

        return {
            "curve": curve,
            "creature_count": creature_count,
            "interaction_count": interaction_count,
            "fixing_count": sum(self.fixing_map.values()),
        }

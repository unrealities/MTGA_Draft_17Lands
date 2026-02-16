"""
src/advisor/engine.py
Decision Engine.
Implements Context-Aware Scoring, Karsten Mana Analysis, and Wheel Prediction.
"""

import statistics
import logging
import re
from typing import List, Dict, Any, Tuple
from src.advisor.schema import Recommendation
from src import constants
from src.card_logic import count_fixing

logger = logging.getLogger(__name__)


class DraftAdvisor:
    # --- Configuration Constants ---
    TOTAL_PICKS = 45
    PACK_SIZE = 14  # Arena draft pack size

    # Karsten Math Targets (Sources needed for 90% consistency)
    SOURCES_NEEDED = {
        1: 9,  # 1 Pip needs 9 sources
        2: 14,  # 2 Pips needs 14 sources
        3: 18,  # 3 Pips needs 18 sources
    }

    def __init__(self, set_metrics, taken_cards: List[Dict]):
        self.metrics = set_metrics
        self.pool = taken_cards
        self.pool_metrics = self._analyze_pool()
        self.active_colors = self._identify_main_colors()
        self.fixing_map = count_fixing(self.pool)

        # Determine our "Lane" (Top 2 Colors)
        self.main_colors = self._identify_main_colors()

        # Count our fixing (Dual lands, treasures)
        self.fixing_count = self._count_fixing_sources()

    def evaluate_pack(
        self, pack_cards: List[Dict], current_pick: int
    ) -> List[Recommendation]:
        if not pack_cards:
            return []

        # 1. Calculate Pack Statistics for Z-Score (Relative Power)
        pack_wrs = [
            float(c.get("deck_colors", {}).get("All Decks", {}).get("gihwr", 0.0))
            for c in pack_cards
        ]
        # Remove zeros for cleaner stats
        valid_wrs = [x for x in pack_wrs if x > 0]
        pack_mean = statistics.mean(valid_wrs) if valid_wrs else 54.0
        pack_std = statistics.pstdev(valid_wrs) if len(valid_wrs) > 1 else 2.0

        recommendations = []

        # Calculate Draft Progress (0.0 to 1.0)
        draft_progress = min(1.0, len(self.pool) / self.TOTAL_PICKS)

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

            # --- STEP 3: Mana Analysis (Karsten Probability) ---
            cast_prob, cast_reason = self._calculate_castability(card, current_pick)

            # --- STEP 4: Structural Hunger ---
            curve_mult, curve_reason = self._calculate_curve_fit(card)

            # --- STEP 5: Wheel Greed (Probability) ---
            wheel_mult, wheel_alert = self._check_wheel_probability(card, current_pick)

            # === MASTER FORMULA ===
            # (Base + Power) * Castability * Curve * WheelGreed

            raw_score = base_score + power_bonus

            final_score = raw_score * cast_prob * curve_mult * wheel_mult

            # Clamp to 0-100
            final_score = max(0, min(100, final_score))

            # Compile Reasoning
            reasons = []
            if cast_reason:
                reasons.append(cast_reason)
            if curve_reason:
                reasons.append(curve_reason)
            if wheel_alert:
                reasons.append("High Wheel Chance")
            if z_score >= 2.0:
                reasons.append("BOMB")

            # Determine Functional CMC for UI
            func_cmc = self._get_functional_cmc(card)

            recommendations.append(
                Recommendation(
                    card_name=name,
                    base_win_rate=raw_gihwr,
                    contextual_score=round(final_score, 1),
                    z_score=round(z_score, 2),
                    cast_probability=cast_prob,
                    wheel_chance=(wheel_mult < 1.0),
                    functional_cmc=func_cmc,
                    reasoning=reasons,
                    is_elite=(z_score >= 1.5),
                    archetype_fit=(
                        "/".join(self.main_colors) if self.main_colors else "Open"
                    ),
                )
            )

        # Sort by the final contextual score
        return sorted(recommendations, key=lambda x: x.contextual_score, reverse=True)

    def _calculate_weighted_score(self, card: Dict, progress: float) -> float:
        """
        Blends Global WR with Archetype WR based on draft progress.
        Early draft = Global matters. Late draft = Archetype matters.
        """
        stats = card.get("deck_colors", {})

        # Global Stats
        global_wr = float(stats.get("All Decks", {}).get("gihwr", 0.0))

        # Archetype Stats (e.g., "UB")
        # We define our archetype string (e.g., "UB") based on main colors
        archetype_key = (
            "".join(sorted(self.main_colors)) if self.main_colors else "All Decks"
        )

        # Fallback to Global if no data for archetype
        arch_wr = float(stats.get(archetype_key, {}).get("gihwr", global_wr))
        if arch_wr == 0.0:
            arch_wr = global_wr

        # The Blend
        # Example: Pick 22 (50% progress). Score is 50% global, 50% archetype.
        expected_wr = (global_wr * (1.0 - progress)) + (arch_wr * progress)

        # Normalize to 0-100 (45% -> 0, 65% -> 100)
        return max(0, min(100, (expected_wr - 45) * 5))

    def _calculate_castability(self, card: Dict, pick: int) -> Tuple[float, str]:
        """
        Calculates the score multiplier based on how hard the card is to cast.

        Logic:
        1. On-Color: 1.0x (No penalty).
        2. Speculation Phase (Pick <= 5): 0.95x (Low penalty).
        3. Splash Logic:
           - Single Pip: Check fixing map for specific color support.
           - Double Pip: Hard Lock (0.0x) unless excessive fixing exists.
        """
        mana_cost = card.get("mana_cost", "")
        if not mana_cost:
            return 1.0, ""  # Lands/Colorless

        card_colors = set(card.get("colors", []))

        # 1. On-Color Check
        # If the card matches our main colors, we assume 1.0 (we will build a mana base for it)
        is_main_color = any(c in self.main_colors for c in card_colors)

        # If card is multi-color (e.g. WB) and we are WB, it's 1.0.
        # If card is WB and we are W (Open), it's 1.0.
        # If card is WB and we are WR, it's technically a splash for B, but often treated as on-color pivot.
        if is_main_color:
            return 1.0, ""

        # 2. Speculation Phase Exception (Picks 1-5)
        # We don't punish off-color early because we might pivot.
        if pick <= 5:
            return 0.95, ""

        # 3. Splash Logic (The Pro Logic)

        # Count Pips (e.g. "{1}{R}{R}" has 2 Red Pips)
        pips = sum(1 for char in mana_cost if char in "WUBRG")

        # Identify the specific colors we need to splash
        # e.g., We are Green. Card is Red/Green. We need Red fixing.
        splash_colors = [c for c in card_colors if c not in self.active_colors]

        # Calculate total fixing sources available for the required splash color(s)
        # If multiple colors needed (e.g. card is UR and we are G), we need fixing for both.
        # For scoring, we take the minimum fixing available across required colors (limiting factor).
        fixing_available = 0
        if splash_colors:
            # We add 1 to the count because we assume we can always add 1 Basic Land of that color
            # to the deck. So 2 Treasures + 1 Basic = 3 Sources.
            sources = [self.fixing_map.get(c, 0) + 1 for c in splash_colors]
            fixing_available = min(sources)

        # Logic for Single Pip Splash (e.g. {2}{R})
        if pips == 1:
            # Pro Rule: You want at least 3 sources for a consistently castable splash card.
            if fixing_available >= 3:
                return 0.8, "Splashable (Fixing Available)"
            # If we have some fixing (e.g. 1 treasure + 1 basic), it's risky but doable.
            elif fixing_available >= 2:
                return 0.6, "Risky Splash"
            else:
                return 0.4, "No Fixing Sources"

        # Logic for Double Pip (e.g. {2}{R}{R})
        # Generally uncastable as a splash.
        if pips >= 2:
            # Exception: Treasure heavy pool (Fixing > 4) implies we are playing 5-color soup
            if fixing_available >= 5:
                return 0.4, "Deep Splash (Heavy Fixing)"
            return 0.05, "Uncastable (Double Pip)"

        # Fallback
        return 0.5, "Off-Color"

    def _calculate_curve_fit(self, card: Dict) -> Tuple[float, str]:
        """Adjusts score based on functional CMC and current curve gaps."""
        cmc = self._get_functional_cmc(card)

        # Hunger: 2-Drops
        # If we have few 2-drops, boost them.
        two_drop_count = self.pool_metrics["curve"].get(2, 0)
        if cmc == 2 and two_drop_count < 4:
            return 1.15, "Fill Curve (2-Drop)"

        # Satiety: Top End (5+)
        # If we have too many big spells, penalize hard.
        top_end = sum(v for k, v in self.pool_metrics["curve"].items() if k >= 5)
        if cmc >= 5 and top_end >= 5:
            return 0.6, "Curve Too High"

        return 1.0, ""

    def _check_wheel_probability(
        self, card: Dict, current_pick: int
    ) -> Tuple[float, str]:
        """
        Determines if a card is likely to circle the table.
        If Pick 3 and ALSA is 12, we shouldn't take it now.
        """
        # Get Average Last Seen At (ALSA)
        alsa = float(card.get("deck_colors", {}).get("All Decks", {}).get("alsa", 0.0))

        if alsa == 0.0:
            return 1.0, ""

        # Logic: If current pick is 2, and ALSA is 11, it will likely be there at pick 10 (Wheel).
        # We define "Wheel Likely" if ALSA is > CurrentPick + 7 (Pack size ~14)
        if alsa > (current_pick + 7.0):
            # Penalty: Don't take it now, take the scarce card.
            return 0.8, "Likely to Wheel"

        return 1.0, ""

    def _get_functional_cmc(self, card: Dict) -> int:
        """
        Parses special mechanics to find the 'True' CMC.
        e.g., Basic Landcycling {1} makes a 6-drop functionally a 1-drop/Land.
        """
        raw_cmc = int(card.get("cmc", 0))
        text = card.get("text", "").lower() if "text" in card else ""

        # Simple heuristics for functional cost
        if "landcycling" in text:
            # It acts as a land tutor, effectively low CMC for curve considerations
            return 1

        # Adventures (This requires more complex parsing usually, but for now we trust base CMC
        # unless we have split card data structure available).

        return raw_cmc

    def _identify_main_colors(self) -> List[str]:
        weights = self.pool_metrics["color_weights"]
        # Sort colors by count desc
        sorted_colors = sorted(weights.items(), key=lambda x: x[1], reverse=True)
        # Return top 2 if they have significant cards
        return [c[0] for c in sorted_colors[:2] if c[1] >= 2]

    def _count_fixing_sources(self) -> int:
        count = 0
        for c in self.pool:
            if "Land" in c.get("types", []) and "Basic" not in c.get("types", []):
                count += 1
            if "Artifact" in c.get("types", []) and int(c.get("cmc", 0)) <= 3:
                # Mana rocks
                count += 1
        return count

    def _analyze_pool(self) -> Dict[str, Any]:
        curve = {}
        creature_count = 0
        interaction_count = 0
        weights = {c: 0 for c in constants.CARD_COLORS}

        for c in self.pool:
            cmc = self._get_functional_cmc(c)
            curve[cmc] = curve.get(cmc, 0) + 1

            t = c.get("types", [])
            if "Creature" in t:
                creature_count += 1
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

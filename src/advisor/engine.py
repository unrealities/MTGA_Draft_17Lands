"""
src/advisor/engine.py

================================================================================
The "Compositional Brain" (v5 Pro-Tour Architecture)
================================================================================
This engine moves beyond strict logic gates and raw win-rates. It evaluates a
draft pack through the lens of advanced Pro Tour draft theories:

1. Sunk Cost Evasion: Weights recent picks heavier than early picks to find the
   *true* open lane, quickly abandoning cut colors.
2. The 2-Drop Rule (Mana Velocity): Tracks low-curve plays rather than generic
   "creatures". Punishes top-heavy decks heavily.
3. The Interaction Quota: Identifies hard removal via Scryfall Oracle Tags and
   applies panic-multipliers if the deck lacks answers.
4. Signal Capitalization: Identifies high-quality cards passing late in Pack 1
   and mathematically encourages pivoting into open colors.
5. Archetype Synergy Delta: Detects if a card overperforms (Synergy) or
   underperforms (Trap) in our specific color pair relative to its global average.
6. Premium Fixing Speculation: Values dual lands highly in Pack 1, and heavily
   targets fixing for off-color bombs we already drafted (Splash Enablers).
================================================================================
"""

import statistics
import logging
import math
import numpy as np
from typing import List, Dict, Any, Tuple
from src.advisor.schema import Recommendation
from src import constants
from src.card_logic import count_fixing

logger = logging.getLogger(__name__)


class DraftAdvisor:
    # --- Configuration Constants ---
    TOTAL_PICKS = 45  # Required for draft progress math

    # --- Pro-Tour Composition Targets ---
    TARGET_EARLY_PLAYS = 7  # CMC 1-2 creatures or cheap interaction
    TARGET_HARD_REMOVAL = 3  # Minimum community-tagged removal spells required
    CAP_COMBAT_TRICKS = 3  # Diminishing returns threshold for community-tagged tricks
    TARGET_CARD_DRAW = 2  # Minimum sources of card advantage/smoothing
    TARGET_EVASION = 3  # Minimum stall-breakers (flyers, menace, etc.)

    # --- Power Thresholds ---
    BOMB_Z_SCORE = 1.5  # Z-Score indicating a true bomb
    IWD_PREMIUM_THRESHOLD = (
        4.5  # Improvement When Drawn % indicating game-altering impact
    )

    def __init__(self, set_metrics, taken_cards: List[Dict]):
        self.metrics = set_metrics
        self.pool = taken_cards

        # 1. Base statistical baselines
        self.global_mean, self.global_std = self.metrics.get_metrics(
            "All Decks", "gihwr"
        )
        if self.global_mean == 0.0:
            self.global_mean = 54.0
        if self.global_std == 0.0:
            self.global_std = 4.0

        # 2. Identify established lane (Using Recency Bias)
        self.main_colors = self._identify_main_colors()
        self.main_archetype = (
            "".join(sorted(self.main_colors[:2]))
            if len(self.main_colors) >= 2
            else "All Decks"
        )
        self.active_colors = self.main_colors  # For legacy v3 compatibility

        # 3. Analyze Pool Needs (Fixing, Curve, Removal, Splashes)
        self.fixing_map = count_fixing(self.pool)
        self.pool_metrics = self._analyze_pool()

    def evaluate_pack(
        self, pack_cards: List[Dict], current_pick: int
    ) -> List[Recommendation]:
        if not pack_cards:
            return []

        # Draft Context
        pack_number = math.ceil(current_pick / 15) if current_pick > 0 else 1
        draft_progress = min(1.0, current_pick / self.TOTAL_PICKS)

        # Pre-Calculate Pack Power Ranks (For Relative Wheel Logic)
        pack_cards_sorted = sorted(
            pack_cards,
            key=lambda c: float(
                c.get("deck_colors", {}).get("All Decks", {}).get("gihwr", 0.0)
            ),
            reverse=True,
        )
        pack_ranks = {c.get("name"): i for i, c in enumerate(pack_cards_sorted)}

        # Calculate Pack Statistics for Contextual Z-Score
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
            stats = card.get("deck_colors", {}).get("All Decks", {})
            raw_gihwr = float(stats.get("gihwr", 0.0))
            raw_iwd = float(stats.get("iwd", 0.0))
            alsa = float(stats.get("alsa", 0.0))

            reasons = []

            # --- STEP 1: Blended Base Score ---
            base_score = self._calculate_weighted_score(card, draft_progress)

            # --- STEP 2: True Bomb Detection (Power & IWD) ---
            z_score = (raw_gihwr - pack_mean) / pack_std if pack_std > 0 else 0

            # IWD Multiplier: A high Win-Rate + high IWD means it actually wins the game when drawn.
            iwd_mult = (
                1.15
                if (raw_iwd > self.IWD_PREMIUM_THRESHOLD and z_score > 1.0)
                else 1.0
            )
            power_bonus = max(0, z_score * 10 * iwd_mult) if z_score > 0.5 else 0

            if iwd_mult > 1.0:
                reasons.append("TRUE BOMB (High IWD)")

            # --- STEP 3: Signal Capitalization (Draft Navigation) ---
            signal_bonus = 0.0
            # If a premium card goes extremely late in Pack 1, it's a massive signal to pivot
            if pack_number == 1 and current_pick >= 5 and alsa > 0:
                lateness = current_pick - alsa
                if lateness >= 2.0 and z_score > 0.5:
                    signal_bonus = lateness * z_score * 3.0
                    reasons.append(f"LATE SIGNAL (+{signal_bonus:.1f})")

            # --- STEP 4: The Archetype Delta (Synergy vs Trap) ---
            synergy_bonus = 0.0
            if len(self.main_colors) >= 2:
                arch_wr = float(
                    card.get("deck_colors", {})
                    .get(self.main_archetype, {})
                    .get("gihwr", 0.0)
                )
                if arch_wr > 0.0:
                    delta = arch_wr - raw_gihwr
                    if delta >= 2.0:
                        synergy_bonus = delta * 2.5
                        reasons.append(f"High Synergy (+{synergy_bonus:.1f})")
                    elif delta <= -2.0 and raw_gihwr > 55.0:
                        # Good card globally, but bad in our specific deck
                        synergy_bonus = delta * 2.0
                        reasons.append(f"Archetype Trap ({synergy_bonus:.1f})")

            # --- STEP 5: Castability & Splash Logic ---
            cast_mult, cast_reason = self._calculate_castability_v4(
                card, pack_number, current_pick, z_score
            )
            if cast_reason:
                reasons.append(cast_reason)

            # --- STEP 6: Compositional Math (Curve, Roles, Tricks) ---
            role_mult, role_reason = self._calculate_composition_bonus(
                card, pack_number
            )
            if role_reason:
                reasons.append(role_reason)

            # --- STEP 7: Relative Wheel Greed ---
            rank_in_pack = pack_ranks.get(name, 99)
            wheel_mult, wheel_alert, wheel_pct = self._check_relative_wheel(
                card, current_pick, rank_in_pack
            )
            if wheel_alert:
                reasons.append(f"Rank #{rank_in_pack + 1} (May Wheel)")

            # === MASTER ALGORITHM ===
            raw_score = base_score + power_bonus + signal_bonus + synergy_bonus
            final_score = raw_score * cast_mult * role_mult * wheel_mult

            final_score = max(0.0, final_score)

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
                    is_elite=(z_score >= self.BOMB_Z_SCORE),
                    archetype_fit=(
                        "/".join(self.main_colors) if self.main_colors else "Open"
                    ),
                    tags=card.get("tags", []),  # Pass tags to UI
                )
            )

        return sorted(recommendations, key=lambda x: x.contextual_score, reverse=True)

    def _identify_main_colors(self) -> List[str]:
        """
        [PRO THEORY]: Sunk Cost Evasion.
        Identifies our lane by giving significantly more weight to recent picks.
        """
        weights = {c: 0.0 for c in constants.CARD_COLORS}
        playable_threshold = self.global_mean - self.global_std
        total_pool_size = len(self.pool)

        for idx, c in enumerate(self.pool):
            wr = float(c.get("deck_colors", {}).get("All Decks", {}).get("gihwr", 0.0))
            if wr < playable_threshold:
                continue

            # Scale power (Bomb = ~3 pts, Filler = ~0.5 pts)
            base_points = max(
                0.2, 1.0 + 2.0 * ((wr - self.global_mean) / self.global_std)
            )

            # Recency Multiplier: Scales from 1.0x (Pick 1) up to 2.5x (Current Pick)
            recency_mult = 1.0 + (1.5 * (idx / max(1, total_pool_size)))

            final_points = base_points * recency_mult

            for color in c.get("colors", []):
                if color in weights:
                    weights[color] += final_points

        sorted_colors = sorted(weights.items(), key=lambda x: x[1], reverse=True)
        # Return top 2 if they have survived the threshold
        return [c[0] for c in sorted_colors[:2] if c[1] >= 2.5]

    def _analyze_pool(self) -> Dict[str, Any]:
        """
        [PRO THEORY]: Scans the drafted pool for structural roles using Scryfall Oracle Tags.
        """
        curve = {}
        early_plays = 0
        hard_removal_count = 0
        combat_trick_count = 0
        fixing_count = 0

        # Macro Concept Trackers
        card_draw_count = 0
        evasion_count = 0
        mana_sink_count = 0

        splash_targets = set()

        for c in self.pool:
            cmc = self._get_functional_cmc(c)
            types = c.get("types", [])
            tags = c.get("tags", [])

            curve[cmc] = curve.get(cmc, 0) + 1

            if "Creature" in types and cmc <= 2:
                early_plays += 1

            if "removal" in tags:
                hard_removal_count += 1
                if cmc <= 2:
                    early_plays += 1

            if "combat_trick" in tags:
                combat_trick_count += 1

            if "fixing" in tags or ("Land" in types and len(c.get("colors", [])) > 1):
                fixing_count += 1

            if "card_draw" in tags:
                card_draw_count += 1

            if "evasion" in tags:
                evasion_count += 1

            if "mana_sink" in tags:
                mana_sink_count += 1

            # Splash Speculation Mapping
            wr = float(c.get("deck_colors", {}).get("All Decks", {}).get("gihwr", 0.0))
            if wr > (self.global_mean + (1.5 * self.global_std)):
                card_colors = c.get("colors", [])
                if self.main_colors and not any(
                    col in self.main_colors for col in card_colors
                ):
                    for col in card_colors:
                        splash_targets.add(col)

        return {
            "curve": curve,
            "early_plays": early_plays,
            "hard_removal_count": hard_removal_count,
            "combat_trick_count": combat_trick_count,
            "fixing_count": fixing_count,
            "card_draw_count": card_draw_count,
            "evasion_count": evasion_count,
            "mana_sink_count": mana_sink_count,
            "splash_targets": splash_targets,
        }

    def _calculate_composition_bonus(self, card: Dict, pack: int) -> Tuple[float, str]:
        """
        [PRO THEORY]: Deck construction modifiers using Semantic Tags.
        """
        types = card.get("types", [])
        tags = card.get("tags", [])
        cmc = self._get_functional_cmc(card)

        # --- Lands & Fixing Speculation ---
        if "Land" in types or "fixing" in tags:
            card_colors = card.get("colors", [])
            splash_targets = self.pool_metrics.get("splash_targets", set())
            if any(c in splash_targets for c in card_colors):
                return 1.3, "Enables Bomb Splash"
            if pack == 1 and len(card_colors) > 1:
                return 1.15, "Premium Fixing"
            return 1.0, ""

        # --- 1. The Interaction Quota ---
        if "removal" in tags:
            current_removal = self.pool_metrics.get("hard_removal_count", 0)
            if pack >= 2 and current_removal < self.TARGET_HARD_REMOVAL:
                return 1.3, "Critical: Needs Removal"
            elif current_removal > 6:
                return 0.8, "Removal Saturated"

        # --- 2. The 2-Drop Rule (Velocity) ---
        if cmc <= 2 and ("Creature" in types or "removal" in tags):
            projected = self.pool_metrics.get("early_plays", 0) * (
                self.TOTAL_PICKS / max(1, len(self.pool))
            )
            if projected < self.TARGET_EARLY_PLAYS:
                multiplier = 1.0 + min(
                    0.5, (self.TARGET_EARLY_PLAYS - projected) * 0.15
                )
                if pack >= 2:
                    return multiplier, "Critical: Needs 2-Drops"
                return 1.1, "Curve Foundation"

        # --- 3. Consistency (Card Draw) ---
        if "card_draw" in tags:
            current_draw = self.pool_metrics.get("card_draw_count", 0)
            if pack >= 2 and current_draw < self.TARGET_CARD_DRAW:
                return 1.2, "Needs Card Advantage"
            elif current_draw >= 5:
                return 0.7, "Card Draw Saturated"

        # --- 4. Board Stall Breakers (Evasion) ---
        if "evasion" in tags:
            current_evasion = self.pool_metrics.get("evasion_count", 0)
            if pack >= 2 and current_evasion < self.TARGET_EVASION:
                return 1.15, "Needs Evasion/Reach"

        # --- 5. Flood Insurance (Mana Sinks) ---
        if "mana_sink" in tags:
            if self.pool_metrics.get("mana_sink_count", 0) == 0 and pack >= 2:
                return 1.1, "Flood Insurance"

        # --- 6. Diminishing Returns on Tricks ---
        if "combat_trick" in tags:
            if self.pool_metrics.get("combat_trick_count", 0) >= self.CAP_COMBAT_TRICKS:
                return 0.5, "Trick Saturated"

        # --- 7. Top-Heavy Penalty ---
        if cmc >= 5 and "mana_sink" not in tags:
            current_top = sum(
                v for k, v in self.pool_metrics.get("curve", {}).items() if k >= 5
            )
            if current_top >= 4 and pack >= 2:
                return 0.7, "Curve Saturated (5+ CMC)"

        return 1.0, ""

    def _calculate_castability_v4(
        self, card: Dict, pack: int, pick: int, z_score: float
    ) -> Tuple[float, str]:
        """Alien Gold Protection & Frank Karsten Splashing Math."""
        mana_cost = card.get("mana_cost", "")
        if not mana_cost:
            return 1.0, ""

        card_colors = set(card.get("colors", []))
        is_on_color = any(c in self.main_colors for c in card_colors)

        if pack == 1 and pick <= 6:
            if is_on_color:
                return 1.0, ""
            if len(card_colors) > 1:
                return 0.8, "Speculative (Gold)"
            return 0.9, "Speculative"

        if len(card_colors) > 1 and not is_on_color and self.main_colors:
            if (
                len(self.main_colors) >= 2
                and self.pool_metrics.get("fixing_count", 0) < 4
            ):
                return 0.0, "Alien Gold (Uncastable)"

        if is_on_color:
            return 1.0, ""

        pips = sum(1 for char in mana_cost if char in "WUBRG")
        splash_colors = [c for c in card_colors if c not in self.main_colors]
        fixing_available = (
            min([self.fixing_map.get(c, 0) for c in splash_colors]) + 1
            if splash_colors
            else 0
        )

        if pack >= 2 and fixing_available <= 1:
            if z_score >= self.BOMB_Z_SCORE:
                return 0.7, "Bomb (Needs Fixing)"
            return 0.2, "Off-Color"

        if z_score >= self.BOMB_Z_SCORE and pips == 1:
            if fixing_available >= 2:
                return 0.85, "Bomb Splash"
            return 0.5, "Bomb (Needs Fixing)"

        if pips == 1:
            if fixing_available >= 3:
                return 0.8, "Splashable"
            if fixing_available >= 2:
                return 0.6, "Risky Splash"
            return 0.2, "No Fixing"

        return 0.1, "Uncastable (Double Pip)"

    def _check_relative_wheel(
        self, card: Dict, pick: int, rank_in_pack: int
    ) -> Tuple[float, str, float]:
        """Polynomial Wheel Math + Contextual Pack Texture."""
        if pick >= 9:
            return 1.0, "", 0.0

        alsa = float(card.get("deck_colors", {}).get("All Decks", {}).get("alsa", 0.0))
        if alsa == 0.0 or alsa <= pick:
            return 1.0, "", 0.0

        pick_idx = min(pick - 1, 5)
        coeffs = constants.WHEEL_COEFFICIENTS[pick_idx]
        base_prob = float(np.polyval(coeffs, alsa))

        context_prob = base_prob
        if rank_in_pack == 0:
            context_prob *= 0.10
        elif rank_in_pack <= 2:
            context_prob *= 0.40
        elif rank_in_pack >= 8:
            context_prob = min(100.0, context_prob * 1.25)

        final_prob = max(0.0, min(100.0, context_prob))

        if final_prob >= 75.0 and rank_in_pack >= 4:
            return 0.8, f"Wheels ~{final_prob:.0f}%", final_prob

        return 1.0, "", final_prob

    def _calculate_weighted_score(self, card: Dict, progress: float) -> float:
        """Blends Global WR with Archetype WR as the draft progresses."""
        stats = card.get("deck_colors", {})
        global_wr = float(stats.get("All Decks", {}).get("gihwr", 0.0))

        arch_wr = float(stats.get(self.main_archetype, {}).get("gihwr", global_wr))
        if arch_wr == 0.0:
            arch_wr = global_wr

        expected_wr = (global_wr * (1.0 - progress)) + (arch_wr * progress)
        score = 50.0 + ((expected_wr - self.global_mean) / self.global_std) * 12.5

        return max(0.0, score)

    def _get_functional_cmc(self, card: Dict) -> int:
        raw_cmc = int(card.get("cmc", 0))
        text = str(card.get("text", "")).lower()
        if "landcycling" in text:
            return 1
        return raw_cmc

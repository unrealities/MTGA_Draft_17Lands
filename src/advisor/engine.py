"""
src/advisor/engine.py
The "Compositional Brain" (v5.5 Pro-Tour Architecture)
Updated: Pip-Sensitive Discipline and Specific Color Fixing Detection.
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
    TOTAL_PICKS = 45
    TARGET_EARLY_PLAYS = 7
    TARGET_HARD_REMOVAL = 3
    CAP_COMBAT_TRICKS = 3
    TARGET_CARD_DRAW = 2
    TARGET_EVASION = 3
    BOMB_Z_SCORE = 1.5
    IWD_PREMIUM_THRESHOLD = 4.5

    def __init__(self, set_metrics, taken_cards: List[Dict]):
        self.metrics = set_metrics
        self.pool = taken_cards or []

        # 1. Base statistical baselines
        self.global_mean, self.global_std = self.metrics.get_metrics(
            "All Decks", "gihwr"
        )
        if self.global_mean <= 0:
            self.global_mean = 54.0
        if self.global_std <= 0:
            self.global_std = 4.0

        # 2. Identify established lane
        self.main_colors, self.color_counts = self._identify_main_colors()
        self.main_archetype = (
            "".join(sorted(self.main_colors[:2]))
            if len(self.main_colors) >= 2
            else "All Decks"
        )
        self.active_colors = self.main_colors

        # 3. Analyze Pool Needs
        self.fixing_map = count_fixing(self.pool)
        self.pool_metrics = self._analyze_pool()

    def evaluate_pack(
        self, pack_cards: List[Dict], current_pick: int
    ) -> List[Recommendation]:
        if not pack_cards:
            return []
        safe_pick = max(1, min(self.TOTAL_PICKS, current_pick))
        pack_number = math.ceil(safe_pick / 15)

        on_color_pool = [
            c
            for c in self.pool
            if all(col in self.main_colors for col in c.get("colors", []))
        ]
        needs_playables = len(on_color_pool) < 20 and pack_number == 3

        pack_wrs = []
        for c in pack_cards:
            try:
                wr = float(
                    c.get("deck_colors", {}).get("All Decks", {}).get("gihwr", 0.0)
                )
                if wr > 0:
                    pack_wrs.append(wr)
            except:
                continue

        pack_mean = statistics.mean(pack_wrs) if pack_wrs else self.global_mean
        pack_std = statistics.pstdev(pack_wrs) if len(pack_wrs) > 1 else self.global_std
        if pack_std <= 0:
            pack_std = self.global_std

        pack_cards_sorted = sorted(
            pack_cards,
            key=lambda c: float(
                c.get("deck_colors", {}).get("All Decks", {}).get("gihwr", 0.0) or 0.0
            ),
            reverse=True,
        )
        pack_ranks = {
            str(c.get("name", "Unknown")).strip(): i
            for i, c in enumerate(pack_cards_sorted)
        }

        recommendations = []
        for card in pack_cards:
            try:
                name = str(card.get("name", "Unknown")).strip()
                stats = card.get("deck_colors", {}).get("All Decks", {})
                raw_gihwr, raw_iwd, alsa = (
                    float(stats.get("gihwr", 0.0)),
                    float(stats.get("iwd", 0.0)),
                    float(stats.get("alsa", 0.0)),
                )
                card_colors = card.get("colors", [])
                reasons, synergy_bonus = [], 0.0

                # --- STEP 1: Blended Base Score ---
                base_score = self._calculate_weighted_score(card, safe_pick)

                # --- STEP 2: Bomb Detection ---
                z_score = (raw_gihwr - pack_mean) / pack_std
                iwd_mult = (
                    1.15
                    if (raw_iwd > self.IWD_PREMIUM_THRESHOLD and z_score > 1.0)
                    else 1.0
                )
                power_bonus = max(0, z_score * 10 * iwd_mult) if z_score > 0.5 else 0

                # --- STEP 3: Signal Capitalization ---
                if pack_number == 1 and safe_pick >= 5 and alsa > 0:
                    lateness = safe_pick - alsa
                    if lateness >= 2.0 and z_score > 0.5:
                        power_bonus += lateness * z_score * 3.0
                        reasons.append(f"LATE SIGNAL")

                # --- STEP 4: Synergy & Focus ---
                is_on_lane = (
                    all(c in self.main_colors for c in card_colors)
                    if card_colors
                    else True
                )
                if len(self.main_colors) >= 2:
                    arch_wr = float(
                        card.get("deck_colors", {})
                        .get(self.main_archetype, {})
                        .get("gihwr", 0.0)
                    )
                    if arch_wr > 0.0:
                        delta = arch_wr - raw_gihwr
                        if delta >= 1.5:
                            synergy_bonus = delta * 3.5
                            reasons.append(f"Archetype Synergy (+{synergy_bonus:.1f})")
                    if is_on_lane:
                        base_score *= 1.3 if needs_playables else 1.1

                # --- STEP 5: Castability (Pip-Sensitive Discipline) ---
                cast_mult, cast_reason = self._calculate_castability_v5(
                    card, pack_number, safe_pick, z_score
                )
                if cast_reason:
                    reasons.append(cast_reason)

                # --- STEP 6: Composition ---
                role_mult, role_reason = self._calculate_composition_bonus(
                    card, pack_number
                )
                if role_reason:
                    reasons.append(role_reason)

                # --- STEP 7: Wheel logic ---
                rank_in_pack = pack_ranks.get(name, 99)
                wheel_mult, _, wheel_pct = self._check_relative_wheel(
                    card, safe_pick, rank_in_pack
                )

                # === MASTER ALGORITHM ===
                final_score = (
                    (base_score + power_bonus + synergy_bonus)
                    * cast_mult
                    * role_mult
                    * wheel_mult
                )
                if iwd_mult > 1.0:
                    reasons.insert(0, "TRUE BOMB (High IWD)")

                recommendations.append(
                    Recommendation(
                        card_name=name,
                        base_win_rate=raw_gihwr,
                        contextual_score=round(max(0.0, final_score), 1),
                        z_score=round(z_score, 2),
                        cast_probability=cast_mult,
                        wheel_chance=wheel_pct,
                        functional_cmc=self._get_functional_cmc(card),
                        reasoning=reasons,
                        is_elite=(z_score >= self.BOMB_Z_SCORE and cast_mult > 0.4),
                        archetype_fit=(
                            self.main_archetype if is_on_lane else "Splash/Speculative"
                        ),
                        tags=card.get("tags", []),
                    )
                )
            except Exception as e:
                logger.warning(f"Advisor error: {e}")
                continue

        return sorted(recommendations, key=lambda x: x.contextual_score, reverse=True)

    def _identify_main_colors(self) -> Tuple[List[str], Dict[str, float]]:
        color_weights, color_counts = {c: 0.0 for c in constants.CARD_COLORS}, {
            c: 0 for c in constants.CARD_COLORS
        }
        playable_threshold, total_pool_size = self.global_mean - self.global_std, len(
            self.pool
        )
        for idx, c in enumerate(self.pool):
            try:
                colors = c.get("colors", [])
                wr = float(
                    c.get("deck_colors", {}).get("All Decks", {}).get("gihwr", 0.0)
                )
                if "Land" not in c.get("types", []):
                    for col in colors:
                        color_counts[col] += 1
                if wr < playable_threshold:
                    continue
                base_points = max(
                    0.2, 1.0 + 2.0 * ((wr - self.global_mean) / self.global_std)
                )
                recency_mult = 1.0 + (2.0 * (idx / max(1, total_pool_size)))
                for color in colors:
                    if color in color_weights:
                        color_weights[color] += base_points * recency_mult
            except:
                continue
        sorted_w = sorted(color_weights.items(), key=lambda x: x[1], reverse=True)
        main_colors = []
        if total_pool_size >= 15 and sum(color_counts.values()) > 5:
            threshold = sum(color_counts.values()) * 0.15
            leader_set = [
                v[0]
                for v in sorted(color_counts.items(), key=lambda x: x[1], reverse=True)[
                    :2
                ]
                if v[1] > 0
            ]
            for col, weight in sorted_w:
                if col in leader_set or color_counts[col] >= threshold:
                    main_colors.append(col)
        else:
            for col, weight in sorted_w:
                if weight >= 2.5:
                    main_colors.append(col)
        return main_colors[:3], color_counts

    def _analyze_pool(self) -> Dict[str, Any]:
        early_plays, hard_removal_count, fixing_count, splash_targets = 0, 0, 0, set()
        for c in self.pool:
            try:
                cmc, tags = self._get_functional_cmc(c), c.get("tags", [])
                if "Creature" in c.get("types", []) and cmc <= 2:
                    early_plays += 1
                if "removal" in tags:
                    hard_removal_count += 1
                    if cmc <= 2:
                        early_plays += 1
                if "fixing_ramp" in tags or (
                    "Land" in c.get("types", []) and len(c.get("colors", [])) > 1
                ):
                    fixing_count += 1
                wr = float(
                    c.get("deck_colors", {}).get("All Decks", {}).get("gihwr", 0.0)
                )
                if wr > (self.global_mean + (1.5 * self.global_std)):
                    for col in c.get("colors", []):
                        if self.main_colors and col not in self.main_colors:
                            splash_targets.add(col)
            except:
                continue
        return {
            "early_plays": early_plays,
            "hard_removal_count": hard_removal_count,
            "fixing_count": fixing_count,
            "splash_targets": splash_targets,
        }

    def _calculate_composition_bonus(self, card: Dict, pack: int) -> Tuple[float, str]:
        tags, cmc = card.get("tags", []), self._get_functional_cmc(card)
        if "Land" in card.get("types", []) or "fixing_ramp" in tags:
            if any(
                c in self.pool_metrics["splash_targets"] for c in card.get("colors", [])
            ):
                return 1.3, "Enables Bomb Splash"
            return (
                (1.15, "Premium Fixing")
                if pack == 1 and len(card.get("colors", [])) > 1
                else (1.0, "")
            )
        if "removal" in tags:
            if (
                pack >= 2
                and self.pool_metrics["hard_removal_count"] < self.TARGET_HARD_REMOVAL
            ):
                return 1.3, "Critical: Needs Removal"
            elif self.pool_metrics["hard_removal_count"] > 6:
                return 0.8, "Removal Saturated"
        if cmc <= 2 and ("Creature" in card.get("types", []) or "removal" in tags):
            projected = self.pool_metrics["early_plays"] * (
                self.TOTAL_PICKS / max(1, len(self.pool))
            )
            if projected < self.TARGET_EARLY_PLAYS:
                return (
                    (
                        1.0 + min(0.5, (self.TARGET_EARLY_PLAYS - projected) * 0.15),
                        "Critical: Needs 2-Drops",
                    )
                    if pack >= 2
                    else (1.1, "Curve Foundation")
                )
        return 1.0, ""

    def _calculate_castability_v5(
        self, card: Dict, pack: int, pick: int, z_score: float
    ) -> Tuple[float, str]:
        mana_cost = card.get("mana_cost", "")
        if not mana_cost:
            return 1.0, ""
        card_colors = card.get("colors", [])
        top_2_lane = self.main_colors[:2]
        is_on_lane = all(c in top_2_lane for c in card_colors) if card_colors else True
        off_color_pips = sum(
            1 for char in mana_cost if char in "WUBRG" and char not in top_2_lane
        )

        if pack == 1:
            if is_on_lane:
                return 1.0, ""
            pressure = 1.0 - (max(0, ((pack - 1) * 15 + (pick - 1)) - 7) * 0.05)
            return (
                (max(0.2, pressure - 0.2), "Off-Color Gold")
                if len(card_colors) > 1
                else (max(0.4, pressure), "Off-Color")
            )

        if not is_on_lane:
            # P2/P3 Double-Pip Discipline: Hard-Lock double pips if no fixing exists
            if (
                pack >= 2
                and off_color_pips >= 2
                and self.pool_metrics["fixing_count"] < 2
            ):
                return 0.01, "Uncastable (Double Pip)"

            # Specific Color Fixing Detection
            splash_colors = [c for c in card_colors if c not in top_2_lane]
            has_specific_fixing = (
                all(self.fixing_map.get(c, 0) > 0 for c in splash_colors)
                if splash_colors
                else False
            )

            if z_score >= self.BOMB_Z_SCORE and off_color_pips == 1:
                if has_specific_fixing or self.pool_metrics["fixing_count"] >= (
                    4 if pack == 3 else 3
                ):
                    return (0.35 if pack == 3 else 0.45), "Bomb Splash"

            if off_color_pips == 1 and has_specific_fixing:
                return 0.3, "Splashable"
            return 0.01 if pack == 3 else 0.05, "Off-Color"
        return 1.0, ""

    def _check_relative_wheel(
        self, card: Dict, pick: int, rank_in_pack: int
    ) -> Tuple[float, str, float]:
        if pick >= 9:
            return 1.0, "", 0.0
        try:
            alsa = float(
                card.get("deck_colors", {}).get("All Decks", {}).get("alsa", 0.0)
            )
            if alsa <= pick:
                return 1.0, "", 0.0
            coeffs = constants.WHEEL_COEFFICIENTS[min(pick - 1, 5)]
            context_prob = float(np.polyval(coeffs, alsa))
            if rank_in_pack == 0:
                context_prob *= 0.10
            elif rank_in_pack <= 2:
                context_prob *= 0.40
            final_prob = max(0.0, min(100.0, context_prob))
            return (
                (0.8, f"Wheels ~{final_prob:.0f}%", final_prob)
                if final_prob >= 75.0 and rank_in_pack >= 4
                else (1.0, "", final_prob)
            )
        except:
            return 1.0, "", 0.0

    def _calculate_weighted_score(self, card: Dict, pick_number: int) -> float:
        try:
            stats = card.get("deck_colors", {})
            global_wr = float(stats.get("All Decks", {}).get("gihwr", 0.0))
            arch_weight = min(0.9, 0.2 + (pick_number / self.TOTAL_PICKS) * 0.7)
            arch_stats = stats.get(self.main_archetype, {})
            arch_wr = float(arch_stats.get("gihwr", global_wr))
            blended_wr = (
                (global_wr * (1.0 - arch_weight)) + (arch_wr * arch_weight)
                if (arch_wr > 0 and int(arch_stats.get("samples", 0)) >= 100)
                else global_wr
            )
            return max(
                0.0,
                50.0
                + ((blended_wr - self.global_mean) / max(0.1, self.global_std)) * 15.0,
            )
        except:
            return 0.0

    def _get_functional_cmc(self, card: Dict) -> int:
        try:
            raw_cmc = int(card.get("cmc", 0))
            return 1 if "landcycling" in str(card.get("text", "")).lower() else raw_cmc
        except:
            return 0

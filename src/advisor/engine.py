"""
src/advisor/engine.py
The "Compositional Brain" (v5.5 Pro-Tour Architecture)
Updated: Bayesian Smoothing, Signal Tie-Breakers, Top-End/Synergy Tracking, and Premium Removal Splash.
"""

import statistics
import logging
import math
import numpy as np
import re
from typing import List, Dict, Any, Tuple
from src.advisor.schema import Recommendation
from src import constants
from src.card_utils import get_functional_cmc
from src.advisor.deck_scorer import SHRINKAGE_K, _table_prior_z, _load_prior_z_table

# (pool_signature, card_name) -> improvement bonus for the pack-3 lookahead:
# the same pool + candidate card recurs every UI refresh, and the heuristic
# path must stay synchronous (no Monte Carlo here). Cleared with the deck
# caches between tests and on dataset switches.
_LOOKAHEAD_CACHE = {}
from src.advisor.mana_base import count_fixing
from src.utils import normalize_color_string

logger = logging.getLogger(__name__)



def _has_hybrid_route(card, lane_colors):
    """True when the card's single OFF-COLOR pip is itself a hybrid ({U/B}):
    payable through either color. A payable hybrid elsewhere must NOT
    excuse an unrelated solid off-color pip."""
    import re as _re

    cost = str(card.get("mana_cost", ""))
    off_color = []
    for sym in _re.findall(r"\{(.*?)\}", cost):
        opts = [c for c in sym.split("/") if c in "WUBRG"]
        if opts and not any(o in lane_colors for o in opts):
            off_color.append(sym)
    return len(off_color) == 1 and "/" in off_color[0]


class DraftAdvisor:
    TOTAL_PICKS = 45  # upper bound for the pack-local pick index
    # Projection base: cards in a full draft. Distinct concept from TOTAL_PICKS
    # on purpose (Pick-Two drafts 42 cards over 21 picks); do not unify.
    TOTAL_CARDS_DRAFTED = 45
    TARGET_EARLY_PLAYS = 7
    TARGET_HARD_REMOVAL = 3
    CAP_COMBAT_TRICKS = 3
    TARGET_CARD_DRAW = 2
    TARGET_EVASION = 3
    BOMB_Z_SCORE = 1.5
    IWD_PREMIUM_THRESHOLD = 4.5

    def __init__(
        self,
        set_metrics,
        taken_cards: List[Dict],
        signals: Dict[str, float] = None,
        draft_progress: Dict = None,
    ):
        self.metrics = set_metrics
        self.pool = taken_cards or []
        self.signals = signals or {}

        # Initialize the prior table eagerly: the cold-start picker path
        # calls _table_prior_z before any posterior helper would warm the
        # lazy loader (fresh-session day-one picks had no prior at all).
        _load_prior_z_table()

        # Draft progress captured from the controller's locked scanner snapshot:
        # picks (1-based, already normalized by cards_per_pick), total_picks,
        # cards (raw picked-ID count, before metadata resolution), total_cards.
        # None = legacy derivation for tests of other mechanics: progress from
        # the pack-local pick, counts from the (filtered) pool.
        self.draft_progress = draft_progress or {}
        self._progress_picks = self.draft_progress.get("picks")
        self._total_picks = self.draft_progress.get("total_picks", self.TOTAL_PICKS)
        self._total_cards = self.draft_progress.get(
            "total_cards", self.TOTAL_CARDS_DRAFTED
        )
        self._raw_card_count = self.draft_progress.get("cards", len(self.pool))

        # 1. Base statistical baselines. set_has_data records whether the
        # active dataset carries real win rates at all: on a day-1 set every
        # card routes through HeuristicEvaluator (n=0 state matrix, state 3),
        # matching deck_scorer.get_card_rating's fallback.
        raw_mean, raw_std = self.metrics.get_metrics("All Decks", "gihwr")
        self.set_has_data = bool(raw_mean and raw_mean > 0)
        self.global_mean = raw_mean if self.set_has_data else 54.0
        self.global_std = raw_std if (self.set_has_data and raw_std > 0) else 4.0

        # 2. Identify established lane
        self.main_colors, self.color_counts = self._identify_main_colors()
        self.main_archetype = (
            normalize_color_string("".join(self.main_colors[:2]))
            if len(self.main_colors) >= 2
            else "All Decks"
        )
        self.active_colors = self.main_colors

        # 3. Analyze Pool Needs
        self.fixing_map = count_fixing(self.pool)
        self.pool_metrics = self._analyze_pool()

    def evaluate_pack(
        self,
        pack_cards: List[Dict],
        current_pick: int,
        current_pack: int = 1,
        draft_progress: Dict = None,
    ) -> List[Recommendation]:
        if not pack_cards:
            return []
        safe_pick = max(1, min(self.TOTAL_PICKS, current_pick))
        pack_number = max(1, current_pack)
        if draft_progress:
            self.draft_progress = draft_progress
            self._progress_picks = draft_progress.get("picks")
            self._total_picks = draft_progress.get("total_picks", self.TOTAL_PICKS)
            self._total_cards = draft_progress.get(
                "total_cards", self.TOTAL_CARDS_DRAFTED
            )
            self._raw_card_count = draft_progress.get("cards", len(self.pool))
        # Draft-wide progress (pick events made + 1), clamped to the format's
        # pick total. The pack-local safe_pick keeps feeding the wheel path,
        # castability and lateness terms.
        progress_picks = self._progress_picks or safe_pick
        progress_picks = max(1, min(self._total_picks, progress_picks))

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

        self.base_deck_score = 0.0
        self.color_options = []
        if pack_number >= 3 and self._raw_card_count >= 23:
            try:
                from src.card_logic import identify_top_pairs

                self.color_options = identify_top_pairs(self.pool, self.metrics)
                self.base_deck_score = self._get_fast_best_deck_score(
                    self.pool, self.color_options
                )
            except Exception as e:
                logger.warning(f"Advisor base deck scoring error: {e}")
                self.base_deck_score = 0.0
                self.color_options = []

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

                # --- STEP 1: Blended Base Score (With Bayesian Smoothing & Signals) ---
                base_score = self._calculate_weighted_score(card, progress_picks)

                # Reliability of the card's own record gates every raw-rate
                # bonus path below (bomb z-score, lateness capitalization): a
                # small-sample spike must not buy its bonuses back through a
                # path the shared posterior does not cover. No samples field
                # (shipped fixtures) keeps full weight.
                global_samples = int(stats.get("samples", 0) or 0)
                reliability = (
                    global_samples / (global_samples + SHRINKAGE_K)
                    if global_samples > 0
                    else 1.0
                )

                # --- STEP 2: Bomb Detection ---
                z_score = (raw_gihwr - pack_mean) / pack_std
                iwd_mult = (
                    1.15
                    if (raw_iwd > self.IWD_PREMIUM_THRESHOLD and z_score > 1.0)
                    else 1.0
                )
                power_bonus = (
                    max(0, z_score * 10 * iwd_mult) * reliability
                    if z_score > 0.5
                    else 0
                )

                # --- STEP 3: Signal Capitalization ---
                if pack_number == 1 and safe_pick >= 5 and alsa > 0:
                    lateness = safe_pick - alsa
                    if lateness >= 2.0 and z_score > 0.5:
                        power_bonus += lateness * z_score * 3.0 * reliability
                        reasons.append(f"LATE SIGNAL")

                # --- STEP 4: Archetype Synergy & 'Glue Cards' ---
                is_on_lane = (
                    all(c in self.main_colors for c in card_colors)
                    if card_colors
                    else True
                )
                if len(self.main_colors) >= 2:
                    arch_stats = (
                        card.get("deck_colors", {}).get(self.main_archetype, {})
                    )
                    arch_wr = float(arch_stats.get("gihwr", 0.0))
                    pair_n = int(arch_stats.get("samples", 0) or 0)
                    if arch_wr > 0.0 and pair_n >= 30:
                        # Reliability-adjusted synergy: a one-game 100% pair
                        # record used to add delta*5 on its RAW gap (a common
                        # outranking established bombs). The pair edge counts
                        # only as far as its own sample size supports.
                        shrunk_pair = raw_gihwr + (arch_wr - raw_gihwr) * (
                            pair_n / (pair_n + SHRINKAGE_K)
                        )
                        delta = shrunk_pair - raw_gihwr

                        # GLUE CARD DETECTION:
                        # If a Common/Uncommon heavily outperforms its global average in our specific lane,
                        # it is an archetype "Glue Card" and gets a massive multiplier to push it over generic Rares.
                        rarity = str(card.get("rarity", "common")).lower()
                        if delta >= 1.0 and rarity in ["common", "uncommon"]:
                            synergy_bonus = delta * 5.0
                            reasons.append(f"Archetype Glue (+{synergy_bonus:.1f})")
                        elif delta >= 1.5:
                            synergy_bonus = delta * 3.0
                            reasons.append(f"Archetype Synergy (+{synergy_bonus:.1f})")

                    if is_on_lane:
                        base_score *= 1.3 if needs_playables else 1.1

                # --- STEP 5: Value Over Replacement (VOR) ---
                if pack_number == 1 and card_colors and len(card_colors) == 1:
                    c = card_colors[0]
                    texture = getattr(self.metrics, "format_texture", {}).get(c, {})
                    if texture and raw_gihwr >= (self.global_mean - self.global_std):
                        tags = card.get("tags", [])
                        cmc = get_functional_cmc(card)

                        roles_to_check = []
                        if "Creature" in card.get("types", []) and cmc <= 2:
                            roles_to_check.append(("2-drop", "2-Drops"))
                        if "removal" in tags:
                            roles_to_check.append(("removal", "Removal"))
                        if "evasion" in tags:
                            roles_to_check.append(("evasion", "Evasion"))

                        for role_key, role_name in roles_to_check:
                            count = texture.get(role_key, 99)
                            if count <= 2:
                                vor_bonus = 6.0
                                power_bonus += vor_bonus
                                reasons.append(
                                    f"High VOR: Scarce {c} {role_name} (+{vor_bonus:.0f})"
                                )
                            elif count >= 7:
                                power_bonus -= 2.0
                                reasons.append(f"Highly Replaceable {role_name}")

                # --- STEP 6: Castability (Pip-Sensitive Discipline & Premium Splashing) ---
                cast_mult, cast_reason = self._calculate_castability_v5(
                    card, pack_number, safe_pick, z_score
                )
                if cast_reason:
                    reasons.append(cast_reason)

                # --- STEP 7: Composition & Synergies ---
                role_mult, role_reason = self._calculate_composition_bonus(
                    card, pack_number
                )
                if role_reason:
                    reasons.append(role_reason)

                # --- STEP 7.5: Late Draft Deck Improvement ---
                deck_improvement_bonus = 0.0
                if pack_number >= 3 and self._raw_card_count >= 23:
                    try:
                        cache_key = (
                            "|".join(
                                sorted(
                                    f"{c.get('name', '')}:{c.get('count', 1)}"
                                    for c in self.pool
                                )
                            ),
                            name,
                        )
                        if cache_key in _LOOKAHEAD_CACHE:
                            deck_improvement_bonus = _LOOKAHEAD_CACHE[cache_key]
                        else:
                            test_pool = self.pool + [card]
                            new_score = self._get_fast_best_deck_score(
                                test_pool, self.color_options, pool_size=len(self.pool)
                            )
                            improvement = new_score - self.base_deck_score
                            if improvement > 0.1:
                                deck_improvement_bonus = improvement * 3.0
                            _LOOKAHEAD_CACHE[cache_key] = deck_improvement_bonus
                        if deck_improvement_bonus > 0:
                            reasons.append(
                                f"Improves Best Deck (+{deck_improvement_bonus:.1f})"
                            )
                    except Exception as e:
                        logger.warning(f"Advisor deck improvement scoring error: {e}")

                # --- STEP 8: Wheel logic ---
                rank_in_pack = pack_ranks.get(name, 99)
                wheel_mult, _, wheel_pct = self._check_relative_wheel(
                    card, safe_pick, rank_in_pack
                )

                # === MASTER ALGORITHM ===
                # The deck-improvement bonus compares decks whose builders
                # already filter is_castable(strict=True): applying cast_mult
                # here discounted the same signal twice.
                final_score = (
                    (base_score + power_bonus + synergy_bonus)
                    * cast_mult
                    * role_mult
                    * wheel_mult
                    + deck_improvement_bonus
                )

                is_basic_land = name in constants.BASIC_LANDS or (
                    "Basic" in card.get("types", []) and "Land" in card.get("types", [])
                )

                if is_basic_land:
                    final_score = 0.0
                    if len(pack_cards) == 1:
                        reasons = ["This is the only available option."]
                    else:
                        reasons = ["Basic Land (Skip)"]

                if iwd_mult > 1.0 and final_score > 0:
                    reasons.insert(0, "TRUE BOMB (High IWD)")

                recommendations.append(
                    Recommendation(
                        card_name=name,
                        base_win_rate=raw_gihwr,
                        contextual_score=round(max(0.0, final_score), 1),
                        z_score=round(z_score, 2),
                        cast_probability=cast_mult,
                        wheel_chance=wheel_pct,
                        functional_cmc=get_functional_cmc(card),
                        reasoning=reasons,
                        is_elite=(
                            (z_score >= self.BOMB_Z_SCORE and cast_mult > 0.4)
                            if not is_basic_land
                            else False
                        ),
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
        color_weights, color_counts = (
            {c: 0.0 for c in constants.CARD_COLORS},
            {c: 0 for c in constants.CARD_COLORS},
        )
        playable_threshold, total_pool_size = (
            self.global_mean - self.global_std,
            len(self.pool),
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
        if self._raw_card_count >= 15 and sum(color_counts.values()) > 5:
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
        off_color_playables = 0
        creature_count = 0
        heavy_drops = 0
        artifacts = 0
        graveyard_enablers = 0
        counters_enablers = 0

        for c in self.pool:
            try:
                cmc, tags = get_functional_cmc(c), c.get("tags", [])
                colors = c.get("colors", [])
                types = c.get("types", [])

                if "Creature" in types:
                    creature_count += 1
                    if cmc <= 2:
                        early_plays += 1

                if cmc >= 5 and "Land" not in types:
                    heavy_drops += 1

                if (
                    "Artifact" in types
                    or "synergy_artifacts" in tags
                    or "token_maker" in tags
                ):
                    artifacts += 1
                if "synergy_graveyard" in tags or "card_advantage" in tags:
                    graveyard_enablers += 1
                if "synergy_counters" in tags:
                    counters_enablers += 1

                if "removal" in tags:
                    hard_removal_count += 1
                    if cmc <= 2 and "Creature" not in types:
                        early_plays += 1
                if "fixing_ramp" in tags or ("Land" in types and len(colors) > 1):
                    fixing_count += 1

                wr = float(
                    c.get("deck_colors", {}).get("All Decks", {}).get("gihwr", 0.0)
                )

                is_off_color = False
                if self.main_colors and colors:
                    is_off_color = not all(col in self.main_colors for col in colors)

                if is_off_color and wr > (self.global_mean - self.global_std):
                    off_color_playables += 1

                if wr > (self.global_mean + (1.5 * self.global_std)):
                    for col in colors:
                        if self.main_colors and col not in self.main_colors:
                            splash_targets.add(col)
            except:
                continue
        return {
            "early_plays": early_plays,
            "hard_removal_count": hard_removal_count,
            "fixing_count": fixing_count,
            "splash_targets": splash_targets,
            "off_color_playables": off_color_playables,
            "creature_count": creature_count,
            "heavy_drops": heavy_drops,
            "artifacts": artifacts,
            "graveyard_enablers": graveyard_enablers,
            "counters_enablers": counters_enablers,
        }

    def _projected_total(self, count: int) -> float:
        """Projects a resolved-pool count to a full draft. Both the numerator
        count and the denominator pool are resolved-card quantities, so the
        projection legitimately moves when a card resolves and changes
        composition; only progress-derived terms must be resolution-invariant."""
        return count * (self._total_cards / max(1, len(self.pool)))

    def _calculate_composition_bonus(self, card: Dict, pack: int) -> Tuple[float, str]:
        tags, cmc = card.get("tags", []), get_functional_cmc(card)
        types = card.get("types", [])

        # 1. Curve and Heavy Drops Check
        if cmc >= 5 and self.pool_metrics["heavy_drops"] >= 4 and "Land" not in types:
            return 0.7, "Curve Too Heavy"

        # 2. Creature Quota Check
        if pack >= 2 and "Creature" in types:
            projected_creatures = self._projected_total(
                self.pool_metrics["creature_count"]
            )
            if projected_creatures < 13:
                return 1.25, "Critical: Needs Creatures"

        # 3. Synergy (A+B) Checks
        if "synergy_artifacts" in tags and self.pool_metrics["artifacts"] >= 4:
            return 1.2, "Artifact Synergy"
        if "synergy_graveyard" in tags and self.pool_metrics["graveyard_enablers"] >= 3:
            return 1.2, "Graveyard Synergy"
        if "synergy_counters" in tags and self.pool_metrics["counters_enablers"] >= 3:
            return 1.2, "Counters Synergy"

        # 4. Fixing Hunger
        if "Land" in types or "fixing_ramp" in tags:
            off_color_playables = self.pool_metrics.get("off_color_playables", 0)
            fixing_count = self.pool_metrics.get("fixing_count", 0)

            if (
                pack >= 2
                and off_color_playables > 0
                and fixing_count <= off_color_playables
            ):
                return 1.4, "Critical: Needs Fixing"

            if any(
                c in self.pool_metrics["splash_targets"] for c in card.get("colors", [])
            ):
                return 1.3, "Enables Bomb Splash"

            return (
                (1.15, "Premium Fixing")
                if pack == 1 and len(card.get("colors", [])) > 1
                else (1.0, "")
            )

        # 5. Removal Check
        if "removal" in tags:
            if (
                pack >= 2
                and self.pool_metrics["hard_removal_count"] < self.TARGET_HARD_REMOVAL
            ):
                return 1.3, "Critical: Needs Removal"
            elif self.pool_metrics["hard_removal_count"] > 6:
                return 0.8, "Removal Saturated"

        # 6. Early Interaction
        if cmc <= 2 and ("Creature" in types or "removal" in tags):
            projected = self._projected_total(self.pool_metrics["early_plays"])
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
        card_colors = card.get("colors", [])
        top_2_lane = self.main_colors[:2]

        off_color_pips = 0
        required_colorless = 0
        if mana_cost:
            is_on_lane = True
            pips = re.findall(r"\{(.*?)\}", mana_cost)
            for pip in pips:
                if "/" in pip:
                    # Hybrid and phyrexian pips are flexible payments, but
                    # only when the alternate option is actually payable:
                    # {2/W} and {B/P} have generic/life alternates (flexible);
                    # {U/B} — purely colored — is a hard off-color pip when
                    # neither color is in the lane.
                    options = [c for c in pip.split("/") if c in "WUBRG"]
                    has_noncolor_alt = any(
                        c not in "WUBRG" for c in pip.split("/")
                    )
                    if options and any(opt in top_2_lane for opt in options):
                        continue
                    if has_noncolor_alt:
                        continue  # generic/life payment available
                    off_color_pips += 1
                    is_on_lane = False
                if pip == "C":
                    required_colorless += 1
                    continue
                if pip in "WUBRG":
                    if pip in top_2_lane:
                        continue
                    off_color_pips += 1
                    is_on_lane = False
        else:
            is_on_lane = (
                all(c in top_2_lane for c in card_colors) if card_colors else True
            )
            off_color_pips = 0 if is_on_lane else 1

        if pack == 1:
            if is_on_lane:
                return 1.0, ""
            pressure = 1.0 - (max(0, ((pack - 1) * 15 + (pick - 1)) - 7) * 0.05)
            return (
                (max(0.2, pressure - 0.2), "Off-Color Gold")
                if len(card_colors) > 1 and off_color_pips > 0
                else (max(0.4, pressure), "Off-Color")
            )

        if required_colorless > 0:
            colorless_sources = self.fixing_map.get("C", 0)
            if colorless_sources < required_colorless:
                # {C} must be paid with colorless mana specifically; basic
                # lands produce their color, not colorless.
                return 0.15, "Colorless Requirement"

        if not is_on_lane:
            if (
                pack >= 2
                and off_color_pips >= 2
                and self.pool_metrics["fixing_count"] < 2
            ):
                return 0.01, "Uncastable (Double Pip)"

            splash_colors = [c for c in card_colors if c not in top_2_lane]
            has_specific_fixing = (
                all(self.fixing_map.get(c, 0) > 0 for c in splash_colors)
                if splash_colors
                else False
            )

            is_premium_removal = "removal" in card.get("tags", []) and z_score >= 1.0

            # Allow premium 1-for-1s to be splashed just like game-winning bombs
            if z_score >= self.BOMB_Z_SCORE or is_premium_removal:
                if off_color_pips == 1:
                    # Color-specific conjunction: generic fixing_count alone
                    # must not unlock a splash (three green duals do not pay
                    # for a blue pip); the pool must also be fixing-rich
                    # enough overall (3 before pack 3, 4 in pack 3).
                    if has_specific_fixing and self.pool_metrics["fixing_count"] >= (
                        4 if pack == 3 else 3
                    ):
                        reason = (
                            "Bomb Splash"
                            if z_score >= self.BOMB_Z_SCORE
                            else "Premium Removal Splash"
                        )
                        return (0.35 if pack == 3 else 0.45), reason
                elif (
                    off_color_pips == 2
                    and get_functional_cmc(card) >= 5
                    and z_score >= self.BOMB_Z_SCORE
                ):
                    # Same color-specific conjunction as the single-pip
                    # branch: generic fixing_count alone must not unlock a
                    # double-pip splash with zero sources of that color.
                    if (
                        has_specific_fixing
                        and self.pool_metrics["fixing_count"] >= 4
                    ):
                        return 0.30, "Greedy Bomb Splash"

            # Hybrid ({U/B}) off-lane: ONE payable route suffices — the
            # card can be cast through either color. Requiring both
            # blocked every hybrid splash candidate.
            if off_color_pips == 1 and (
                has_specific_fixing or _has_hybrid_route(card, top_2_lane)
            ):
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
            if not self.set_has_data:
                # Day 1 before any data exists. The shipped card prior still
                # speaks here: what the card DOES predicts its expected z, and
                # a table hit beats metadata heuristics (fresh adversarial
                # round: the prior was advertised for exactly this state but
                # never consulted in it). Pure heuristics remain for cards
                # outside the table.
                prior_z = _table_prior_z(card)
                if prior_z:
                    return max(0.0, 50.0 + prior_z * 15.0)
                from src.sealed_logic import HeuristicEvaluator

                h = HeuristicEvaluator.evaluate(card)
                return max(
                    0.0,
                    50.0
                    + ((h - self.global_mean) / max(0.1, self.global_std)) * 15.0,
                )

            stats = card.get("deck_colors", {})
            global_wr = float(stats.get("All Decks", {}).get("gihwr", 0.0))
            arch_weight = min(0.9, 0.2 + (pick_number / self._total_picks) * 0.7)
            arch_stats = stats.get(self.main_archetype, {})
            arch_wr = float(arch_stats.get("gihwr", global_wr))

            # BAYESIAN SMOOTHING via the shared posterior helper (cycle 2,
            # item 1a): the archetype rate shrinks toward global + pair-offset
            # with n/(n+k); n <= 0 keeps the raw value (shipped fixtures have
            # no samples field, so their pinned numbers are unchanged).
            from src.advisor.deck_scorer import card_wr_posteriors

            post = card_wr_posteriors(card, [self.main_archetype], self.metrics)
            samples = int(arch_stats.get("samples", 0))
            trusted_arch_wr = (
                post["shrunk_arch"] if post["n"] > 0 else arch_wr
            )
            # The GLOBAL side of the blend is the posterior too: the raw rate
            # let a one-game 100% spike outrank established bombs in the
            # base score (fresh adversarial round R1).
            trusted_global_wr = (
                post["shrunk_global"] if post["n_global"] > 0 else global_wr
            )

            blended_wr = (
                (trusted_global_wr * (1.0 - arch_weight)) + (trusted_arch_wr * arch_weight)
                if (arch_wr > 0 and samples >= 10)
                else trusted_global_wr
            )

            base_score = max(
                0.0,
                50.0
                + ((blended_wr - self.global_mean) / max(0.1, self.global_std)) * 15.0,
            )

            # SIGNAL TIE-BREAKER
            card_colors = card.get("colors", [])
            if self.signals and card_colors:
                signal_strength = sum(self.signals.get(c, 0.0) for c in card_colors)
                if signal_strength > 10.0:
                    base_score *= 1.05

            return base_score
        except:
            return 0.0

    def _get_fast_best_deck_score(
        self,
        pool: List[Dict],
        color_options: List[List[str]],
        pool_size: int = None,
    ) -> float:
        """Best holistic deck score over the variant builders. `pool_size`
        overrides the pool length fed to the scorer: the pack-3 lookahead
        passes the baseline's size so the comparison is not contaminated by
        the expected-spells step penalty (a +1 pool crossing a step shifts
        the penalty by a constant -10 with no deck change at all)."""
        from src.card_logic import (
            build_variant_consistency,
            build_variant_greedy,
            build_variant_curve,
            build_variant_soup,
            calculate_holistic_score,
        )

        effective_size = len(pool) if pool_size is None else pool_size
        best_score = 0.0
        for main_colors in color_options:
            for builder in [build_variant_consistency, build_variant_curve]:
                deck = builder(pool, main_colors, self.metrics)
                if deck:
                    score, _ = calculate_holistic_score(
                        deck, main_colors, effective_size, self.metrics
                    )
                    if score > best_score:
                        best_score = score

            deck, splash = build_variant_greedy(pool, main_colors, self.metrics)
            if deck:
                # Score by the deck's own identity (shared helper with the
                # suggester) so the lookahead and the suggester never score the
                # same deck under different color regimes.
                from src.advisor.deck_builder import deck_color_identity

                target_colors = deck_color_identity(deck) or (
                    main_colors + [splash] if splash else main_colors
                )
                score, _ = calculate_holistic_score(
                    deck, target_colors, effective_size, self.metrics
                )
                if score > best_score:
                    best_score = score

        deck, soup_colors = build_variant_soup(pool, self.metrics)
        if deck:
            from src.advisor.deck_builder import deck_color_identity

            target_colors = deck_color_identity(deck) or (
                soup_colors[:3] if soup_colors else ["All Decks"]
            )
            score, _ = calculate_holistic_score(
                deck, target_colors, effective_size, self.metrics
            )
            if score > best_score:
                best_score = score

        return best_score

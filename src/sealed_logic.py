"""
src/sealed_logic.py
Core data structures and Day-1 Heuristic Engine for the Epic Sealed Studio.
Manages multi-deck variants and calculates card power without 17Lands data.
"""

import json
import os
import logging
from typing import List, Dict, Optional, Tuple
from src import constants

logger = logging.getLogger(__name__)


class HeuristicEvaluator:
    """
    Evaluates card power purely based on Scryfall metadata (Rarity, CMC, Tags).
    Generates a score from 40.0 to 68.0 to seamlessly substitute for 17Lands GIHWR.
    """

    BASE_SCORES = {
        "common": 52.0,  # ~C-
        "uncommon": 54.0,  # ~C
        "rare": 58.0,  # ~B-
        "mythic": 60.0,  # ~B
    }

    @classmethod
    def evaluate(cls, card: Dict) -> float:
        from src.card_logic import get_functional_cmc

        rarity = str(card.get("rarity", "common")).lower()
        score = cls.BASE_SCORES.get(rarity, 52.0)

        cmc = get_functional_cmc(card)
        tags = card.get("tags", [])
        types = card.get("types", [])

        # 1. Evaluate Removal
        if "removal" in tags:
            if cmc <= 2:
                score += 6.0  # Premium removal
            elif cmc <= 4:
                score += 4.0
            else:
                score += 1.5  # Clunky removal

        # 2. Evaluate Fixing & Ramp
        if "fixing_ramp" in tags:
            if cmc <= 3:
                score += 4.0
            else:
                score += 1.5

        # 3. Evaluate Impact
        if "evasion" in tags:
            score += 2.5
        if "card_advantage" in tags:
            score += 3.0

        # 4. Evaluate Curve / Tempo
        if "Creature" in types:
            if cmc == 2:
                score += 1.5
            elif cmc == 3:
                score += 1.0
            elif cmc >= 5 and not any(
                t in tags for t in ["removal", "evasion", "card_advantage"]
            ):
                score -= 4.0  # Penalize big dumb vanilla creatures

        # 5. Minor Synergy
        if "combat_trick" in tags:
            score -= 1.0
        if "protection" in tags:
            score += 1.0

        return max(40.0, min(68.0, score))


class SealedVariant:
    """Represents a single deck build within a Sealed Session."""

    def __init__(self, name: str):
        self.name = name
        self.main_deck_counts: Dict[str, int] = {}

    def add_card(self, card_name: str, count: int = 1):
        self.main_deck_counts[card_name] = (
            self.main_deck_counts.get(card_name, 0) + count
        )

    def remove_card(self, card_name: str, count: int = 1):
        if card_name in self.main_deck_counts:
            self.main_deck_counts[card_name] -= count
            if self.main_deck_counts[card_name] <= 0:
                del self.main_deck_counts[card_name]

    def to_dict(self) -> Dict:
        return {"name": self.name, "main_deck_counts": self.main_deck_counts}

    @classmethod
    def from_dict(cls, data: Dict) -> "SealedVariant":
        variant = cls(data.get("name", "Unnamed Variant"))
        variant.main_deck_counts = data.get("main_deck_counts", {})
        return variant


class SealedSession:
    """The master state manager for the Epic Sealed Studio."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.master_pool: List[Dict] = []
        self.variants: Dict[str, SealedVariant] = {}
        self.active_variant_name: str = ""
        self._pool_inventory: Dict[str, int] = {}

    def load_pool(self, raw_pool: List[Dict]):
        self.master_pool = raw_pool
        self._pool_inventory.clear()

        for card in raw_pool:
            name = card.get(constants.DATA_FIELD_NAME)
            count = card.get(constants.DATA_FIELD_COUNT, 1)
            if name:
                self._pool_inventory[name] = self._pool_inventory.get(name, 0) + count

        if not self.variants:
            self.create_variant("Build 1")

    def create_variant(self, name: str, copy_from: Optional[str] = None):
        base_name = name
        counter = 1
        while name in self.variants:
            name = f"{base_name} ({counter})"
            counter += 1

        new_variant = SealedVariant(name)
        if copy_from and copy_from in self.variants:
            new_variant.main_deck_counts = self.variants[
                copy_from
            ].main_deck_counts.copy()

        self.variants[name] = new_variant
        self.active_variant_name = name

    def delete_variant(self, name: str):
        if name in self.variants and len(self.variants) > 1:
            del self.variants[name]
            if self.active_variant_name == name:
                self.active_variant_name = list(self.variants.keys())[0]

    def rename_variant(self, old_name: str, new_name: str) -> bool:
        if old_name in self.variants and new_name not in self.variants:
            variant = self.variants.pop(old_name)
            variant.name = new_name
            self.variants[new_name] = variant
            if self.active_variant_name == old_name:
                self.active_variant_name = new_name
            return True
        return False

    def move_to_main(self, card_name: str, count: int = 1) -> bool:
        if not self.active_variant_name:
            return False

        variant = self.variants[self.active_variant_name]
        max_available = self._pool_inventory.get(card_name, 0)
        is_basic = card_name in constants.BASIC_LANDS
        current_in_main = variant.main_deck_counts.get(card_name, 0)

        if is_basic or (current_in_main + count <= max_available):
            variant.add_card(card_name, count)
            return True
        return False

    def move_to_sideboard(self, card_name: str, count: int = 1):
        if self.active_variant_name:
            self.variants[self.active_variant_name].remove_card(card_name, count)

    def get_active_deck_lists(self) -> Tuple[List[Dict], List[Dict]]:
        if not self.active_variant_name:
            return [], []

        main_deck = []
        sideboard = []
        variant = self.variants[self.active_variant_name]

        card_prototypes = {}
        for card in self.master_pool:
            name = card.get(constants.DATA_FIELD_NAME)
            if name and name not in card_prototypes:
                card_prototypes[name] = card

        for name, count in variant.main_deck_counts.items():
            if name in card_prototypes:
                import copy

                card_copy = copy.deepcopy(card_prototypes[name])
                card_copy[constants.DATA_FIELD_COUNT] = count
                main_deck.append(card_copy)
            elif name in constants.BASIC_LANDS:
                main_deck.append(
                    {
                        "name": name,
                        "cmc": 0,
                        "types": ["Land", "Basic"],
                        "colors": [],
                        "count": count,
                    }
                )

        for name, total_count in self._pool_inventory.items():
            used_in_main = variant.main_deck_counts.get(name, 0)
            remaining = total_count - used_in_main

            if remaining > 0 and name in card_prototypes:
                import copy

                card_copy = copy.deepcopy(card_prototypes[name])
                card_copy[constants.DATA_FIELD_COUNT] = remaining
                sideboard.append(card_copy)

        return main_deck, sideboard

    def save_session(self):
        filepath = os.path.join(constants.TEMP_FOLDER, f"sealed_{self.session_id}.json")
        try:
            data = {
                "session_id": self.session_id,
                "active_variant_name": self.active_variant_name,
                "variants": {k: v.to_dict() for k, v in self.variants.items()},
            }
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save sealed session: {e}")

    @classmethod
    def load_session(
        cls, session_id: str, raw_pool: List[Dict]
    ) -> Optional["SealedSession"]:
        filepath = os.path.join(constants.TEMP_FOLDER, f"sealed_{session_id}.json")
        if not os.path.exists(filepath):
            return None
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("session_id") != session_id:
                return None

            session = cls(session_id)
            session.load_pool(raw_pool)
            session.active_variant_name = data.get("active_variant_name", "")
            for k, v_data in data.get("variants", {}).items():
                session.variants[k] = SealedVariant.from_dict(v_data)
            return session
        except Exception:
            return None


def generate_sealed_shells(session: SealedSession, metrics, tier_data=None) -> None:
    """
    Analyzes the SealedSession's master pool and mathematically generates
    the top 3 distinct shells, loading them directly into the session variants.
    """
    # Import locally to avoid circular dependencies
    from src.card_logic import (
        identify_top_pairs,
        build_variant_consistency,
        build_variant_greedy,
        build_variant_curve,
        calculate_holistic_score,
    )

    pool = session.master_pool
    if not pool or len(pool) < 40:
        return

    session.variants.clear()
    top_pairs = identify_top_pairs(pool, metrics, tier_data)
    if not top_pairs:
        top_pairs = [["W", "U"]]

    primary_pair = top_pairs[0]

    # 1. Best 2-Color
    con_deck = build_variant_consistency(pool, primary_pair, metrics, tier_data)
    if con_deck:
        score, _ = calculate_holistic_score(
            con_deck, primary_pair, len(pool), metrics, tier_data
        )
        variant = SealedVariant(f"Best 2-Color ({''.join(primary_pair)}) [{score:.0f}]")
        for c in con_deck:
            variant.add_card(c["name"], c.get("count", 1))
        session.variants[variant.name] = variant
        session.active_variant_name = variant.name

    # 2. Greedy Splash
    greedy_deck, splash_color = build_variant_greedy(
        pool, primary_pair, metrics, tier_data
    )
    if greedy_deck and splash_color:
        target_colors = primary_pair + [splash_color]
        score, _ = calculate_holistic_score(
            greedy_deck, target_colors, len(pool), metrics, tier_data
        )
        variant = SealedVariant(f"Greedy Splash (+{splash_color}) [{score:.0f}]")
        for c in greedy_deck:
            variant.add_card(c["name"], c.get("count", 1))
        session.variants[variant.name] = variant

    # 3. Aggro / Tempo
    secondary_pair = top_pairs[1] if len(top_pairs) > 1 else primary_pair
    tempo_deck = build_variant_curve(pool, secondary_pair, metrics, tier_data)
    if tempo_deck:
        score, _ = calculate_holistic_score(
            tempo_deck, secondary_pair, len(pool), metrics, tier_data
        )
        variant = SealedVariant(
            f"Aggro Curve ({''.join(secondary_pair)}) [{score:.0f}]"
        )
        for c in tempo_deck:
            variant.add_card(c["name"], c.get("count", 1))
        if variant.name not in session.variants:
            session.variants[variant.name] = variant

    if not session.variants:
        session.create_variant("Empty Build")

"""
src/dataset.py
Data storage and retrieval for card ratings.
"""

from src.utils import Result, check_file_integrity, normalize_color_string
from src.file_extractor import initialize_card_data
from typing import List, Dict, Tuple
from src.constants import (
    DATA_FIELD_NAME,
    DATA_FIELD_MANA_COST,
    DATA_FIELD_TYPES,
    DATA_FIELD_DECK_COLORS,
    DATA_SECTION_IMAGES,
    COLOR_NAMES_DICT,
    WIN_RATE_OPTIONS,
    WIN_RATE_FIELDS_DICT,
)


class Dataset:
    def __init__(self, retrieve_unknown: bool = False):
        self._dataset = None
        self._retrieve_unknown = retrieve_unknown

    def clear(self) -> None:
        self._dataset = None

    def open_file(self, file_location: str) -> Result:
        if not file_location:
            return Result.ERROR_MISSING_FILE

        result, json_data = check_file_integrity(file_location)
        if result != Result.VALID:
            return result

        if "color_ratings" in json_data:
            json_data["color_ratings"] = {
                normalize_color_string(k): v
                for k, v in json_data["color_ratings"].items()
            }

        if "card_ratings" in json_data:
            for card in json_data["card_ratings"].values():
                if "deck_colors" in card:
                    card["deck_colors"] = {
                        normalize_color_string(k): v
                        for k, v in card["deck_colors"].items()
                    }

        self._dataset = json_data
        return result

    def get_data_by_id(self, id_list: List[str]) -> List[Dict]:
        if not isinstance(id_list, list):
            return []
        card_data = []
        ratings = self._dataset["card_ratings"] if self._dataset else {}

        for arena_id in id_list:
            string_id = str(arena_id)
            if string_id in ratings:
                card_data.append(ratings[string_id])
            elif self._retrieve_unknown:
                empty_dict = {
                    DATA_FIELD_NAME: string_id,
                    DATA_FIELD_MANA_COST: "",
                    DATA_FIELD_TYPES: [],
                    DATA_SECTION_IMAGES: [],
                }
                initialize_card_data(empty_dict)
                card_data.append(empty_dict)
        return card_data

    def get_data_by_name(self, name_list: List[str]) -> List[Dict]:
        if not isinstance(name_list, list) or not self._dataset:
            return []
        ratings = self._dataset.get("card_ratings", {})
        transformed = {v[DATA_FIELD_NAME]: v for v in ratings.values()}
        return [transformed[n] for n in name_list if n in transformed]

    def get_names_by_id(self, id_list: List[str]) -> List[str]:
        """Restored for test and scanner compatibility."""
        data = self.get_data_by_id(id_list)
        return [c[DATA_FIELD_NAME] for c in data if DATA_FIELD_NAME in c]

    def get_ids_by_name(self, name_list: List[str], return_int: bool = False) -> List:
        """Restored for test and scanner compatibility."""
        if not self._dataset:
            return []
        ratings = self._dataset.get("card_ratings", {})
        # Create mapping of Name -> ID
        name_to_id = {v[DATA_FIELD_NAME]: k for k, v in ratings.items()}
        results = []
        for name in name_list:
            if name in name_to_id:
                val = name_to_id[name]
                results.append(int(val) if return_int else str(val))
        return results

    def get_card_ratings(self) -> Dict:
        return self._dataset.get("card_ratings", {}) if self._dataset else {}

    def get_color_ratings(self) -> Dict:
        return self._dataset.get("color_ratings", {}) if self._dataset else {}

    def get_all_names(self) -> List[str]:
        if self._dataset:
            ratings = self._dataset.get("card_ratings", {})
            return list(set([v[DATA_FIELD_NAME] for v in ratings.values()]))
        return []

    def get_card_archetypes_by_field(self, card_name: str, field: str) -> List[Tuple]:
        if not self._dataset or field not in WIN_RATE_OPTIONS:
            return []

        card_list = self.get_data_by_name([card_name])
        if not card_list:
            return []

        deck_stats = card_list[0].get(DATA_FIELD_DECK_COLORS, {})
        archetype_list = []

        all_decks = deck_stats.get("All Decks", {})
        # Fix: Only include if there is actually win rate data
        if all_decks and all_decks.get(field, 0.0) > 0:
            archetype_list.append(
                [
                    "",
                    "All Decks",
                    all_decks.get(field, 0.0),
                    all_decks.get(WIN_RATE_FIELDS_DICT[field], 0),
                ]
            )

        for color, name in COLOR_NAMES_DICT.items():
            if color in deck_stats:
                spec = deck_stats[color]
                if spec.get(field, 0) > 0:
                    archetype_list.append(
                        [name, color, spec[field], spec[WIN_RATE_FIELDS_DICT[field]]]
                    )

        return sorted(archetype_list, key=lambda x: x[3], reverse=True)

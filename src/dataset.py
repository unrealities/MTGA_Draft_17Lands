"""
src/dataset.py
Data storage and retrieval for card ratings.
"""

from src.utils import (
    Result,
    check_file_integrity,
    normalize_color_string,
    sanitize_card_name,
)
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
    def __init__(self, retrieve_unknown: bool = False, db_path: str = None):
        self._dataset = None
        self._retrieve_unknown = retrieve_unknown
        self.db_path = db_path
        self._name_index = {}
        self._id_index = {}
        self.unknown_id_cache = {}

    def clear(self) -> None:
        """Clears the dataset and all memory caches."""
        self._dataset = None
        self._name_index.clear()
        self._id_index.clear()
        self.unknown_id_cache.clear()

    def _resolve_unknown_id(self, grp_id: str) -> str:
        """Queries the local MTG Arena database to instantly translate unknown IDs."""
        if grp_id in self.unknown_id_cache:
            return self.unknown_id_cache[grp_id]

        import sqlite3
        import os
        from src import constants

        try:
            db_folder = (
                os.path.join(self.db_path, constants.LOCAL_DOWNLOADS_DATA)
                if self.db_path
                else ""
            )

            if db_folder and os.path.exists(db_folder):
                db_files = [
                    f
                    for f in os.listdir(db_folder)
                    if f.startswith(constants.LOCAL_DATA_FILE_PREFIX_DATABASE)
                ]

                if db_files:
                    db_files.sort(
                        key=lambda x: os.path.getmtime(os.path.join(db_folder, x)),
                        reverse=True,
                    )
                    db_file = os.path.join(db_folder, db_files[0])

                    conn = sqlite3.connect(db_file)
                    cursor = conn.cursor()

                    query = "SELECT loc.Loc FROM Cards c JOIN Localizations_enUS loc ON c.titleid = loc.LocId WHERE c.grpid = ?"
                    cursor.execute(query, (grp_id,))
                    row = cursor.fetchone()
                    conn.close()

                    if row and row[0]:
                        name = row[0]
                        self.unknown_id_cache[grp_id] = name
                        return name
        except Exception as e:
            from src.logger import create_logger

            create_logger().error(f"SQLite ID Resolution failed: {e}")

        self.unknown_id_cache[grp_id] = grp_id
        return grp_id

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

        self._name_index.clear()
        self._id_index.clear()

        if "card_ratings" in json_data:
            for k, card in json_data["card_ratings"].items():
                if "deck_colors" in card:
                    card["deck_colors"] = {
                        normalize_color_string(k_color): v_color
                        for k_color, v_color in card["deck_colors"].items()
                    }
                card_name = sanitize_card_name(card.get(DATA_FIELD_NAME))
                if card_name:
                    card[DATA_FIELD_NAME] = card_name
                    self._name_index[card_name] = card
                    self._id_index[card_name] = k

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
                display_name = self._resolve_unknown_id(string_id)

                if display_name and display_name in self._name_index:
                    matched_card = self._name_index[display_name]
                    ratings[string_id] = matched_card
                    card_data.append(matched_card)
                else:
                    is_basic = display_name in [
                        "Plains",
                        "Island",
                        "Swamp",
                        "Mountain",
                        "Forest",
                        "Wastes",
                    ]
                    empty_dict = {
                        DATA_FIELD_NAME: display_name,
                        DATA_FIELD_MANA_COST: "",
                        DATA_FIELD_TYPES: ["Land", "Basic"] if is_basic else [],
                        DATA_SECTION_IMAGES: [],
                    }
                    from src.file_extractor import initialize_card_data

                    initialize_card_data(empty_dict)
                    card_data.append(empty_dict)
        return card_data

    def get_data_by_name(self, name_list: List[str]) -> List[Dict]:
        if not isinstance(name_list, list) or not self._dataset:
            return []
        return [self._name_index[n] for n in name_list if n in self._name_index]

    def get_names_by_id(self, id_list: List[str]) -> List[str]:
        """Restored for test and scanner compatibility."""
        data = self.get_data_by_id(id_list)
        return [c[DATA_FIELD_NAME] for c in data if DATA_FIELD_NAME in c]

    def get_ids_by_name(self, name_list: List[str], return_int: bool = False) -> List:
        """Restored for test and scanner compatibility."""
        if not self._dataset:
            return []
        results = []
        for name in name_list:
            if name in self._id_index:
                val = self._id_index[name]
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
                        [
                            name,
                            color,
                            spec[field],
                            spec.get(WIN_RATE_FIELDS_DICT[field], 0),
                        ]
                    )

        return sorted(archetype_list, key=lambda x: x[3], reverse=True)

from src.utils import Result, check_file_integrity
from src.file_extractor import initialize_card_data
from typing import List, Dict, Tuple
from src.constants import (
    DATA_FIELD_NAME,
    DATA_FIELD_MANA_COST,
    DATA_FIELD_TYPES,
    DATA_FIELD_DECK_COLORS,
    DATA_FIELD_COLORS,
    DATA_SECTION_IMAGES,
    COLOR_NAMES_DICT,
    WIN_RATE_OPTIONS,
    WIN_RATE_FIELDS_DICT
)

class Dataset:
    def __init__(self, retrieve_unknown: bool = False):
        self._dataset = None
        self._retrieve_unknown = retrieve_unknown
        
    def clear(self) -> None:
        """
        Clear the stored dataset
        """
        self._dataset = None
        
    def open_file(self, file_location: str) -> None:
        """
        Open the the dataset file
        """
        result = Result.ERROR_MISSING_FILE
        
        if not file_location:
            return result
            
        result, json_data = check_file_integrity(file_location)
        
        if result != Result.VALID:
            return result
            
        self._dataset = json_data
        
        return result

    def get_data_by_id(self, id_list: List[str]) -> List[Dict]:
        """
        Takes a list of Arena IDs and returns the corresponding card data for each recognized ID in the dataset.
        
        Input Example:
            id_list: ["90662", "90663"] or [90662, 90663]
            
        Output Example:
            card_data: [
                {
                    "name": "Collector's Cage", 
                    "cmc": 2,
                    "mana_cost": "{1}{W}",
                    "isprimarycard": 1,
                    "linkedfacetype": 0,
                    "types": ["Artifact"],
                    "rarity": "mythic", 
                    "image": ["https://cards.scryfall.io/large/front/a/3/a33703bb-51c0-4d57-9d06-1148507ddc4f.jpg?1712352680"], 
                    "colors": ["W"], 
                    "deck_colors": {
                        "All Decks" : {"gihwr": 62.62, "ohwr": 61.41, ....}
                        "W": {"gihwr": 0.0, "ohwr": 0.0, ....}
                        ...
                    }
                },
                {
                    "name": "Grand Abolisher", 
                    "cmc": 2,
                    "mana_cost": "{W}{W}",
                    "isprimarycard": 1,
                    "linkedfacetype": 0,
                    "types": ["Creature"],
                    "rarity": "mythic", 
                    "image": ["https://cards.scryfall.io/large/front/e/e/ee793ed2-7d59-4640-8868-ad486600df2c.jpg?1712352691"], 
                    "colors": ["W"], 
                    "deck_colors": {
                        "All Decks" : {"gihwr": 50.85, "ohwr": 50.98, ....}
                        "W": {"gihwr": 0.0, "ohwr": 0.0, ....}
                        ...
                    }
                }
            ]
        """
        if not isinstance(id_list, list):
            raise ValueError("Input argument must be a list")
        
        card_data = []
        
        for arena_id in id_list:
            string_id = str(arena_id)
            if self._dataset and string_id in self._dataset["card_ratings"]:
                card_data.append(self._dataset["card_ratings"][string_id])
            elif self._retrieve_unknown:
                empty_dict = {
                    DATA_FIELD_NAME: string_id,
                    DATA_FIELD_MANA_COST: "",
                    DATA_FIELD_TYPES: [],
                    DATA_SECTION_IMAGES: []
                }
                initialize_card_data(empty_dict)
                card_data.append(empty_dict)
        
        return card_data
        
    def get_data_by_name(self, name_list: List[str]) -> List[Dict]:
        """
        Takes a list of card names and returns the corresponding card data for each recognized name in the dataset.
        
        Input Example:
            name_list: ["Collector's Cage", "Grand Abolisher"]
            
        Output Example:
            card_data: [
                {
                    "name": "Collector's Cage", 
                    "cmc": 2,
                    "mana_cost": "{1}{W}",
                    "isprimarycard": 1,
                    "linkedfacetype": 0,
                    "types": ["Artifact"],
                    "rarity": "mythic", 
                    "image": ["https://cards.scryfall.io/large/front/a/3/a33703bb-51c0-4d57-9d06-1148507ddc4f.jpg?1712352680"], 
                    "colors": ["W"], 
                    "deck_colors": {
                        "All Decks" : {"gihwr": 62.62, "ohwr": 61.41, ....}
                        "W": {"gihwr": 0.0, "ohwr": 0.0, ....}
                        ...
                    }
                },
                {
                    "name": "Grand Abolisher", 
                    "cmc": 2,
                    "mana_cost": "{W}{W}",
                    "isprimarycard": 1,
                    "linkedfacetype": 0,
                    "types": ["Creature"],
                    "rarity": "mythic", 
                    "image": ["https://cards.scryfall.io/large/front/e/e/ee793ed2-7d59-4640-8868-ad486600df2c.jpg?1712352691"], 
                    "colors": ["W"], 
                    "deck_colors": {
                        "All Decks" : {"gihwr": 50.85, "ohwr": 50.98, ....}
                        "W": {"gihwr": 0.0, "ohwr": 0.0, ....}
                        ...
                    }
                }
            ]
        """
        
        if not isinstance(name_list, list):
            raise ValueError("Input argument must be a list")
        
        card_data = []
        
        # Remove the arena ID part of the dictionary and make the card name the key
        transformed_dataset = {v[DATA_FIELD_NAME]: v for v in self._dataset["card_ratings"].values()}
                
        for name in name_list:
            if self._dataset and name in transformed_dataset:
                card_data.append(transformed_dataset[name])
            elif self._retrieve_unknown:
                empty_dict = {
                    DATA_FIELD_NAME: name,
                    DATA_FIELD_MANA_COST: "",
                    DATA_FIELD_TYPES: [],
                    DATA_SECTION_IMAGES: []
                }
                initialize_card_data(empty_dict)
                card_data.append(empty_dict)
                
        return card_data
    
    def get_names_by_id(self, id_list: List[str]) -> List[str]:
        """
        Takes a list of Arena IDs and returns the corresponding card name for each recognized ID in the dataset.
        
        Input Example:
            name_list: ["90662", "90663","90670"] or [90662, 90663, 90670]
            
        Output Example:
            id_list: ["Collector's Cage", "Grand Abolisher", "Harvester of Misery"]
        """
        if not isinstance(id_list, list):
            raise ValueError("Input argument must be a list")
        
        name_list = []
        
        if self._dataset is None:
            return name_list
            
        for arena_id in id_list:
            string_id = str(arena_id)
            if string_id in self._dataset["card_ratings"]:
                name_list.append(self._dataset["card_ratings"][string_id][DATA_FIELD_NAME])
                
        return name_list
        
    def get_ids_by_name(self, name_list: List[str], return_int: bool = False) -> List[str]:
        """
        Takes a list of card names and returns the corresponding Arena ID for each recognized name in the dataset, returned as an integer or string. 
         If there are multiple entries for a name, the function returns the Arena ID from the last entry.
        
        Input Examples:
            Example 1: 
                name_list: ["Collector's Cage", "Grand Abolisher", "Harvester of Misery"]
                return_int: False
                
            Example 2: 
                name_list: ["Collector's Cage", "Grand Abolisher", "Harvester of Misery"]
                return_int: True
        Output Examples:
            Example 1: 
                id_list: ["90662", "90663","90670"]
            
            Example 2: 
                id_list: [90662, 90663, 90670]
        """
        if not isinstance(name_list, list):
            raise ValueError("name_list argument must be a list")
            
        if not isinstance(return_int, bool):
            raise ValueError("return_int argument must be a bool")
            
        id_list = []
        
        if self._dataset is None:
            return id_list
            
        # Make the name the key and the id the value
        transformed_dataset = {v[DATA_FIELD_NAME]: k for k, v in self._dataset["card_ratings"].items()}
            
        for name in name_list:
            if name in transformed_dataset:
                id_list.append(int(transformed_dataset[name]) if return_int else transformed_dataset[name])
                
        return id_list
        
    def get_color_ratings(self) -> Dict:
        """
        Returns the 'color_ratings' section of the dataset
        """
        color_ratings = {}
        
        if self._dataset is not None:
            color_ratings = self._dataset["color_ratings"]
            
        return color_ratings
        
    def get_card_ratings(self) -> Dict:
        """
        Returns the 'card_ratings' section of the dataset
        """
        card_ratings = {}
        
        if self._dataset is not None:
            card_ratings = self._dataset["card_ratings"]
            
        return card_ratings
        
    def get_all_names(self) -> List[str]:
        """
        Returns a list containing all of the unique card names in the dataset
        
        Output Example:
            name_list: ["Another Round","One Last Job", "Crime /// Punishment", "Port Razer", ...]
        """
        name_list = []
        
        if self._dataset is not None:
            name_list = list(set([v[DATA_FIELD_NAME] for v in self._dataset["card_ratings"].values()]))
        
        return name_list
        
    def get_top_archetypes(self, card_name:str, field:str) -> List[Tuple[str, str]]:
        """
        """
        archetype_list = []

        if field not in WIN_RATE_OPTIONS:
            return archetype_list

        card_data = self.get_data_by_name([card_name])

        if not card_data:
            return archetype_list

        win_rate = card_data[0][DATA_FIELD_DECK_COLORS]["All Decks"][field]
        game_count = card_data[0][DATA_FIELD_DECK_COLORS]["All Decks"][WIN_RATE_FIELDS_DICT[field]]
        if not win_rate:
            return archetype_list
        else:
            archetype_list.append(["", "All Decks", win_rate, game_count])

        temp_list = []

        for color, name in COLOR_NAMES_DICT.items():
            win_rate = card_data[0][DATA_FIELD_DECK_COLORS][color][field]
            game_count = card_data[0][DATA_FIELD_DECK_COLORS][color][WIN_RATE_FIELDS_DICT[field]]
            if win_rate != 0:
                temp_list.append([
                    name, 
                    color, 
                    str(win_rate), 
                    game_count
                ])

        # Sort the list by the field (highest to lowest)
        if temp_list:
            temp_list.sort(key=lambda x: x[3], reverse=True)

        # Combine lists
        archetype_list.extend(temp_list)

        return archetype_list
  
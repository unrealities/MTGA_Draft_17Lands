import json
import time


class SetCombiner:
    def __init__(self):
        self.sets = []
        self.combined = {}

    def load_json(self, file_path):
        with open(file_path, "r") as file:
            data = json.load(file)
            self.sets.append(data)

    def combine_meta(self):
        meta = {}
        for set in self.sets:
            for key, value in set["meta"].items():
                if key not in meta:
                    if "_date" in key:
                        meta[key] = value.split(" ")[0]
                    else:
                        meta[key] = value
                else:
                    if key == "collection_date":
                        if time.strptime(
                            value.split(" ")[0], "%Y-%m-%d"
                        ) > time.strptime(meta[key], "%Y-%m-%d"):
                            meta[key] = value

                    elif key == "start_date":
                        if time.strptime(
                            value.split(" ")[0], "%Y-%m-%d"
                        ) < time.strptime(meta[key], "%Y-%m-%d"):
                            meta[key] = value

                    elif key == "end_date":
                        if time.strptime(
                            value.split(" ")[0], "%Y-%m-%d"
                        ) > time.strptime(meta[key], "%Y-%m-%d"):
                            meta[key] = value

                    elif key == "version":
                        if value > meta[key]:
                            meta[key] = value

                    elif key == "game_count":
                        meta[key] += value
        return meta

    def combine_color_ratings(self):
        color_ratings = {}
        first = True
        for set in self.sets:
            color_ratings_keys = list(color_ratings.keys())
            count = set["meta"]["game_count"]
            if not first:
                for key in color_ratings_keys:
                    if key not in set["color_ratings"].keys():
                        color_ratings.pop(key, None)
            for key, value in set["color_ratings"].items():
                if key not in color_ratings and first:
                    color_ratings[key] = (value / 100) * count
                elif key not in color_ratings and not first:
                    continue
                else:
                    color_ratings[key] += (value / 100) * count
                    color_ratings[key] /= self.combined["meta"]["game_count"]
                    color_ratings[key] = round(color_ratings[key] * 100, 1)
            first = False
        return color_ratings

    def combine_card_ratings(self):
        from constants import COUNTS_DICT
        card_ratings = {}
        
        COUNTS_DICT['pool'] = None
        
        for set_data in self.sets:
            for card_id, card_data in set_data["card_ratings"].items():
                if card_id not in card_ratings:
                    card_ratings[card_id] = {
                        "name": card_data["name"],
                        "cmc": card_data["cmc"],
                        "mana_cost": card_data["mana_cost"], 
                        "isprimarycard": card_data["isprimarycard"],
                        "linkedfacetype": card_data["linkedfacetype"],
                        "types": card_data["types"].copy(),
                        "rarity": card_data["rarity"],
                        "image": card_data["image"].copy(),
                        "colors": card_data["colors"].copy(),
                        "deck_colors": {}
                    }
                
                for color, stats in card_data["deck_colors"].items():
                    if color not in card_ratings[card_id]["deck_colors"]:
                        card_ratings[card_id]["deck_colors"][color] = {}
                    
                    for stat, value in stats.items():
                        if stat in COUNTS_DICT or stat == 'pool':
                            current = card_ratings[card_id]["deck_colors"][color].get(stat, 0)
                            card_ratings[card_id]["deck_colors"][color][stat] = current + value
                        else:
                            count_stat = COUNTS_DICT.get(stat)
                            if count_stat:
                                # If current value exists and is 0.0 or new value is 0.0, result is 0.0
                                current_value = card_ratings[card_id]["deck_colors"][color].get(stat, None)
                                if current_value == 0.0 or value == 0.0:
                                    card_ratings[card_id]["deck_colors"][color][stat] = 0.0
                                else:
                                    # Calculate weighted average only for non-zero values
                                    count = stats.get(count_stat, 0)
                                    current_count = card_ratings[card_id]["deck_colors"][color].get(count_stat, 0)
                                    total_count = current_count + count
                                    if total_count > 0:
                                        weighted_avg = ((current_value * current_count) + (value * count)) / total_count
                                        card_ratings[card_id]["deck_colors"][color][stat] = weighted_avg
                                    else:
                                        card_ratings[card_id]["deck_colors"][color][stat] = value
                            else:
                                # For stats without counts (like iwd)
                                current_value = card_ratings[card_id]["deck_colors"][color].get(stat, None)
                                if current_value == 0.0 or value == 0.0:
                                    card_ratings[card_id]["deck_colors"][color][stat] = 0.0
                                elif current_value is None:
                                    card_ratings[card_id]["deck_colors"][color][stat] = value
                                else:
                                    card_ratings[card_id]["deck_colors"][color][stat] = (current_value + value) / 2

        return card_ratings

    def combine_sets(self):
        self.combined["meta"] = self.combine_meta()
        self.combined["color_ratings"] = self.combine_color_ratings()

        # print(self.sets[0]["card_ratings"]["19577"]["deck_colors"])
        self.combined["card_ratings"] = self.combine_card_ratings()
        print(self.combined)

    def get_combined(self, output_file_path):
        with open(output_file_path, "w") as file:
            json.dump(self.combined, file, indent=4)

import base64
import json
import os
import time
from enum import Enum
from io import BytesIO
from PIL import ImageGrab
from src.constants import (
    LIMITED_USER_GROUP_ALL,
    LIMITED_TYPES_DICT,
    LIMITED_GROUPS_LIST,
    SET_FILE_SUFFIX,
    SETS_FOLDER,
    DATA_FIELD_NAME,
    DATA_FIELD_COLORS,
    DATA_FIELD_CMC,
    DATA_FIELD_TYPES,
    DATA_FIELD_DECK_COLORS,
    DATA_FIELD_GIHWR,
    DATA_FIELD_ALSA,
    DATA_FIELD_IWD,
    DATA_FIELD_MANA_COST,
    DATA_SECTION_IMAGES,
    FILTER_OPTION_ALL_DECKS,
    SCREENSHOT_FOLDER,
    SCREENSHOT_PREFIX,
    DATA_FIELD_SEEN,
    DATA_FIELD_PICKED,
    DATA_FIELD_POOL,
)


class Result(Enum):
    """Enumeration class for file integrity results"""

    VALID = 0
    ERROR_MISSING_FILE = 1
    ERROR_UNREADABLE_FILE = 2


def process_json(obj):
    """
    Convert JSON string with escape characters to a nested dictionary
    """
    if isinstance(obj, dict):
        return {key: process_json(value) for key, value in obj.items()}
    elif isinstance(obj, str):
        try:
            parsed_json = json.loads(obj)
            return process_json(parsed_json)
        except json.JSONDecodeError:
            return obj
    else:
        return obj


def json_find(key, obj):
    """
    Retrieve a value from a nested dictionary using a specified key.
    """
    result = None
    if isinstance(obj, dict):
        if key in obj:
            result = obj[key]
        else:
            for value in obj.values():
                result = json_find(key, value)
                if result is not None:
                    break
    return result


def retrieve_local_set_list(codes, names=None):
    """Scans the Sets folder and returns a list of valid set files"""
    file_list = []
    error_list = []
    for file in os.listdir(SETS_FOLDER):
        try:
            name_segments = file.split("_")
            if len(name_segments) == 4:
                set_code = name_segments[0].upper()
                event_type = name_segments[1]
                user_group = name_segments[2]
                file_suffix = name_segments[3]
            else:
                continue

            if (
                (set_code not in codes)
                or (event_type not in LIMITED_TYPES_DICT)
                or (user_group not in LIMITED_GROUPS_LIST)
                or (file_suffix != SET_FILE_SUFFIX)
            ):
                continue

            if names:
                set_name = list(names)[list(codes).index(name_segments[0].upper())]
            else:
                set_name = set_code

            file_location = os.path.join(SETS_FOLDER, file)
            result, json_data = check_file_integrity(file_location)

            if result == Result.VALID:
                if json_data["meta"]["version"] == 1:
                    start_date, end_date = json_data["meta"]["date_range"].split("->")
                else:
                    start_date = json_data["meta"]["start_date"]
                    end_date = json_data["meta"]["end_date"]

                if "game_count" in json_data["meta"]:
                    game_count = json_data["meta"]["game_count"]
                else:
                    game_count = 0

                file_list.append(
                    (
                        set_name,
                        event_type,
                        user_group,
                        start_date,
                        end_date,
                        file_location,
                        game_count,
                    )
                )
        except Exception as error:
            error_list.append(error)
    return file_list, error_list


def check_file_integrity(filename):
    """Extracts data from a file to determine if it's formatted correctly"""
    result = Result.VALID
    json_data = {}

    try:
        with open(filename, "r", encoding="utf-8", errors="replace") as json_file:
            json_data = json_file.read()
    except FileNotFoundError:
        return Result.ERROR_MISSING_FILE, json_data

    try:
        json_data = json.loads(json_data)

        if json_data.get("meta"):
            meta = json_data["meta"]
            version = meta.get("version")
            if version == 1:
                meta.get("date_range", "").split("->")
            else:
                meta.get("start_date")
                meta.get("end_date")
        else:
            return Result.ERROR_UNREADABLE_FILE, json_data

        cards = json_data.get("card_ratings")
        if isinstance(cards, dict) and len(cards) >= 100:
            for card in cards.values():
                card.get(DATA_FIELD_NAME)
                card.get(DATA_FIELD_COLORS)
                card.get(DATA_FIELD_CMC)
                card.get(DATA_FIELD_TYPES)
                card.get(DATA_FIELD_MANA_COST)
                card.get(DATA_SECTION_IMAGES)
                deck_colors = card.get(DATA_FIELD_DECK_COLORS, {}).get(
                    FILTER_OPTION_ALL_DECKS, {}
                )
                deck_colors.get(DATA_FIELD_GIHWR)
                deck_colors.get(DATA_FIELD_ALSA)
                deck_colors.get(DATA_FIELD_IWD)
                deck_colors.get(DATA_FIELD_SEEN)
                deck_colors.get(DATA_FIELD_PICKED)
                deck_colors.get(DATA_FIELD_POOL)
                break
        else:
            return Result.ERROR_UNREADABLE_FILE, json_data

    except json.JSONDecodeError:
        return Result.ERROR_UNREADABLE_FILE, json_data

    return result, json_data


def capture_screen_base64str(persist):
    """takes a screenshot and returns it as a base64 encoded string"""
    screenshot = ImageGrab.grab()
    buffered = BytesIO()
    screenshot.save(buffered, format="PNG")
    if persist:
        current_timestamp = int(time.time())
        filename = SCREENSHOT_PREFIX + str(current_timestamp) + ".png"
        if not os.path.exists(SCREENSHOT_FOLDER):
            os.makedirs(SCREENSHOT_FOLDER)
        screenshot.save(os.path.join(SCREENSHOT_FOLDER, filename), format="PNG")

    return base64.b64encode(buffered.getvalue()).decode("utf-8")

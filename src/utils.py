import base64
import json
import os
import time
import platform
import subprocess
from enum import Enum
from io import BytesIO
from PIL import ImageGrab
from typing import List
from src.constants import (
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


def retrieve_local_set_list(codes=None, names=None):
    """Scans the Sets folder and returns a list of valid set files"""
    file_list = []
    error_list = []
    for file in os.listdir(SETS_FOLDER):
        try:

            dataset_info = read_dataset_info(file, codes, names)
            if dataset_info:
                file_list.append(dataset_info)
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


def detect_string(search_line: str, search_strings: List[str]) -> int:
    """
    Matches keywords regardless of underscores or spaces.
    Example: 'Event_Join' matches 'EventJoin'. 
    Always returns the index of the first JSON bracket to ensure parsing validity.
    """
    # Normalize for comparison
    norm_line = search_line.upper().replace("_", "").replace(" ", "")
    for pattern in search_strings:
        norm_pattern = pattern.upper().replace("_", "").replace(" ", "")
        if norm_pattern in norm_line:
            # Match found. Find the start of the actual data payload.
            bracket = search_line.find("{")
            return bracket if bracket != -1 else len(search_line)
    return -1


def open_file(file_path: str):
    """
    Open a file in its default application based on the operating system.

    Parameters:
        file_path (str): The path to the file to be opened.

    Behavior:
        - On Windows: Uses os.startfile() to open the file with the default application.
        - On macOS: Uses the 'open' command via subprocess to open the file.
        - On Linux/Unix: Uses the 'xdg-open' command via subprocess to open the file.

    This function ensures cross-platform compatibility for opening files.
    """
    if platform.system() == "Windows":
        os.startfile(file_path)
    elif platform.system() == "Darwin":  # macOS
        subprocess.call(["open", file_path])
    else:  # Linux and other Unix-based systems
        subprocess.call(["xdg-open", file_path])


def clean_string(input_string: str, uppercase: bool = True) -> str:
    """Cleans a string by removing unwanted characters"""
    unwanted_chars = [" ", ".", "/", "_"]
    for char in unwanted_chars:
        input_string = input_string.replace(char, "")
    return input_string.upper() if uppercase else input_string


def read_dataset_info(filename: str, codes=None, names=None):
    """Reads the meta section of a dataset file"""
    name_segments = filename.split("_")
    cleaned_codes = [clean_string(code) for code in codes] if codes else None
    if len(name_segments) == 4:
        set_code = name_segments[0].upper()
        event_type = name_segments[1]
        user_group = name_segments[2]
        file_suffix = name_segments[3]
    else:
        return ()

    if (
        (cleaned_codes and set_code not in cleaned_codes)
        or (event_type not in LIMITED_TYPES_DICT)
        or (user_group not in LIMITED_GROUPS_LIST)
        or (file_suffix != SET_FILE_SUFFIX)
    ):
        return ()

    if names:
        set_name = list(names)[list(cleaned_codes).index(name_segments[0].upper())]
    else:
        set_name = set_code

    file_location = os.path.join(SETS_FOLDER, filename)
    result, json_data = check_file_integrity(file_location)

    if result == Result.VALID:
        if json_data["meta"]["version"] == 1:
            start_date, end_date = json_data["meta"]["date_range"].split("->")
        else:
            start_date = json_data["meta"]["start_date"]
            end_date = json_data["meta"]["end_date"]
        collection_date = json_data["meta"].get("collection_date", "")

        if "game_count" in json_data["meta"]:
            game_count = int(json_data["meta"]["game_count"])
        else:
            game_count = 0

        return (
            set_name,
            event_type,
            user_group,
            start_date,
            end_date,
            game_count,
            file_location,
            collection_date,
        )

    return ()


def normalize_color_string(color_string: str) -> str:
    """
    Standardizes any combination of color symbols (GW, WG, RUG)
    to MTG WUBRG order (WG, WR, URG).
    """
    from src.constants import CARD_COLORS  # ["W", "U", "B", "R", "G"]

    if not color_string or color_string in ["All Decks", "Auto"]:
        return color_string

    # Clean input: Keep only valid WUBRG symbols
    symbols = [c for c in str(color_string).upper() if c in CARD_COLORS]

    # Sort based on the WUBRG index defined in constants
    # White(0) < Blue(1) < Black(2) < Red(3) < Green(4)
    sorted_symbols = sorted(list(set(symbols)), key=lambda x: CARD_COLORS.index(x))

    return "".join(sorted_symbols)

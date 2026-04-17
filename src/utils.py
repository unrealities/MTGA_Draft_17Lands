import json
import os
import time
import platform
import subprocess
from enum import Enum
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
)
from src.logger import create_logger

logger = create_logger()


class Result(Enum):
    """Enumeration class for file integrity results"""

    VALID = 0
    ERROR_MISSING_FILE = 1
    ERROR_UNREADABLE_FILE = 2


def process_json(obj):
    """
    Convert JSON string with escape characters to a nested dictionary.
    Includes sanitization for malformed, unescaped MTGA logs.
    """
    if isinstance(obj, dict):
        return {key: process_json(value) for key, value in obj.items()}
    elif isinstance(obj, str):
        try:
            parsed_json = json.loads(obj)
            return process_json(parsed_json)
        except json.JSONDecodeError:
            # MTG Arena occasionally outputs broken, unescaped JSON (e.g. "request":"{"DraftId":"123"}")
            # We intercept this, strip the outer string quotes, and reconstruct it into a valid nested dict.
            sanitized = (
                obj.strip()
                .replace('"request":"{', '"request":{')
                .replace('"Payload":"{', '"Payload":{')
            )
            if sanitized.endswith('}"}'):
                sanitized = sanitized[:-3] + "}}"

            try:
                parsed_sanitized = json.loads(sanitized)
                return process_json(parsed_sanitized)
            except:
                pass
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


_LOCAL_SET_CACHE = {"mtime": 0.0, "files": []}


def invalidate_local_set_cache():
    global _LOCAL_SET_CACHE
    _LOCAL_SET_CACHE["mtime"] = 0.0


def retrieve_local_set_list(codes=None, names=None):
    """Scans the Sets folder and returns a list of valid set files (Highly Cached)"""
    global _LOCAL_SET_CACHE
    file_list = []
    error_list = []

    try:
        current_mtime = os.path.getmtime(SETS_FOLDER)
    except OSError:
        current_mtime = 0.0

    # CACHE HIT: Bypass the heavy JSON file reading entirely
    if (
        current_mtime != 0.0
        and current_mtime == _LOCAL_SET_CACHE["mtime"]
        and _LOCAL_SET_CACHE["files"]
    ):
        all_files = _LOCAL_SET_CACHE["files"]
    else:
        # CACHE MISS - Deep Scan (Runs only on boot or when a new dataset is downloaded)
        all_files = []
        if os.path.exists(SETS_FOLDER):
            for file in os.listdir(SETS_FOLDER):
                try:
                    # Read without codes/names filter to cache the raw underlying data
                    dataset_info = read_dataset_info(file, None, None)
                    if dataset_info:
                        all_files.append(dataset_info)
                except Exception as error:
                    error_list.append(error)
        _LOCAL_SET_CACHE["mtime"] = current_mtime
        _LOCAL_SET_CACHE["files"] = all_files

    # APPLY FILTERS INSTANTLY
    cleaned_codes = [clean_string(code) for code in codes] if codes else None

    for f in all_files:
        (
            set_name,
            event_type,
            user_group,
            start_date,
            end_date,
            game_count,
            file_location,
            collection_date,
        ) = f
        filename = os.path.basename(file_location)
        name_segments = filename.split("_")
        if not name_segments:
            continue

        set_code = name_segments[0].upper()
        cleaned_set_code = clean_string(set_code)

        if cleaned_codes and cleaned_set_code not in cleaned_codes:
            continue

        display_name = set_name
        if names and cleaned_codes and cleaned_set_code in cleaned_codes:
            try:
                display_name = list(names)[list(cleaned_codes).index(cleaned_set_code)]
            except ValueError:
                pass

        file_list.append(
            (
                display_name,
                event_type,
                user_group,
                start_date,
                end_date,
                game_count,
                file_location,
                collection_date,
            )
        )

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
            logger.error(f"Validation Failed: Missing 'meta' field in {filename}")
            return Result.ERROR_UNREADABLE_FILE, json_data

        cards = json_data.get("card_ratings")
        if isinstance(cards, dict) and len(cards) >= 10:
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
            count = len(cards) if isinstance(cards, dict) else 0
            logger.error(
                f"Validation Failed: Insufficient cards ({count} < 10) in {filename}"
            )
            return Result.ERROR_UNREADABLE_FILE, json_data

    except json.JSONDecodeError as e:
        logger.error(f"Validation Failed: JSON Decode Error in {filename}: {e}")
        return Result.ERROR_UNREADABLE_FILE, json_data
    except Exception as e:
        logger.error(f"Validation Failed: Unexpected Error in {filename}: {e}")
        return Result.ERROR_UNREADABLE_FILE, json_data

    return result, json_data


def detect_string(search_line: str, search_strings: List[str]) -> int:
    """
    Robustly identifies the start of a JSON block in an Arena log line.
    Indifferent to underscores, spaces, or casing.
    """
    # FAST PATH 1: If there's no JSON payload, immediately skip
    json_start = search_line.find("{")
    if json_start == -1:
        return -1

    # FAST PATH 2: Exact substring match (Solves massive CPU freezing on huge logs)
    for pattern in search_strings:
        if pattern in search_line:
            return json_start

    # SLOW PATH: Fallback to heavily sanitized matching if WOTC changed formatting
    norm_line = search_line.upper().replace("_", "").replace(" ", "")
    for pattern in search_strings:
        norm_pattern = pattern.upper().replace("_", "").replace(" ", "")
        if norm_pattern in norm_line:
            return json_start

    return -1


def open_file(file_path: str):
    """
    Open a file in its default application based on the operating system.
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

    is_custom = False

    # NEW: Handle Custom Datasets (5 segments: SET_EVENT_GROUP_CUSTOMSTAMP_Data.json)
    if len(name_segments) == 5:
        set_code = name_segments[0].upper()
        event_type = name_segments[1]
        user_group = name_segments[2]
        # name_segments[3] is the "Custom-12345678" stamp
        file_suffix = name_segments[4]
        is_custom = True
    # STANDARD: Official Datasets (4 segments: SET_EVENT_GROUP_Data.json)
    elif len(name_segments) == 4:
        set_code = name_segments[0].upper()
        event_type = name_segments[1]
        user_group = name_segments[2]
        file_suffix = name_segments[3]
    else:
        return ()

    cleaned_set_code = clean_string(set_code)

    if (
        (cleaned_codes and cleaned_set_code not in cleaned_codes)
        or (event_type not in LIMITED_TYPES_DICT)
        or (user_group not in LIMITED_GROUPS_LIST)
        or (file_suffix != SET_FILE_SUFFIX)
    ):
        return ()

    if names and cleaned_codes and cleaned_set_code in cleaned_codes:
        try:
            set_name = list(names)[list(cleaned_codes).index(cleaned_set_code)]
        except ValueError:
            set_name = set_code
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

        if is_custom:
            try:
                s = f"{start_date[5:7]}/{start_date[8:10]}"
                e = f"{end_date[5:7]}/{end_date[8:10]}"
                user_group = f"{user_group} ({s}-{e})"
            except Exception:
                user_group = f"{user_group} (Custom)"

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


def is_cache_stale(filepath: str, hours: int = 24) -> bool:
    """Checks if a file is older than the specified hours."""
    if not os.path.exists(filepath):
        return True
    file_age_seconds = time.time() - os.path.getmtime(filepath)
    return file_age_seconds > (hours * 3600)


def sanitize_card_name(name: str) -> str:
    from src.constants import CARD_NAME_CORRECTIONS

    if not name:
        return name

    # 1. Exact match (fast path)
    if name in CARD_NAME_CORRECTIONS:
        return CARD_NAME_CORRECTIONS[name]

    # 2. Prevent recursive duplication if it's already fully corrected
    if name in CARD_NAME_CORRECTIONS.values():
        return name

    # 3. Substring correction for weird encoding artifacts
    for bad, good in CARD_NAME_CORRECTIONS.items():
        if bad in name:
            name = name.replace(bad, good)

    return name


def bind_scroll(widget, scroll_command):
    """
    Applies cross-platform mouse wheel bindings to a Tkinter widget.
    Smoothly handles OS-specific Delta calculation quirks.
    """
    import sys

    if sys.platform == "darwin":
        widget.bind(
            "<MouseWheel>", lambda e: scroll_command(-1 * e.delta, "units"), add="+"
        )
    elif sys.platform == "win32":
        widget.bind(
            "<MouseWheel>",
            lambda e: scroll_command(-1 * (int(e.delta) // 120), "units"),
            add="+",
        )
    else:
        # Linux / X11
        widget.bind("<Button-4>", lambda e: scroll_command(-1, "units"), add="+")
        widget.bind("<Button-5>", lambda e: scroll_command(1, "units"), add="+")

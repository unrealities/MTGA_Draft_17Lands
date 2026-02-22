"""
src/limited_sets.py
Metadata management for Magic sets and 17Lands compatibility.
"""

import datetime
import json
import re
import ssl
import time
import os
import urllib.request
from typing import Dict, List, Tuple
from pydantic import BaseModel, Field
from src import constants
from src.logger import create_logger
from src.constants import APPLICATION_VERSION

logger = create_logger()

LIMITED_SETS_VERSION = 7
TOTAL_SCRYFALL_SETS = 50
DATE_SHIFT_OFFSET_DAYS = -30
CACHE_DURATION_SECONDS = 86400

TEMP_FOLDER = os.path.join(os.getcwd(), "Temp")
if not os.path.exists(TEMP_FOLDER):
    os.makedirs(TEMP_FOLDER)
TEMP_LIMITED_SETS = os.path.join(TEMP_FOLDER, "temp_set_list.json")

REPLACE_PHRASE_LATEST = "{LATEST}"
REPLACE_PHRASE_DATE_SHIFT = "{DATESHIFT}"
START_DATE_DEFAULT = "2019-01-01"

# Headers to prevent HTTP 400/403 errors from Scryfall/17Lands
# Scryfall requires a User-Agent and accepts application/json
USER_AGENT = f"MTGADraftTool/{APPLICATION_VERSION}"
ACCEPT = "application/json;q=0.9,*/*;q=0.8"
API_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": ACCEPT,
}


class SetInfo(BaseModel):
    arena: List[str] = Field(default_factory=list)
    scryfall: List[str] = Field(default_factory=list)
    seventeenlands: List[str] = Field(default_factory=list)
    formats: List[str] = Field(default_factory=list)
    set_code: str = ""
    start_date: str = START_DATE_DEFAULT


class SpecialEvent(BaseModel):
    label: str = ""
    type: str = ""
    set_code: str = ""
    keywords: List[str] = Field(default_factory=list)
    number_of_players: int = 8


class SetDictionary(BaseModel):
    version: int = 0
    latest_set: str = ""
    data: Dict[str, SetInfo] = Field(default_factory=dict)
    special_events: List[SpecialEvent] = [
        SpecialEvent(
            label="OpenDay1",
            type="Sealed",
            set_code=REPLACE_PHRASE_LATEST,
            keywords=["ArenaOpen", "Day1"],
        ),
        SpecialEvent(
            label="OpenDay2",
            type="PremierDraft",
            set_code=REPLACE_PHRASE_LATEST,
            keywords=["ArenaOpen", "Day2"],
        ),
        SpecialEvent(
            label="QualSealed",
            type="Sealed",
            set_code=REPLACE_PHRASE_LATEST,
            keywords=["Qualifier"],
        ),
        SpecialEvent(
            label="QualDraft",
            type="PremierDraft",
            set_code=REPLACE_PHRASE_LATEST,
            keywords=["Qualifier", "Draft"],
        ),
    ]


def shift_date(start_date, shifted_days, string_format, next_dow=None):
    try:
        shifted_date = start_date + datetime.timedelta(days=shifted_days)
        if next_dow is not None and (0 <= next_dow <= 6):
            shifted_date += datetime.timedelta((next_dow - shifted_date.weekday()) % 7)
        return shifted_date, (
            shifted_date.strftime(string_format) if string_format else ""
        )
    except Exception as error:
        logger.error(error)
        return datetime.date.min, ""


class LimitedSets:
    def __init__(self, sets_file_location: str = TEMP_LIMITED_SETS):
        self.sets_file_location = sets_file_location
        self.limited_sets = SetDictionary()
        self.sets_scryfall = SetDictionary()
        self.sets_17lands = SetDictionary()
        self.context = ssl.create_default_context()
        self.latest_set = ""

    def retrieve_limited_sets(self) -> SetDictionary:
        self.limited_sets = SetDictionary()
        if self._is_cache_valid():
            logger.info("Using cached set list.")
            self.limited_sets, _ = self.read_sets_file()
            self.__substitute_strings()
            return self.limited_sets

        logger.info("Cache expired or missing. Fetching new set list from network.")
        self.retrieve_17lands_sets()
        self.retrieve_scryfall_sets()
        self.__assemble_limited_sets()
        self.__substitute_strings()
        self.write_sets_file(self.limited_sets)
        return self.limited_sets

    def _is_cache_valid(self) -> bool:
        if not os.path.exists(self.sets_file_location):
            return False
        try:
            return (
                time.time() - os.path.getmtime(self.sets_file_location)
            ) < CACHE_DURATION_SECONDS
        except Exception:
            return False

    def retrieve_scryfall_sets(self, retries: int = 3, wait: int = 5) -> SetDictionary:
        self.sets_scryfall = SetDictionary()
        url = "https://api.scryfall.com/sets"

        while retries:
            try:
                req = urllib.request.Request(url, headers=API_HEADERS)
                url_data = urllib.request.urlopen(req, context=self.context).read()
                set_json_data = json.loads(url_data)
                self.__process_scryfall_sets(set_json_data["data"])

                while set_json_data["has_more"]:
                    url = set_json_data["next_page"]
                    req = urllib.request.Request(url, headers=API_HEADERS)
                    url_data = urllib.request.urlopen(req, context=self.context).read()
                    set_json_data = json.loads(url_data)
                    self.__process_scryfall_sets(set_json_data["data"])
                break
            except Exception as error:
                logger.error(f"limited_sets.retrieve_scryfall_sets - {error}")
                retries -= 1
                if retries:
                    time.sleep(wait)
        return self.sets_scryfall

    def retrieve_17lands_sets(self, retries: int = 3, wait: int = 5) -> SetDictionary:
        self.sets_17lands = SetDictionary()
        url = "https://www.17lands.com/data/filters"

        while retries:
            try:
                req = urllib.request.Request(url, headers=API_HEADERS)
                url_data = urllib.request.urlopen(req, context=self.context).read()
                set_json_data = json.loads(url_data)
                self.__process_17lands_sets(set_json_data)
                break
            except Exception as error:
                logger.error(f"limited_sets.retrieve_17lands_sets - {error}")
                retries -= 1
                if retries:
                    time.sleep(wait)
        return self.sets_17lands

    def read_sets_file(self) -> Tuple[SetDictionary, bool]:
        temp_sets = SetDictionary(version=LIMITED_SETS_VERSION)
        success = False
        try:
            with open(self.sets_file_location, "r", encoding="utf-8") as f:
                json_data = json.loads(f.read())
            sets_object = SetDictionary.model_validate(json_data)
            if sets_object.version < LIMITED_SETS_VERSION:
                return temp_sets, success
            temp_sets = sets_object
            success = True
        except Exception:
            pass
        return temp_sets, success

    def write_sets_file(self, sets_object: SetDictionary) -> bool:
        try:
            sets_object.version = LIMITED_SETS_VERSION
            with open(self.sets_file_location, "w", encoding="utf-8") as file:
                json.dump(sets_object.model_dump(), file, indent=4)
            return True
        except Exception as e:
            logger.error(f"Failed to write sets file: {e}")
            return False

    def __assemble_limited_sets(self) -> None:
        read_sets, _ = self.read_sets_file()
        if self.latest_set:
            read_sets.latest_set = self.latest_set
        if self.sets_17lands.data:
            self.limited_sets = self.__append_limited_sets(read_sets)
        else:
            self.limited_sets = read_sets

    def __append_limited_sets(self, read_sets: SetDictionary) -> SetDictionary:
        temp_dict = SetDictionary(version=LIMITED_SETS_VERSION)
        alchemy_sets = {}

        if self.sets_scryfall.data and self.sets_17lands.data:
            set_codes_to_remove = []

            for set_name, set_fields in self.sets_scryfall.data.items():
                set_code = set_fields.seventeenlands[0]
                if set_code in self.sets_17lands.data:
                    if re.match(r"^Y\d{2}[A-Za-z]{3}$", set_code):
                        alchemy_sets[set_name] = self.sets_17lands.data[set_code]
                    else:
                        temp_dict.data[set_name] = self.sets_17lands.data[set_code]
                    set_codes_to_remove.append(set_code)
            for set_code, set_fields in self.sets_17lands.data.items():
                if set_code not in set_codes_to_remove:
                    if re.match(r"^Y\d{2}[A-Za-z]{3}$", set_code):
                        alchemy_sets[set_code] = set_fields
                    else:
                        temp_dict.data[set_code] = set_fields

        temp_dict.data.update(read_sets.data)
        temp_dict.data.update(alchemy_sets)
        temp_dict.latest_set = str(read_sets.latest_set)  # Cast to str for tests
        return temp_dict

    def __process_17lands_sets(self, data: dict):
        try:
            for card_set in data["expansions"]:
                self.sets_17lands.data[card_set] = SetInfo(
                    arena=[constants.SET_SELECTION_ALL],
                    seventeenlands=[card_set],
                    set_code=card_set.split(" ")[0].upper(),
                )
            for card_set, date_string in data["start_dates"].items():
                if card_set in self.sets_17lands.data:
                    self.sets_17lands.data[card_set].start_date = (
                        REPLACE_PHRASE_DATE_SHIFT
                        if "Cube" in card_set
                        else date_string.split("T")[0]
                    )
            for card_set, formats in data["formats_by_expansion"].items():
                if card_set in self.sets_17lands.data:
                    self.sets_17lands.data[card_set].formats = [
                        x for x in formats if x in constants.LIMITED_TYPE_LIST
                    ] + [x for x in constants.LIMITED_TYPE_LIST if x not in formats]
            if self.sets_17lands.data:
                self.latest_set = self.sets_17lands.data[
                    next(iter(self.sets_17lands.data))
                ].set_code
        except Exception as error:
            logger.error(error)

    def __process_scryfall_sets(self, data: Dict):
        counter = len(self.sets_scryfall.data)
        for card_set in data:
            try:
                set_name, set_code = card_set["name"], card_set["code"]
                if card_set["set_type"] in constants.SUPPORTED_SET_TYPES:
                    if counter >= TOTAL_SCRYFALL_SETS:
                        break
                    if card_set["set_type"] == constants.SET_TYPE_ALCHEMY:
                        self.sets_scryfall.data[set_name] = (
                            self.__process_scryfall_sets_alchemy(set_code, card_set)
                        )
                    elif (card_set["set_type"] == constants.SET_TYPE_MASTERS) and (
                        not card_set["digital"]
                    ):
                        continue
                    else:
                        self.sets_scryfall.data[set_name] = SetInfo(
                            arena=[constants.SET_SELECTION_ALL],
                            seventeenlands=[set_code.upper()],
                        )
                    counter += 1
            except Exception as error:
                logger.error(error)

    def __process_scryfall_sets_alchemy(self, set_code: str, data: Dict) -> SetInfo:
        if ("parent_set_code" in data) and ("block_code" in data):
            return SetInfo(
                arena=[constants.SET_SELECTION_ALL],
                seventeenlands=[
                    f"{data['block_code'].upper()}{data['parent_set_code'].upper()}"
                ],
            )
        elif ("block_code" in data) and (
            re.findall(r"^[yY]\d{2}$", data["block_code"])
        ):
            parent_code = re.findall(r"^[yY](\w{3})$", set_code)
            if parent_code:
                return SetInfo(
                    arena=[constants.SET_SELECTION_ALL],
                    seventeenlands=[
                        f"{data['block_code'].upper()}{parent_code[0].upper()}"
                    ],
                )
        return SetInfo(
            arena=[constants.SET_SELECTION_ALL], seventeenlands=[set_code.upper()]
        )

    def __substitute_strings(self):
        latest = str(self.latest_set or self.limited_sets.latest_set)
        for event in self.limited_sets.special_events:
            if event.set_code == REPLACE_PHRASE_LATEST and latest:
                event.set_code = latest

        for data in self.limited_sets.data.values():
            if data.start_date == REPLACE_PHRASE_DATE_SHIFT:
                data.start_date = str(
                    shift_date(
                        datetime.date.today(), DATE_SHIFT_OFFSET_DAYS, "%Y-%m-%d"
                    )[1]
                )

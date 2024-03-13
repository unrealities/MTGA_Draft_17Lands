import copy
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

logger = create_logger()


class SetInfo(BaseModel):
    arena: List[str] = Field(default_factory=list)
    scryfall: List[str] = Field(default_factory=list)
    seventeenlands: List[str] = Field(default_factory=list)
    start_date: str = ""


class SetDictionary(BaseModel):
    data: Dict[str, SetInfo] = Field(default_factory=dict)


CUSTOM_SETS = {
    "dbl": SetInfo(arena=[constants.SET_SELECTION_ALL], scryfall=[], seventeenlands=["DBL"]),
    "sir": SetInfo(arena=[constants.SET_SELECTION_ALL], scryfall=[], seventeenlands=["SIR"]),
    "mat": SetInfo(arena=[constants.SET_SELECTION_ALL], scryfall=[], seventeenlands=["MAT"]),
}

TOTAL_SCRYFALL_SETS = 50
SET_ARENA_CUBE_START_OFFSET_DAYS = -25
TEMP_LIMITED_SETS = os.path.join("Temp", "temp_set_list.json")


def shift_date(start_date, shifted_days, string_format, next_dow=None):
    '''Shifts a date by a certain number of days'''
    shifted_date_string = ""
    shifted_date = datetime.date.min
    try:
        shifted_date = start_date + datetime.timedelta(days=shifted_days)

        if next_dow and (0 <= next_dow <= 6):
            # Shift the date to the next specified day of the week (0 = Monday, 6 = Sunday)
            shifted_date += datetime.timedelta(
                (next_dow - shifted_date.weekday()) % 7)

        shifted_date_string = shifted_date.strftime(
            string_format) if string_format else ""

    except Exception as error:
        logger.error(error)

    return shifted_date, shifted_date_string


class LimitedSets:
    def __init__(self, sets_file_location: str = TEMP_LIMITED_SETS):
        self.sets_file_location: str = sets_file_location
        self.limited_sets: SetDictionary()
        self.sets_scryfall = SetDictionary()
        self.sets_17lands = SetDictionary()
        self.context: ssl.SSLContext = ssl.SSLContext()

    def retrieve_limited_sets(self) -> SetDictionary:
        '''Retrieve a list of sets from 17Lands and Scryfall

            Set fields
           . "arena" : The codes for the sets retrieved from the temp_card_data.json.
               - This is the primary way that this application builds the card dataset
               - Key word "ALL" can be used (e.g., "arena" : ["ALL"]) if all Arena cards are required (e.g., if you're builing a cube dataset)
           . "scryfall" : The codes for the sets retrieved using the scryfall API
               - Example: https://api.scryfall.com/cards/search?order=set&unique=prints&q=e%3AMID
               - This is the secondary way that this application builds the card dataset, in the event that there's an issue temp_card_data.json
               - It's not feasible to download data for every card listed on Scryfall so the all keyword can't be used with this field
           . "17Lands" : The code for the data listed on the https://www.17lands.com/card_ratings page
               - The dataset file name uses the set code from this field (e.g., MAT_PremierDraft_Data.json)
               - When searching the Arena player log, the application uses this set code to link the event set to the card dataset
                   - Examples:
                        - CubeDraft_Arena_20220812 -> CUBE_PremierDraft_Data.json
                        - PremierDraft_BRO_20221115 -> BRO_PremierDraft_Data.json
        '''
        self.limited_sets = SetDictionary()

        self.retrieve_17lands_sets()
        self.retrieve_scryfall_sets()

        self.__assemble_limited_sets()

        return self.limited_sets

    def retrieve_scryfall_sets(self, retries: int = 3, wait: int = 5) -> SetDictionary:
        '''Retrieve a list of Magic sets using the Scryfall API'''
        self.sets_scryfall = SetDictionary()

        while retries:
            try:
                url = "https://api.scryfall.com/sets"
                url_data = urllib.request.urlopen(
                    url, context=self.context).read()
                set_json_data = json.loads(url_data)

                self.__process_scryfall_sets(set_json_data["data"])

                while set_json_data["has_more"]:
                    url = set_json_data["next_page"]
                    url_data = urllib.request.urlopen(
                        url, context=self.context).read()
                    set_json_data = json.loads(url_data)
                    self.__process_scryfall_sets(set_json_data["data"])

                break

            except Exception as error:
                logger.error(error)

            retries -= 1

            if retries:
                time.sleep(wait)

        return self.sets_scryfall

    def retrieve_17lands_sets(self, retries: int = 3, wait: int = 5) -> SetDictionary:
        '''Retrieve the list of sets that are supported by 17Lands'''
        self.sets_17lands = SetDictionary()
        while retries:
            try:
                url = "https://www.17lands.com/data/filters"
                url_data = urllib.request.urlopen(
                    url, context=self.context).read()
                set_json_data = json.loads(url_data)

                self.__process_17lands_sets(set_json_data)
                break

            except Exception as error:
                logger.error(error)

            retries -= 1

            if retries:
                time.sleep(wait)

        return self.sets_17lands

    def read_sets_file(self) -> Tuple[SetDictionary, bool]:
        '''Read the sets file and build the sets object'''
        self.limited_sets = SetDictionary()
        success = False
        try:
            with open(self.sets_file_location, 'r', encoding="utf-8", errors="replace") as json_file:
                json_data = json.loads(json_file.read())

            sets_object = SetDictionary.parse_obj(json_data)

            if not sets_object.data:
                return self.limited_sets, success

            sets_to_remove = []
            for set_name, set_info in sets_object.data.items():
                self.limited_sets.data[set_name] = set_info
                set_code = set_info.seventeenlands[0]
                if set_code in self.sets_17lands.data:
                    sets_to_remove.append(set_code)

            for set_code in sets_to_remove:
                del self.sets_17lands.data[set_code]

            success = True
        except (FileNotFoundError, json.JSONDecodeError) as error:
            logger.error(error)

        return self.limited_sets, success

    def write_sets_file(self, sets_object: SetDictionary) -> bool:
        '''Write the sets object data to a local file'''
        success = False
        try:
            if type(sets_object) != SetDictionary:
                raise TypeError("sets_object must be of type SetDictionary")

            # Create the directory if it's missing
            os.makedirs(os.path.dirname(
                self.sets_file_location), exist_ok=True)

            with open(self.sets_file_location, 'w', encoding="utf-8", errors="replace") as file:
                json.dump(sets_object.dict(), file,
                          ensure_ascii=False, indent=4)

            success = True
        except (FileNotFoundError, TypeError, OSError) as error:
            logger.error(error)

        return success

    def __assemble_limited_sets(self) -> None:
        '''Retrieve a stored set dataset and append any missing set that are listed on 17Lands'''

        # Retrieve a stored sets dataset from the Temp folder
        self.limited_sets, _ = self.read_sets_file()

        if self.sets_17lands:
            # Add any missing sets to the dataset
            self.limited_sets = self.__append_limited_sets()

            # store the modified dataset in the Temp folder
            self.write_sets_file(self.limited_sets)

        return

    def __append_limited_sets(self) -> SetDictionary:
        '''Create a list of sets using lists collected from 17Lands and Scryfall'''
        temp_dict = SetDictionary()
        if self.sets_scryfall.data and self.sets_17lands.data:
            set_codes_to_remove = []
            # If the application is able to collect the set list from Scryfall and 17Lands, then it will use the 17Lands list to filter the Scryfall list
            for code in self.sets_17lands.data:
                for set_name, set_fields in self.sets_scryfall.data.items():
                    set_code = set_fields.seventeenlands[0]
                    if set_code == code:
                        temp_dict.data[set_name] = set_fields
                        set_codes_to_remove.append(code)
                        break

            # Remove the set codes from self.sets_17lands
            for code in set_codes_to_remove:
                del self.sets_17lands.data[code]

        # Insert any 17Lands sets that were not collected from Scryfall
        temp_dict.data.update(self.sets_17lands.data)
        temp_dict.data.update(self.limited_sets.data)

        return temp_dict

    def __process_17lands_sets(self, data: dict):
        '''Parse json data from the 17lands filters page'''
        try:
            for card_set in data["expansions"]:
                self.sets_17lands.data[card_set.upper()] = SetInfo(arena=[constants.SET_SELECTION_ALL],
                                                                   scryfall=[],
                                                                   seventeenlands=[card_set.upper()])
            for card_set, date_string in data["start_dates"].items():
                if card_set.upper() in self.sets_17lands.data:
                    self.sets_17lands.data[card_set.upper()].start_date = date_string.split('T')[
                        0]

        except Exception as error:
            logger.error(error)

        return

    def __process_scryfall_sets(self, data: Dict):
        '''Parse the Scryfall set list data to extract information for sets that are supported by Arena
           - Scryfall lists all Magic sets (paper and digital), so the application needs to filter out non-Arena sets
           - The application will only display sets that have been released

           This process links the bonus sheets to the main sets by checking for a "parent_set_code" field and linking the set to its parent.
           - Examples:
              - "mul" is linked to "mom" because "mul" has a "parent_set_code" of "mom"
              - "sis" isn't linked to "sir" because "sis" doens't have a "parent_set_code"
           - If the set has linked sets that can't be identified using the process above, then they need to be added to the CUSTOM_SETS dictionary
        '''
        counter = len(self.sets_scryfall.data)
        side_sets = {}
        for card_set in data:
            try:

                set_name = card_set["name"]
                set_code = card_set["code"]

                if set_code in CUSTOM_SETS:
                    # Only retrieve the last X sets + CUBE
                    if counter >= TOTAL_SCRYFALL_SETS:
                        break
                    counter += 1
                    self.sets_scryfall.data[set_name] = copy.deepcopy(
                        CUSTOM_SETS[set_code])
                elif card_set["set_type"] in constants.SUPPORTED_SET_TYPES:
                    # Only retrieve the last X sets + CUBE
                    if counter >= TOTAL_SCRYFALL_SETS:
                        break
                    if card_set["set_type"] == constants.SET_TYPE_ALCHEMY:
                        self.sets_scryfall.data[set_name] = self.__process_scryfall_sets_alchemy(
                            set_code, card_set)
                    elif (card_set["set_type"] == constants.SET_TYPE_MASTERS) and (not card_set["digital"]):
                        continue
                    else:
                        self.sets_scryfall.data[set_name] = SetInfo(
                            arena=[constants.SET_SELECTION_ALL],
                            seventeenlands=[set_code.upper()]
                        )
                    counter += 1
                elif (card_set["set_type"] == constants.SET_TYPE_MASTERPIECE and
                      "parent_set_code" in card_set):
                    # Add the supplementary sets (i.e., mystic archives, retro artifacts)
                    parent_code = card_set["parent_set_code"].upper()
                    if parent_code in side_sets:
                        side_sets[parent_code].append(set_code.upper())
                    else:
                        side_sets[parent_code] = [set_code.upper()]

            except Exception as error:
                logger.error(error)

        # Insert the cube set
        self.sets_scryfall.data["Arena Cube"] = SetInfo(
            arena=[constants.SET_SELECTION_ALL],
            scryfall=[],
            seventeenlands=["CUBE"],
            start_date=shift_date(
                datetime.date.today(), SET_ARENA_CUBE_START_OFFSET_DAYS, "%Y-%m-%d")[1]
        )

        return

    def __process_scryfall_sets_alchemy(self, set_code: str, data: Dict) -> SetInfo:
        '''Process Scryfall sets for Alchemy specific information'''
        set_entry = SetInfo()
        if ("parent_set_code" in data) and ("block_code" in data):
            set_entry.arena = [constants.SET_SELECTION_ALL]
            set_entry.seventeenlands = [
                f"{data['block_code'].upper()}{data['parent_set_code'].upper()}"]

        elif ("block_code" in data) and (re.findall(r"^[yY]\d{2}$", data["block_code"], re.DOTALL)):
            parent_code = re.findall(
                r"^[yY](\w{3})$", set_code, re.DOTALL)

            if parent_code:
                set_entry.arena = [constants.SET_SELECTION_ALL]
                set_entry.seventeenlands = [
                    f"{data['block_code'].upper()}{parent_code[0].upper()}"]

            else:
                set_entry = SetInfo(
                    arena=[constants.SET_SELECTION_ALL],
                    seventeenlands=[set_code.upper()]
                )
        else:
            set_entry = SetInfo(
                arena=[constants.SET_SELECTION_ALL],
                seventeenlands=[set_code.upper()]
            )
        return set_entry

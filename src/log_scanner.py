"""This module contains the functions that are used for parsing the Arena log"""
import os
import json
import re
import logging
import src.constants as constants
import src.card_logic as CL
import src.file_extractor as FE
from enum import Enum
from datetime import datetime
from src.logger import create_logger
from src.set_metrics import SetMetrics
from src.dataset import Dataset
from src.ocr import OCR
from src.utils import (
    process_json,
    json_find,
    Result,
    retrieve_local_set_list,
    capture_screen_base64str,
    detect_string,
)

if not os.path.exists(constants.DRAFT_LOG_FOLDER):
    os.makedirs(constants.DRAFT_LOG_FOLDER)

LOG_TYPE_DRAFT = "draftLog"

logger = create_logger()

class Source(Enum):
    REFRESH = 1
    UPDATE = 2

class ArenaScanner:
    '''Class that handles the processing of the information within Arena Player.log file'''

    def __init__(self, filename, set_list, sets_location: str = constants.SETS_FOLDER, step_through: bool = False, retrieve_unknown: bool = False):
        self.arena_file = filename
        self.set_list = set_list
        self.draft_log = logging.getLogger(LOG_TYPE_DRAFT)
        self.draft_log.setLevel(logging.INFO)
        self.sets_location = sets_location

        self.logging_enabled = False
        
        self.step_through = step_through
        self.set_data = Dataset(retrieve_unknown)
        self.draft_type = constants.LIMITED_TYPE_UNKNOWN
        self.pick_offset = 0
        self.pack_offset = 0
        self.search_offset = 0
        self.draft_start_offset = 0
        self.draft_sets = []
        self.current_pick = 0
        self.current_pack = 0
        self.number_of_players = 8
        self.picked_cards = [[] for i in range(self.number_of_players)]
        self.taken_cards = []
        self.sideboard = []
        self.pack_cards = [[]] * self.number_of_players
        self.initial_pack = [[]] * self.number_of_players
        self.previous_picked_pack = 0
        self.current_picked_pick = 0
        self.file_size = 0
        self.data_source = "None"
        self.event_string = ""
        self.draft_label = ""

    def set_arena_file(self, filename):
        '''Public function that's used for storing the location of the Player.log file'''
        self.arena_file = filename

    def log_enable(self, enable):
        '''Enable/disable the application draft log feature that records draft data in a log file within the Logs folder'''
        self.logging_enabled = enable
        self.log_suspend(not enable)

    def log_suspend(self, suspended):
        '''Prevents the application from updating the draft log file'''
        if suspended:
            self.draft_log.setLevel(logging.CRITICAL)
        elif self.logging_enabled:
            self.draft_log.setLevel(logging.INFO)

    def __new_log(self, card_set, event, draft_id):
        '''Create a new draft log file'''
        try:
            log_name = f"DraftLog_{card_set}_{event}_{draft_id}.log"
            log_path = os.path.join(constants.DRAFT_LOG_FOLDER, log_name)
            for handler in self.draft_log.handlers:
                if isinstance(handler, logging.FileHandler):
                    self.draft_log.removeHandler(handler)
            formatter = logging.Formatter(
                '%(asctime)s,%(message)s', datefmt='<%d%m%Y %H:%M:%S>')
            new_handler = logging.FileHandler(log_path, delay=True)
            new_handler.setFormatter(formatter)
            self.draft_log.addHandler(new_handler)
            logger.info("Creating new draft log: %s", log_path)
        except Exception as error:
            logger.error(error)

    def clear_draft(self, full_clear):
        '''Clear the stored draft data collected from the Player.log file'''
        if full_clear:
            self.search_offset = 0
            self.draft_start_offset = 0
            self.file_size = 0
        self.set_data.clear()
        self.draft_type = constants.LIMITED_TYPE_UNKNOWN
        self.pick_offset = 0
        self.pack_offset = 0
        self.draft_sets = None
        self.current_pick = 0
        self.number_of_players = 8
        self.picked_cards = [[] for i in range(self.number_of_players)]
        self.taken_cards = []
        self.sideboard = []
        self.pack_cards = [[]] * self.number_of_players
        self.initial_pack = [[]] * self.number_of_players
        self.current_pack = 0
        self.previous_picked_pack = 0
        self.current_picked_pick = 0
        self.data_source = "None"
        self.draft_label = ""

    def draft_start_search(self):
        '''Search for the string that represents the start of a draft'''
        update = False
        event_type = ""
        event_line = ""
        draft_id = ""

        try:
            # Check if a new player.log was created (e.g. application was started before Arena was started)
            arena_file_size = os.path.getsize(self.arena_file)
            if self.file_size > arena_file_size:
                self.clear_draft(True)
                logger.info(
                    "New Arena Log Detected (%d), (%d)", self.file_size, arena_file_size)
            self.file_size = arena_file_size
            offset = self.search_offset
            with open(self.arena_file, 'r', encoding="utf-8", errors="replace") as log:
                log.seek(offset)
                while True:
                    line = log.readline()
                    if not line:
                        break
                    offset = log.tell()
                    self.search_offset = offset
                    start_offset = detect_string(line, constants.DRAFT_START_STRINGS)
                    if start_offset != -1:
                        self.draft_start_offset = offset
                        entry_string = line[start_offset:]
                        event_data = process_json(entry_string)
                        update, event_type, draft_id = self.__check_event(event_data)
                        event_line = line
            if update:
                self.__new_log(self.draft_sets[0], event_type, draft_id)
                self.draft_log.info(event_line)
                self.pick_offset = self.draft_start_offset
                self.pack_offset = self.draft_start_offset
                logger.info(
                    "New draft detected %s, %s", event_type, self.draft_sets)
        except Exception as error:
            logger.error(error)

        return update

    def __check_event(self, event_data):
        '''Parse a draft start string and extract pertinent information'''
        update = False
        event_type = ""
        draft_id = ""
        try:
            draft_id = json_find("id", event_data)
            event_name = json_find("EventName", event_data)
            logger.info("Event found %s", event_name)
            event_match, event_type, event_label, event_set, number_of_players = self.__check_special_event(event_name)
            if not event_match:
                event_match, event_type, event_label, event_set, number_of_players = self.__check_standard_event(event_name)
                
            if event_match:
                self.clear_draft(False)
                self.draft_type = constants.LIMITED_TYPES_DICT[event_type]
                self.draft_sets = event_set
                self.draft_label = event_label
                self.event_string = event_name
                self.number_of_players = number_of_players
                update = True

        except Exception as error:
            logger.error(error)

        return update, event_type, draft_id
        
    def __check_special_event(self, event_name):
        ''''''
        event_match = False
        event_type = ""
        event_label = ""
        event_set = ""
        number_of_players = 8

        for event in self.set_list.special_events:
            if (
                event.type in constants.LIMITED_TYPES_DICT and
                all(x in event_name for x in event.keywords)
            ):
                event_type = event.type
                # Truncate the string to prevent the label from increasing the width of the main window when displayed
                event_label = event.label[:12]
                event_set = [event.set_code]
                number_of_players = 4 if constants.PICK_TWO_EVENT_STRING in event_name else event.number_of_players
                event_match = True
                break
                
        return event_match, event_type, event_label, event_set, number_of_players
        
    def __check_standard_event(self, event_name):
        ''''''
        event_match = False
        event_type = ""
        event_label = ""
        event_set = []
        number_of_players = 8
        event_sections = event_name.split('_')
        
        # Find event type in event string
        events = [i for i in constants.LIMITED_TYPES_DICT
                  for x in event_sections if i in x]
        if not events and [i for i in constants.DRAFT_DETECTION_CATCH_ALL for x in event_sections if i in x]:
            # Unknown draft events will be parsed as premier drafts
            events.append(constants.LIMITED_TYPE_STRING_DRAFT_PREMIER)

        if events:
            # Handle Cube events specifically to be more future-proof
            if "Cube" in event_name:
                # Find all known cube sets from the available data
                cube_sets = {name: info for name, info in self.set_list.data.items() if "Cube" in name}
                
                # Sort by name length, descending, to match more specific variants first (e.g., "Powered Cube" before "Arena Cube")
                sorted_cube_names = sorted(cube_sets.keys(), key=len, reverse=True)

                # Look for a keyword from the known cube names (e.g., "Powered") in the event string
                for cube_name in sorted_cube_names:
                    # Strip "Cube" and whitespace to get the unique keyword, e.g., "Powered"
                    keyword = cube_name.replace("Cube", "").strip() 
                    if keyword and keyword.lower() in event_name.lower():
                        event_set = cube_sets[cube_name].seventeenlands
                        break  # Found the most specific match, stop searching
                
                # If no specific variant was found, default to generic "CUBE"
                if not event_set:
                    event_set = ["CUBE"]
            else:
                # Find set name within the event string for non-Cube events
                event_set = [i.seventeenlands[0] for i in self.set_list.data.values()
                             for x in event_sections if i.seventeenlands[0].lower() in x.lower()]
                # Remove duplicates while retaining order
                event_set = list(dict.fromkeys(event_set))

            event_set = ["UNKN"] if not event_set else event_set

            if events[0] == constants.LIMITED_TYPE_STRING_SEALED:
                # Trad_Sealed_NEO_20220317
                event_type = constants.LIMITED_TYPE_STRING_TRAD_SEALED if "Trad" in event_sections else constants.LIMITED_TYPE_STRING_SEALED
            else:
                event_type = events[0]
            event_label = event_type
            event_match = True
            number_of_players = 4 if constants.PICK_TWO_EVENT_STRING in event_name else 8
            
        return event_match, event_type, event_label, event_set, number_of_players
                

    def draft_data_search(self, use_ocr, save_screenshot):
        '''Collect draft data from the Player.log file based on the current active format'''
        update = False
        previous_pick = self.current_pick
        previous_pack = self.current_pack
        previous_picked = self.current_picked_pick

        if (
            self.draft_type == constants.LIMITED_TYPE_DRAFT_PREMIER_V1 or
            self.draft_type == constants.LIMITED_TYPE_DRAFT_PICK_TWO
        ):
            # Use OCR to retrieve P1P1
            if use_ocr:
                self.__get_ocr_pack(save_screenshot)
            # Backup - collect the P1P1 cards from the log
            self.__draft_pack_search_premier_p1p1()
            self.__draft_pack_search_premier_v1()
            self.__draft_picked_search_premier_v1()
        elif self.draft_type == constants.LIMITED_TYPE_DRAFT_PREMIER_V2:
            # Use OCR to retrieve P1P1
            if use_ocr:
                self.__get_ocr_pack(save_screenshot)
            self.__draft_pack_search_premier_p1p1()
            self.__draft_pack_search_premier_v2()
            self.__draft_picked_search_premier_v2()
        elif (
            self.draft_type == constants.LIMITED_TYPE_DRAFT_QUICK or
            self.draft_type == constants.LIMITED_TYPE_DRAFT_PICK_TWO_QUICK
        ):
            self.__draft_picked_search_quick()
            self.__draft_pack_search_quick()
        elif (
            self.draft_type == constants.LIMITED_TYPE_DRAFT_TRADITIONAL or
            self.draft_type == constants.LIMITED_TYPE_DRAFT_PICK_TWO_TRAD
        ):
            # Use OCR to retrieve P1P1
            if use_ocr:
                self.__get_ocr_pack(save_screenshot)
            self.__draft_pack_search_traditional_p1p1()
            self.__draft_pack_search_traditional()
            self.__draft_picked_search_traditional()
        elif ((self.draft_type == constants.LIMITED_TYPE_SEALED)
                or (self.draft_type == constants.LIMITED_TYPE_SEALED_TRADITIONAL)):
            update = self.__sealed_pack_search()
        if not update:
            if ((previous_pack != self.current_pack) or
                (previous_pick != self.current_pick) or
                (previous_picked != self.current_picked_pick)):
                update = True

        return update
    def __get_ocr_pack(self, persist):
        try:  
            # Exit if the draft is past P1P1
            if self.current_pack != 0 or self.current_pick != 0:
                return

            card_names = self.set_data.get_all_names()

            # Exit if the dataset isn't available - Data Source is 'None'
            if not card_names:
                return

            screenshot = capture_screen_base64str(persist)
            received_names = OCR().get_pack(card_names, screenshot)

            # Convert the card names to Arena IDs so that the existing pack parsing logic can be used
            pack_cards = self.set_data.get_ids_by_name(received_names)

            # Exit if there are no recognizable cards in the OCR results
            if not pack_cards:
                return

            # initial_pack: the contents of the pack when it's first seen
            # pack_cards: the current contents of the pack
            # The app is recording both of these to determine which cards didn't wheel.
            self.initial_pack[0] = pack_cards
            self.pack_cards[0] = pack_cards
            self.current_pack = 1
            self.current_pick = 1

        except Exception as error:
            logger.error(error)

    def __draft_pack_search_premier_p1p1(self):
        '''Parse premier draft string that contains the P1P1 pack data'''
        offset = self.pack_offset
        draft_data = object()
        pack_cards = []
        pack = 0
        pick = 0
        # Identify and print out the log lines that contain the draft packs
        try:
            with open(self.arena_file, 'r', encoding="utf-8", errors="replace") as log:
                log.seek(offset)

                while True:
                    line = log.readline()
                    if not line:
                        break
                    offset = log.tell()

                    if detect_string(line, [constants.DRAFT_P1P1_STRING_PREMIER]) != -1:
                        # Remove any prefix (e.g. log timestamp)
                        start_offset = line.find("{\"id\":")
                        self.draft_log.info(line)
                        entry_string = line[start_offset:]
                        draft_data = process_json(entry_string)

                        pack_cards = []
                        try:
                            cards = json_find(constants.DRAFT_P1P1_STRING_PREMIER, draft_data)

                            for card in cards:
                                pack_cards.append(str(card))

                            pack = json_find("PackNumber", draft_data)
                            pick = json_find("PickNumber", draft_data)
                            
                            # Exit if you're not receiving P1P1
                            if pack != 1 or pick != 1:
                                break

                            pack_index = (pick - 1) % self.number_of_players

                            if self.current_pack != pack:
                                self.initial_pack = [[]] * self.number_of_players

                            if len(self.initial_pack[pack_index]) == 0:
                                self.initial_pack[pack_index] = pack_cards

                            self.pack_cards[pack_index] = pack_cards

                            if (self.current_pack == 0) and (self.current_pick == 0):
                                self.current_pack = pack
                                self.current_pick = pick

                            if self.step_through:
                                break
                        except Exception as error:
                            self.draft_log.info(
                                "__draft_pack_search_premier_p1p1 Sub Error: %s", error)
        except Exception as error:
            self.draft_log.info(
                "__draft_pack_search_premier_p1p1 Error: %s", error)

        return pack_cards

    def __draft_picked_search_premier_v1(self):
        '''Parse the premier draft string that contains the player pick information'''
        offset = self.pick_offset
        draft_data = object()
        pack = 0
        pick = 0
        # Identify and print out the log lines that contain the draft packs
        try:
            with open(self.arena_file, 'r', encoding="utf-8", errors="replace") as log:
                log.seek(offset)

                while True:
                    line = log.readline()
                    if not line:
                        break
                    offset = log.tell()
                    if detect_string(line, [constants.DRAFT_PICK_STRING_PREMIER]) != -1:
                        self.pick_offset = offset
                        start_offset = line.find("{\"id\"")
                        self.draft_log.info(line)

                        try:
                            # Identify the pack
                            entry_string = line[start_offset:]
                            draft_data = process_json(entry_string)

                            pack = int(json_find("Pack", draft_data))
                            pick = int(json_find("Pick", draft_data))
                            if "GrpIds" in entry_string:
                                cards = json_find("GrpIds", draft_data)
                            else:
                                cards = [str(json_find("GrpId", draft_data))]

                            pack_index = (pick - 1) % self.number_of_players

                            if self.previous_picked_pack != pack:
                                self.picked_cards = [[] for i in range(self.number_of_players)]

                            self.picked_cards[pack_index].extend(cards)
                            self.taken_cards.extend(cards)

                            self.previous_picked_pack = pack
                            self.current_picked_pick = pick

                            if self.step_through:
                                break

                        except Exception as error:
                            self.draft_log.info(
                                "__draft_picked_search_premier_v1 Error: %s", error)
        except Exception as error:
            self.draft_log.info(
                "__draft_picked_search_premier_v1 Error: %s", error)

    def __draft_pack_search_premier_v1(self):
        '''Parse the premier draft string that contains the non-P1P1 pack data'''
        offset = self.pack_offset
        draft_data = object()
        pack_cards = []
        pack = 0
        pick = 0
        # Identify and print out the log lines that contain the draft packs
        try:
            with open(self.arena_file, 'r', encoding="utf-8", errors="replace") as log:
                log.seek(offset)

                while True:
                    line = log.readline()
                    if not line:
                        break
                    offset = log.tell()

                    if detect_string(line, [constants.DRAFT_PACK_STRING_PREMIER]) != -1:
                        self.pack_offset = offset
                        start_offset = line.find("{\"draftId\"")
                        self.draft_log.info(line)
                        pack_cards = []
                        # Identify the pack
                        entry_string = line[start_offset:]
                        draft_data = process_json(entry_string)
                        try:
                            cards = str(json_find("PackCards", draft_data)).split(',')

                            for card in cards:
                                pack_cards.append(str(card))

                            pack = json_find("SelfPack", draft_data)
                            pick = json_find("SelfPick", draft_data)

                            pack_index = (pick - 1) % self.number_of_players

                            if self.current_pack != pack:
                                self.initial_pack = [[]] * self.number_of_players

                            if len(self.initial_pack[pack_index]) == 0:
                                self.initial_pack[pack_index] = pack_cards

                            self.pack_cards[pack_index] = pack_cards

                            self.current_pack = pack
                            self.current_pick = pick

                            if self.step_through:
                                break

                        except Exception as error:
                            self.draft_log.info(
                                "__draft_pack_search_premier_v1 Error: %s", error)

        except Exception as error:
            self.draft_log.info(
                "__draft_pack_search_premier_v1 Error: %s", error)
        return pack_cards

    def __draft_pack_search_premier_v2(self):
        '''Parse the premier draft string that contains the non-P1P1 pack data'''
        offset = self.pack_offset
        draft_data = object()
        pack_cards = []
        pack = 0
        pick = 0
        # Identify and print out the log lines that contain the draft packs
        try:
            with open(self.arena_file, 'r', encoding="utf-8", errors="replace") as log:
                log.seek(offset)

                while True:
                    line = log.readline()
                    if not line:
                        break
                    offset = log.tell()

                    string_offset = detect_string(line, [constants.DRAFT_PACK_STRING_PREMIER])
                    if string_offset != -1:
                        self.pack_offset = offset
                        self.draft_log.info(line)
                        pack_cards = []
                        # Identify the pack
                        draft_data = json.loads(line[string_offset:])
                        try:

                            cards = str(draft_data["PackCards"]).split(',')

                            for card in cards:
                                pack_cards.append(str(card))

                            pack = draft_data["SelfPack"]
                            pick = draft_data["SelfPick"]

                            pack_index = (pick - 1) % self.number_of_players

                            if self.current_pack != pack:
                                self.initial_pack = [[]] * self.number_of_players

                            if len(self.initial_pack[pack_index]) == 0:
                                self.initial_pack[pack_index] = pack_cards

                            self.pack_cards[pack_index] = pack_cards

                            self.current_pack = pack
                            self.current_pick = pick

                            if self.step_through:
                                break

                        except Exception as error:
                            self.draft_log.info(
                                "__draft_pack_search_premier_v2 Error: %s", error)

        except Exception as error:
            self.draft_log.info(
                "__draft_pack_search_premier_v2 Error: %s", error)
        return pack_cards

    def __draft_picked_search_premier_v2(self):
        '''Parse the premier draft string that contains the player pick data'''
        offset = self.pick_offset
        draft_data = object()
        pack = 0
        pick = 0
        # Identify and print out the log lines that contain the draft packs
        try:
            with open(self.arena_file, 'r', encoding="utf-8", errors="replace") as log:
                log.seek(offset)

                while True:
                    line = log.readline()
                    if not line:
                        break
                    offset = log.tell()

                    string_offset = detect_string(line, [constants.DRAFT_PICK_STRING_PREMIER_OLD])
                    if string_offset != -1:
                        self.draft_log.info(line)
                        self.pick_offset = offset
                        try:
                            # Identify the pack
                            draft_data = json.loads(line[string_offset:])

                            request_data = json.loads(draft_data["request"])
                            param_data = request_data["params"]

                            pack = int(param_data["packNumber"])
                            pick = int(param_data["pickNumber"])

                            if "cardIds" in param_data:
                                cards = param_data["cardIds"]
                            else:
                                cards = [param_data["cardId"]]

                            pack_index = (pick - 1) % self.number_of_players

                            if self.previous_picked_pack != pack:
                                self.picked_cards = [[] for i in range(self.number_of_players)]

                            self.picked_cards[pack_index].extend(cards)
                            self.taken_cards.extend(cards)

                            self.previous_picked_pack = pack
                            self.current_picked_pick = pick

                            if self.step_through:
                                break

                        except Exception as error:
                            self.draft_log.info(
                                "__draft_picked_search_premier_v2 Error: %s", error)

        except Exception as error:
            self.draft_log.info(
                "__draft_picked_search_premier_v2 Error: %s", error)

    def __draft_pack_search_quick(self):
        '''Parse the quick draft string that contains the current pack data'''
        offset = self.pack_offset
        draft_data = object()
        pack_cards = []
        pack = 0
        pick = 0
        # Identify and print out the log lines that contain the draft packs
        try:
            with open(self.arena_file, 'r', encoding="utf-8", errors="replace") as log:
                log.seek(offset)

                while True:
                    line = log.readline()
                    if not line:
                        break
                    offset = log.tell()

                    if detect_string(line, [constants.DRAFT_PACK_STRING_QUICK]) != -1:
                        self.pack_offset = offset
                        # Remove any prefix (e.g. log timestamp)
                        start_offset = line.find("{\"CurrentModule\"")
                        self.draft_log.info(line)
                        entry_string = line[start_offset:]
                        draft_data = process_json(entry_string)
                        
                        draft_status = json_find("DraftStatus", draft_data)

                        if draft_status == "PickNext":
                            pack_cards = []
                            try:
                                cards = json_find(constants.DRAFT_PACK_STRING_QUICK, draft_data)

                                for card in cards:
                                    pack_cards.append(str(card))

                                pack = int(json_find("PackNumber", draft_data)) + 1
                                pick = int(json_find("PickNumber", draft_data)) + 1
                                
                                pack_index = (pick - 1) % self.number_of_players

                                if self.current_pack != pack:
                                    self.initial_pack = [[]] * self.number_of_players

                                if len(self.initial_pack[pack_index]) == 0:
                                    self.initial_pack[pack_index] = pack_cards

                                self.pack_cards[pack_index] = pack_cards

                                self.current_pack = pack
                                self.current_pick = pick

                                # Transfer "PickedCards" to taken_cards if the previous picks were missed
                                if not self.taken_cards:
                                    picks = json_find("PickedCards", draft_data)
                                    if picks:
                                        self.taken_cards.extend(picks)

                                if self.step_through:
                                    break

                            except Exception as error:
                                self.draft_log.info(
                                    "__draft_pack_search_quick Error: %s", error)
        except Exception as error:
            self.draft_log.info("__draft_pack_search_quick Error: %s", error)

        return pack_cards

    def __draft_picked_search_quick(self):
        '''Parse the quick draft string that contains the player pick data'''
        offset = self.pick_offset
        draft_data = object()
        pack = 0
        pick = 0
        # Identify and print out the log lines that contain the draft packs
        try:
            with open(self.arena_file, 'r', encoding="utf-8", errors="replace") as log:
                log.seek(offset)

                while True:
                    line = log.readline()
                    if not line:
                        break
                    offset = log.tell()

                    string_offset = detect_string(line, [constants.DRAFT_PICK_STRING_QUICK])
                    if string_offset != -1:
                        self.draft_log.info(line)
                        self.pick_offset = offset
                        try:
                            # Identify the pack
                            entry_string = line[string_offset:]
                            draft_data = process_json(entry_string)

                            pack = int(json_find("PackNumber", draft_data)) + 1
                            pick = int(json_find("PickNumber", draft_data)) + 1
                            if "CardIds" in entry_string:
                                cards = json_find("CardIds", draft_data)
                            else:
                                cards = [str(json_find("CardId", draft_data))]

                            pack_index = (pick - 1) % self.number_of_players

                            if self.previous_picked_pack != pack:
                                self.picked_cards = [[] for i in range(self.number_of_players)]

                            self.previous_picked_pack = pack
                            self.current_picked_pick = pick

                            self.picked_cards[pack_index].extend(cards)
                            self.taken_cards.extend(cards)

                            if self.step_through:
                                break

                        except Exception as error:
                            self.draft_log.info(
                                "__draft_picked_search_quick Error: %s", error)
        except Exception as error:
            self.draft_log.info("__draft_picked_search_quick Error: %s", error)

    def __draft_pack_search_traditional_p1p1(self):
        '''Parse the traditional draft string that contains the P1P1 pack data'''
        offset = self.pack_offset
        draft_data = object()
        pack_cards = []
        pack = 0
        pick = 0
        # Identify and print out the log lines that contain the draft packs
        try:
            with open(self.arena_file, 'r', encoding="utf-8", errors="replace") as log:
                log.seek(offset)

                while True:
                    line = log.readline()
                    if not line:
                        break
                    offset = log.tell()

                    if detect_string(line, [constants.DRAFT_P1P1_STRING_PREMIER]) != -1:
                        # Remove any prefix (e.g. log timestamp)
                        start_offset = line.find("{\"id\":")
                        self.draft_log.info(line)
                        entry_string = line[start_offset:]
                        draft_data = process_json(entry_string)
                        
                        pack_cards = []
                        try:

                            cards = json_find(constants.DRAFT_P1P1_STRING_PREMIER, draft_data)

                            for card in cards:
                                pack_cards.append(str(card))

                            pack = json_find("PackNumber", draft_data)
                            pick = json_find("PickNumber", draft_data)

                            # Exit if you're not receiving P1P1
                            if pack != 1 or pick != 1:
                                break

                            pack_index = (pick - 1) % self.number_of_players

                            if self.current_pack != pack:
                                self.initial_pack = [[]] * self.number_of_players

                            if len(self.initial_pack[pack_index]) == 0:
                                self.initial_pack[pack_index] = pack_cards

                            self.pack_cards[pack_index] = pack_cards

                            if (self.current_pack == 0) and (self.current_pick == 0):
                                self.current_pack = pack
                                self.current_pick = pick

                            if self.step_through:
                                break

                        except Exception as error:
                            self.draft_log.info(
                                "__draft_pack_search_traditional_p1p1 Error: %s", error)
        except Exception as error:
            self.draft_log.info(
                "__draft_pack_search_traditional_p1p1 Error: %s", error)

        return pack_cards

    def __draft_picked_search_traditional(self):
        '''Parse the traditional draft string that contains the player pick data'''
        offset = self.pick_offset
        draft_data = object()
        pack = 0
        pick = 0
        # Identify and print out the log lines that contain the draft packs
        try:
            with open(self.arena_file, 'r', encoding="utf-8", errors="replace") as log:
                log.seek(offset)

                while True:
                    line = log.readline()
                    if not line:
                        break
                    offset = log.tell()

                    if detect_string(line, [constants.DRAFT_PICK_STRING_PREMIER]) != -1:
                        self.pick_offset = offset
                        start_offset = line.find("{\"id\"")
                        self.draft_log.info(line)

                        try:
                            # Identify the pack
                            entry_string = line[start_offset:]
                            draft_data = process_json(entry_string)

                            pack = int(json_find("Pack", draft_data))
                            pick = int(json_find("Pick", draft_data))
                            if "GrpIds" in entry_string:
                                cards = json_find("GrpIds", draft_data)
                            else:
                                cards = [str(json_find("GrpId", draft_data))]

                            pack_index = (pick - 1) % self.number_of_players

                            if self.previous_picked_pack != pack:
                                self.picked_cards = [[] for i in range(self.number_of_players)]

                            self.picked_cards[pack_index].extend(cards)
                            self.taken_cards.extend(cards)

                            self.previous_picked_pack = pack
                            self.current_picked_pick = pick

                            if self.step_through:
                                break

                        except Exception as error:
                            self.draft_log.info(
                                "__draft_picked_search_traditional Error: %s", error)
        except Exception as error:
            self.draft_log.info(
                "__draft_picked_search_traditional Error: %s", error)

    def __draft_pack_search_traditional(self):
        '''Parse the quick draft string that contains the non-P1P1 pack data'''
        offset = self.pack_offset
        draft_data = object()
        pack_cards = []
        pack = 0
        pick = 0
        # Identify and print out the log lines that contain the draft packs
        try:
            with open(self.arena_file, 'r', encoding="utf-8", errors="replace") as log:
                log.seek(offset)

                while True:
                    line = log.readline()
                    if not line:
                        break
                    offset = log.tell()

                    if detect_string(line, [constants.DRAFT_PACK_STRING_PREMIER]) != -1:
                        self.pack_offset = offset
                        start_offset = line.find("{\"draftId\"")
                        self.draft_log.info(line)
                        pack_cards = []
                        # Identify the pack
                        entry_string = line[start_offset:]
                        draft_data = process_json(entry_string)
                        try:
                            cards = str(json_find("PackCards", draft_data)).split(',')

                            for card in cards:
                                pack_cards.append(str(card))

                            pack = json_find("SelfPack", draft_data)
                            pick = json_find("SelfPick", draft_data)

                            pack_index = (pick - 1) % self.number_of_players

                            if self.current_pack != pack:
                                self.initial_pack = [[]] * self.number_of_players

                            if len(self.initial_pack[pack_index]) == 0:
                                self.initial_pack[pack_index] = pack_cards

                            self.pack_cards[pack_index] = pack_cards

                            self.current_pack = pack
                            self.current_pick = pick

                            if self.step_through:
                                break

                        except Exception as error:
                            self.draft_log.info(
                                "__draft_pack_search_traditional Error: %s", error)

        except Exception as error:
            self.draft_log.info(
                "__draft_pack_search_traditional Error: %s", error)
        return pack_cards

    def __sealed_pack_search(self):
        '''Parse sealed string that contains all of the card data'''
        offset = self.pack_offset
        draft_string = f'\"InternalEventName\":\"{self.event_string}\"'
        update = False
        # Identify and print out the log lines that contain the draft packs
        try:
            with open(self.arena_file, 'r', encoding="utf-8", errors="replace") as log:
                log.seek(offset)

                while True:
                    line = log.readline()
                    if not line:
                        break
                    offset = log.tell()

                    #string_offset = line.find(draft_string)
                    if (draft_string in line) and ("CardPool" in line):
                        try:
                            self.pack_offset = offset
                            self.draft_log.info(line)

                            if "Courses" in line:
                                start_offset = line.find("{\"Courses\"")
                                course_data = json.loads(line[start_offset:])
                                for course in course_data["Courses"]:
                                    if course["InternalEventName"] == self.event_string:
                                        card_pool = [str(x) for x in course["CardPool"]]
                                        self.__sealed_update(card_pool)
                                        update = True
                            elif "Course" in line:
                                start_offset = line.find("{\"Course\"")
                                course_data = process_json(line[start_offset:])
                                if course_data["Course"]["InternalEventName"] == self.event_string:
                                    card_pool = [str(x) for x in course_data["Course"]["CardPool"]]
                                    self.__sealed_update(card_pool)
                                    update = True
                        except Exception as error:
                            self.draft_log.info(
                                "__sealed_pack_search Error: %s", error)

        except Exception as error:
            self.draft_log.info("__sealed_pack_search Error: %s", error)
        return update
        
    def __sealed_update(self, cards):
        
        if not self.taken_cards:
            self.taken_cards.extend(cards)

    def retrieve_data_sources(self):
        '''Return a list of set files that can be used with the current active draft'''
        data_sources = {}

        try:
            if self.draft_type != constants.LIMITED_TYPE_UNKNOWN:
                draft_list = list(constants.LIMITED_TYPES_DICT.keys())
                draft_type = [x for x in draft_list if constants.LIMITED_TYPES_DICT[x] == self.draft_type][0]

                file_list, error_list = retrieve_local_set_list(self.draft_sets)

                # Log all of errors generated by retrieve_local_set_list
                for error_string in error_list:
                    logger.error(error_string)

                # Sort the list by draft type and end date
                if file_list:
                    file_list.sort(key=lambda x: (
                        datetime.strptime(x[4], "%Y-%m-%d") if x[1] == draft_type else datetime.min,  # Sort matching events by newest to oldest
                        x[1] != draft_type,  # Sort non-matching events
                    ), reverse=True)  # Reverse sorting order

                for file in file_list:
                    set_code = file[0]
                    event_type = file[1]
                    user_group = file[2]
                    location = file[6]
                    # Alchemy sets use the [Y##]{event_type} ({user_group}) naming scheme and everything else uses <event_type> ({user_group}) scheme
                    type_string = f"[{set_code[0:3]}]{event_type} ({user_group})" if re.findall(r"^[Yy]\d{2}", set_code) else f"{event_type} ({user_group})"
                    data_sources[type_string] = location

        except Exception as error:
            logger.error(error)

        if not data_sources:
            data_sources = constants.DATA_SOURCES_NONE

        return data_sources

    def retrieve_set_data(self, file):
        '''Retrieve set data from the set data files'''
        result = Result.ERROR_MISSING_FILE
        self.set_data.clear()

        try:
            result = self.set_data.open_file(file)

        except Exception as error:
            logger.error(error)

        return result

    def retrieve_set_metrics(self):
        '''Parse set data and calculate the mean and standard deviation for a set'''
        set_metrics = SetMetrics(self.set_data)

        return set_metrics

    def retrieve_color_win_rate(self, label_type):
        '''Parse set data and return a list of color win rates'''
        deck_colors = {}
        for colors in constants.DECK_FILTERS:
            deck_color = colors
            if (label_type == constants.DECK_FILTER_FORMAT_NAMES) and (deck_color in constants.COLOR_NAMES_DICT):
                deck_color = constants.COLOR_NAMES_DICT[deck_color]
            deck_colors[colors] = deck_color

        try:
            color_ratings = self.set_data.get_color_ratings()
            if color_ratings:
                for colors in color_ratings:
                    for deck_color in deck_colors:
                        if (len(deck_color) == len(colors)) and set(deck_color).issubset(colors):
                            filter_label = deck_color
                            if (label_type == constants.DECK_FILTER_FORMAT_NAMES) and (deck_color in constants.COLOR_NAMES_DICT):
                                filter_label = constants.COLOR_NAMES_DICT[deck_color]
                            ratings_string = filter_label + \
                                f' ({color_ratings[colors]}%)'
                            deck_colors[deck_color] = ratings_string
        except Exception as error:
            logger.error(error)

        # Switch key and value
        deck_colors = {v: k for k, v in deck_colors.items()}

        return deck_colors

    def retrieve_current_picked_cards(self):
        '''Return the card data for the card that was picked from the current pack'''
        picked_cards = []

        pack_index = max(self.current_pick - 1, 0) % self.number_of_players

        if pack_index < len(self.picked_cards):
            picked_cards = self.set_data.get_data_by_id(self.picked_cards[pack_index])

        return picked_cards

    def retrieve_current_missing_cards(self):
        '''Retrieve a list of missing cards from the current pack'''
        missing_cards = []

        try:
            pack_index = max(self.current_pick - 1, 0) % self.number_of_players

            if pack_index < len(self.pack_cards):
                # Retrieve the cards from the current pack
                current_pack_cards = self.pack_cards[pack_index]

            if pack_index < len(self.initial_pack):
                # Retrieve the cards that were initially in the current pack
                initial_pack_cards = self.initial_pack[pack_index]

            # Identify the missing cards by removing the taken card and the current cards from the initial pack
            card_list = [
                x for x in initial_pack_cards if x not in current_pack_cards]
            missing_cards = self.set_data.get_data_by_id(card_list)
        except Exception as error:
            logger.error(error)

        return missing_cards

    def retrieve_current_pack_cards(self):
        '''Return the cards from the current pack'''
        pack_cards = []

        pack_index = max(self.current_pick - 1, 0) % self.number_of_players

        if pack_index < len(self.pack_cards):
            pack_cards = self.set_data.get_data_by_id(self.pack_cards[pack_index])

        return pack_cards

    def retrieve_taken_cards(self):
        '''Return the card data for all of the cards that were picked during the draft'''
        taken_cards = self.set_data.get_data_by_id(self.taken_cards)
        return taken_cards

    def retrieve_current_pack_and_pick(self):
        '''Return the current pack and pick numbers (p1p1 is current_pack=1, current_pick=1)'''
        return self.current_pack, self.current_pick

    def retrieve_current_limited_event(self):
        '''Return the set code string and event type string'''
        event_set = ""
        event_type = ""

        try:
            event_set = self.draft_sets[0] if self.draft_sets else ""
            event_type = self.draft_label
        except Exception as error:
            logger.error(error)

        return event_set, event_type

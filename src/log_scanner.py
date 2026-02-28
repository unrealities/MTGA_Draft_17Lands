"""
src/log_scanner.py

This module contains the ArenaScanner class used for parsing the Arena log
and managing the state of the current draft (packs, picks, event info).
"""

import os
import json
import re
import logging
from enum import Enum
from datetime import datetime

import src.constants as constants
from src.logger import create_logger
from src.set_metrics import SetMetrics
from src.dataset import Dataset
from src.ocr import OCR
from src.tier_list import TierList
from src.utils import (
    process_json,
    json_find,
    retrieve_local_set_list,
    capture_screen_base64str,
    detect_string,
    normalize_color_string,
    Result,
)

if not os.path.exists(constants.DRAFT_LOG_FOLDER):
    os.makedirs(constants.DRAFT_LOG_FOLDER)

LOG_TYPE_DRAFT = "draftLog"

logger = create_logger()


class Source(Enum):
    REFRESH = 1
    UPDATE = 2


class ArenaScanner:
    """Class that handles the processing of the information within Arena Player.log file"""

    def __init__(
        self,
        filename,
        set_list,
        sets_location: str = constants.SETS_FOLDER,
        step_through: bool = False,
        retrieve_unknown: bool = False,
    ):
        self.arena_file = filename
        self.set_list = set_list
        self.draft_log = logging.getLogger(LOG_TYPE_DRAFT)
        self.draft_log.setLevel(logging.INFO)
        self.sets_location = sets_location

        self.logging_enabled = False

        self.step_through = step_through
        self.set_data = Dataset(retrieve_unknown)
        self.tier_list = TierList()
        self.draft_type = constants.LIMITED_TYPE_UNKNOWN
        self.pick_offset = 0
        self.pack_offset = 0
        self.search_offset = 0
        self.draft_start_offset = 0
        self.draft_sets = []
        self.current_pick = 0
        self.current_pack = 0
        self.number_of_players = 8
        self.picked_cards = [[] for _ in range(self.number_of_players)]
        self.pack_cards = [[] for _ in range(self.number_of_players)]
        self.initial_pack = [[] for _ in range(self.number_of_players)]
        self.taken_cards = []
        self.sideboard = []
        self.previous_picked_pack = 0
        self.current_picked_pick = 0
        self.file_size = 0
        self.data_source = "None"
        self.event_string = ""
        self.draft_label = ""
        self.draft_history = []
        self.current_draft_id = ""

    def set_arena_file(self, filename):
        """Updates the log path and resets pointers for a clean scan."""
        if self.arena_file != filename:
            logger.info(f"Scanner path updated to: {filename}")
            self.arena_file = filename
            self.search_offset = 0
            self.draft_start_offset = 0
            self.file_size = 0
            self.clear_draft(True)

    def log_enable(self, enable):
        """Enable/disable the application draft log feature that records draft data in a log file within the Logs folder"""
        self.logging_enabled = enable
        self.log_suspend(not enable)

    def log_suspend(self, suspended):
        """Prevents the application from updating the draft log file"""
        if suspended:
            self.draft_log.setLevel(logging.CRITICAL)
        elif self.logging_enabled:
            self.draft_log.setLevel(logging.INFO)

    def __new_log(self, card_set, event, draft_id):
        """Create a new draft log file"""
        try:
            log_name = f"DraftLog_{card_set}_{event}_{draft_id}.log"
            log_path = os.path.join(constants.DRAFT_LOG_FOLDER, log_name)
            for handler in self.draft_log.handlers:
                if isinstance(handler, logging.FileHandler):
                    self.draft_log.removeHandler(handler)
            formatter = logging.Formatter(
                "%(asctime)s,%(message)s", datefmt="<%d%m%Y %H:%M:%S>"
            )
            new_handler = logging.FileHandler(log_path, delay=True)
            new_handler.setFormatter(formatter)
            self.draft_log.addHandler(new_handler)
            logger.info("Creating new draft log: %s", log_path)
        except Exception as error:
            logger.error(error)

    def clear_draft(self, full_clear):
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
        self.picked_cards = [[] for _ in range(self.number_of_players)]
        self.pack_cards = [[] for _ in range(self.number_of_players)]
        self.initial_pack = [[] for _ in range(self.number_of_players)]
        self.taken_cards = []
        self.sideboard = []
        self.current_pack = 0
        self.previous_picked_pack = 0
        self.current_picked_pick = 0
        self.data_source = "None"
        self.draft_label = ""
        self.draft_history = []
        self.current_draft_id = ""

    def draft_start_search(self):
        """Search for the string that represents the start of a draft"""
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
                    "New Arena Log Detected (%d), (%d)", self.file_size, arena_file_size
                )
            self.file_size = arena_file_size
            offset = self.search_offset
            with open(self.arena_file, "r", encoding="utf-8", errors="replace") as log:
                log.seek(offset)
                while True:
                    line = log.readline()
                    if not line:
                        break
                    offset = log.tell()
                    self.search_offset = offset
                    start_offset = detect_string(line, constants.DRAFT_START_STRINGS)

                    # Standard Event Join
                    if start_offset != -1:
                        entry_string = line[start_offset:]
                        event_data = process_json(entry_string)

                        # Correct Logic: Latch update to True, don't overwrite if False
                        is_new, et, did = self.__check_event(event_data)
                        if is_new:
                            update = True
                            event_type = et
                            draft_id = did
                            event_line = line
                            self.draft_start_offset = offset

                    # Deck Recovery (EventSetDeckV2)
                    elif "InternalEventName" in line and "CardPool" in line:
                        try:
                            json_start = line.find("{")
                            if json_start != -1:
                                event_data = process_json(line[json_start:])
                                internal_name = json_find(
                                    "InternalEventName", event_data
                                )
                                if internal_name:
                                    dummy_payload = {"EventName": internal_name}

                                    is_new, et, did = self.__check_event(dummy_payload)
                                    if is_new:
                                        update = True
                                        event_type = et
                                        draft_id = did
                                        event_line = line
                                        self.draft_start_offset = offset

                                        card_pool = json_find("CardPool", event_data)
                                        if card_pool:
                                            self.taken_cards = [
                                                str(c) for c in card_pool
                                            ]
                                            logger.info(
                                                f"Recovered {len(self.taken_cards)} cards from Deck Set log"
                                            )
                        except Exception as e:
                            logger.error(f"Error parsing Deck Recovery line: {e}")

            if update:
                self.__new_log(self.draft_sets[0], event_type, draft_id)
                self.draft_log.info(event_line)
                self.pick_offset = self.draft_start_offset
                self.pack_offset = self.draft_start_offset
                logger.info("New draft detected %s, %s", event_type, self.draft_sets)
        except Exception as error:
            logger.error(error)

        return update

    def __check_event(self, event_data):
        """Parse a draft start string and extract pertinent information"""
        update = False
        event_type = ""
        draft_id = ""
        try:
            draft_id = json_find("id", event_data)
            event_name = json_find("EventName", event_data)

            # If the event is the same as the current event, then don't reset the draft data
            if self.event_string == event_name:
                return update, event_type, draft_id

            logger.info("Event found %s", event_name)
            event_match, event_type, event_label, event_set, number_of_players = (
                self.__check_special_event(event_name)
            )
            if not event_match:
                event_match, event_type, event_label, event_set, number_of_players = (
                    self.__check_standard_event(event_name)
                )

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
        """"""
        event_match = False
        event_type = ""
        event_label = ""
        event_set = ""
        number_of_players = 8

        for event in self.set_list.special_events:
            if event.type in constants.LIMITED_TYPES_DICT and all(
                x in event_name for x in event.keywords
            ):
                event_type = event.type
                event_label = event.label[:12]
                event_set = [event.set_code]
                number_of_players = (
                    4
                    if constants.PICK_TWO_EVENT_STRING in event_name
                    else event.number_of_players
                )
                event_match = True
                break

        return event_match, event_type, event_label, event_set, number_of_players

    def __check_standard_event(self, event_name):
        """"""
        event_match = False
        event_type = ""
        event_label = ""
        event_set = []
        number_of_players = 8
        event_sections = event_name.split("_")

        events = [
            i for i in constants.LIMITED_TYPES_DICT for x in event_sections if i in x
        ]
        if not events and [
            i
            for i in constants.DRAFT_DETECTION_CATCH_ALL
            for x in event_sections
            if i in x
        ]:
            # Unknown draft events will be parsed as premier drafts
            events.append(constants.LIMITED_TYPE_STRING_DRAFT_PREMIER)

        if events:
            upper_sections = [sec.upper() for sec in event_sections]

            # 1. Try to find the set code in the known Set List
            # Sort by length descending to match more specific cubes (CUBE-POWERED) before generic (CUBE)
            for i in sorted(
                self.set_list.data.values(), key=lambda v: len(v.set_code), reverse=True
            ):
                if not i.set_code:
                    continue

                # FIX: Ensure "CUBE" is treated as a separate word for robust matching (e.g. POWEREDCUBE vs CUBE-POWERED)
                normalized_code = i.set_code.replace("-", " ").replace("CUBE", " CUBE ")
                code_parts = normalized_code.split()

                # A set matches if ALL of its parts are found as substrings in ANY of the separated sections
                if all(
                    any(part.upper() in sec for sec in upper_sections)
                    for part in code_parts
                ):
                    event_set = [i.set_code]
                    break

            # 2. Heuristic Fallback: If not found in metadata, try to extract a plausible Set Code
            # This handles new sets (like ECL) that haven't been added to set_list.json yet.
            if not event_set:
                for section in event_sections:
                    # Skip the event type part (e.g. PremierDraft) and Date parts
                    if any(ev in section for ev in events) or section.isdigit():
                        continue

                    # Assume 3-4 letter alphanumeric code is the set code
                    if 3 <= len(section) <= 4 and section.isalnum():
                        event_set = [section.upper()]
                        break

            event_set = ["UNKN"] if not event_set else event_set

            if events[0] == constants.LIMITED_TYPE_STRING_SEALED:
                event_type = (
                    constants.LIMITED_TYPE_STRING_TRAD_SEALED
                    if "Trad" in event_sections
                    else constants.LIMITED_TYPE_STRING_SEALED
                )
            else:
                event_type = events[0]
            event_label = event_type
            event_match = True
            number_of_players = (
                4 if constants.PICK_TWO_EVENT_STRING in event_name else 8
            )

        return event_match, event_type, event_label, event_set, number_of_players

    def draft_data_search(self, use_ocr, save_screenshot):
        """Collect draft data from the Player.log file based on the current active format"""
        update = False
        previous_pick = self.current_pick
        previous_pack = self.current_pack
        previous_picked = self.current_picked_pick

        # Route draft types to their appropriate parsers

        if self.draft_type == constants.LIMITED_TYPE_DRAFT_PREMIER_V1:
            if use_ocr:
                self.__get_ocr_pack(save_screenshot)
            self.__draft_pack_search_premier_p1p1()
            self.__draft_pack_search_premier_v1()
            self.__draft_picked_search_premier_v1()

        elif (
            self.draft_type == constants.LIMITED_TYPE_DRAFT_PREMIER_V2
            or self.draft_type == constants.LIMITED_TYPE_DRAFT_PICK_TWO
        ):
            # PickTwo uses V2 logic (EventPlayerDraftMakePick)
            if use_ocr:
                self.__get_ocr_pack(save_screenshot)
            self.__draft_pack_search_premier_p1p1()
            self.__draft_pack_search_premier_v2()
            self.__draft_picked_search_premier_v2()

        elif (
            self.draft_type == constants.LIMITED_TYPE_DRAFT_QUICK
            or self.draft_type == constants.LIMITED_TYPE_DRAFT_PICK_TWO_QUICK
        ):
            self.__draft_picked_search_quick()
            self.__draft_pack_search_quick()

        elif (
            self.draft_type == constants.LIMITED_TYPE_DRAFT_TRADITIONAL
            or self.draft_type == constants.LIMITED_TYPE_DRAFT_PICK_TWO_TRAD
        ):
            if use_ocr:
                self.__get_ocr_pack(save_screenshot)
            self.__draft_pack_search_traditional_p1p1()
            self.__draft_pack_search_traditional()
            self.__draft_picked_search_traditional()

        elif (self.draft_type == constants.LIMITED_TYPE_SEALED) or (
            self.draft_type == constants.LIMITED_TYPE_SEALED_TRADITIONAL
        ):
            update = self.__sealed_pack_search()

        if not update:
            if (
                (previous_pack != self.current_pack)
                or (previous_pick != self.current_pick)
                or (previous_picked != self.current_picked_pick)
            ):
                update = True

        return update

    def __get_ocr_pack(self, persist):
        try:
            if self.current_pack != 0 or self.current_pick != 0:
                return

            card_names = self.set_data.get_all_names()

            if not card_names:
                return

            screenshot = capture_screen_base64str(persist)
            received_names = OCR().get_pack(card_names, screenshot)

            pack_cards = self.set_data.get_ids_by_name(received_names)

            if not pack_cards:
                return

            self._check_and_wipe_stale_pool(1, 1)
            self.initial_pack[0] = pack_cards
            self.pack_cards[0] = pack_cards
            self.current_pack = 1
            self.current_pick = 1
            self._record_pack(1, 1, pack_cards)

        except Exception as error:
            logger.error(error)

    def __draft_pack_search_premier_p1p1(self):
        offset = self.pack_offset
        try:
            with open(self.arena_file, "r", encoding="utf-8", errors="replace") as log:
                log.seek(offset)
                while True:
                    line = log.readline()
                    if not line:
                        break
                    current_pos = log.tell()

                    start_json = detect_string(
                        line, [constants.DRAFT_P1P1_STRING_PREMIER]
                    )
                    if start_json != -1:
                        self.pack_offset = current_pos
                        self.draft_log.info(line)
                        draft_data = process_json(line[start_json:])

                        cards = json_find(
                            constants.DRAFT_P1P1_STRING_PREMIER, draft_data
                        )
                        if not cards:
                            continue

                        pack_cards = [str(c) for c in cards]
                        pack = json_find("PackNumber", draft_data)
                        pick = json_find("PickNumber", draft_data)

                        if pack == 1 and pick == 1:
                            self._check_and_wipe_stale_pool(pack, pick)
                            self.pack_cards[0] = pack_cards
                            self.initial_pack[0] = pack_cards
                            self.current_pack, self.current_pick = 1, 1
                            self._record_pack(1, 1, pack_cards)
        except Exception as e:
            logger.error(f"P1P1 Search Error: {e}")

    def __draft_pack_search_premier_v1(self):
        offset = self.pack_offset
        try:
            with open(self.arena_file, "r", encoding="utf-8", errors="replace") as log:
                log.seek(offset)
                while True:
                    line = log.readline()
                    if not line:
                        break
                    current_pos = log.tell()

                    if detect_string(line, [constants.DRAFT_PACK_STRING_PREMIER]) != -1:
                        self.pack_offset = current_pos
                        start_offset = line.find('{"draftId"')
                        self.draft_log.info(line)
                        entry_string = line[start_offset:]
                        draft_data = process_json(entry_string)

                        try:
                            cards = str(json_find("PackCards", draft_data)).split(",")
                            pack_cards = [str(c) for c in cards]

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
                            self._record_pack(pack, pick, pack_cards)

                            if self.step_through:
                                break
                        except Exception as e:
                            logger.error(f"V1 Pack Error: {e}")

        except Exception as e:
            logger.error(f"V1 Pack Search Error: {e}")

    def _check_and_wipe_stale_pool(self, pack, pick, draft_id=None):
        wipe_needed = False
        reason = ""

        # Condition 0: DraftId changed (Unique Draft Instance detected)
        if draft_id and self.current_draft_id and draft_id != self.current_draft_id:
            wipe_needed = True
            reason = f"New DraftId detected ({draft_id})"

        # Condition 1: Explicit P1P1
        elif pack == 1 and pick == 1:
            wipe_needed = True
            reason = "P1P1 detected"

        # Condition 2: Time Travel (Moving backwards in packs/picks)
        elif self.current_pack > 0:
            if (pack < self.current_pack) or (
                pack == self.current_pack and pick < self.current_pick
            ):
                wipe_needed = True
                reason = f"Draft rewind detected (P{pack}P{pick} vs P{self.current_pack}P{self.current_pick})"

        # Condition 3: Jumping from a Recovered Deck into early Pack 1
        elif self.current_pack == 0 and pack == 1:
            if len(self.taken_cards) >= 15:
                wipe_needed = True
                reason = "Transition from Deck Builder to new Draft"

        # Execute Wipe
        if wipe_needed and (len(self.taken_cards) > 0 or self.current_pack > 0):
            logger.info(f"{reason}. Wiping stale card pool.")
            self.taken_cards = []
            self.picked_cards = [[] for _ in range(self.number_of_players)]
            self.draft_history = []
            self.sideboard = []
            self.current_pack = 0
            self.current_pick = 0
            self.previous_picked_pack = 0

        # Sync ID
        if draft_id:
            self.current_draft_id = draft_id

    def __draft_picked_search_premier_v1(self):
        offset = self.pick_offset
        try:
            with open(self.arena_file, "r", encoding="utf-8", errors="replace") as log:
                log.seek(offset)
                while True:
                    line = log.readline()
                    if not line:
                        break
                    offset = log.tell()

                    if (
                        detect_string(line, [constants.DRAFT_PICK_STRING_PREMIER_OLD])
                        != -1
                    ):
                        self.pick_offset = offset
                        self.draft_log.info(line)
                        try:
                            string_offset = detect_string(
                                line, [constants.DRAFT_PICK_STRING_PREMIER_OLD]
                            )
                            draft_data = process_json(line[string_offset:])

                            pack = int(json_find("Pack", draft_data))
                            pick = int(json_find("Pick", draft_data))
                            cards = [str(json_find("GrpId", draft_data))]

                            pack_index = (pick - 1) % self.number_of_players

                            if self.previous_picked_pack != pack:
                                self.picked_cards = [
                                    [] for _ in range(self.number_of_players)
                                ]

                            self.picked_cards[pack_index].extend(cards)
                            self.taken_cards.extend(cards)
                            self.previous_picked_pack = pack
                            self.current_picked_pick = pick

                            if self.step_through:
                                break
                        except Exception as e:
                            logger.error(f"V1 Pick Error: {e}")

        except Exception as e:
            logger.error(f"V1 Pick Search Error: {e}")

    def __draft_pack_search_premier_v2(self):
        offset = self.pack_offset
        try:
            with open(self.arena_file, "r", encoding="utf-8", errors="replace") as log:
                log.seek(offset)
                while True:
                    line = log.readline()
                    if not line:
                        break
                    offset = log.tell()

                    # V2 Pack uses standard DRAFT_PACK_STRING_PREMIER like V1 but payload might be slightly different
                    if detect_string(line, [constants.DRAFT_PACK_STRING_PREMIER]) != -1:
                        self.pack_offset = offset
                        self.draft_log.info(line)
                        string_offset = detect_string(
                            line, [constants.DRAFT_PACK_STRING_PREMIER]
                        )

                        try:
                            # Use json.loads directly if possible, or process_json for nested
                            try:
                                draft_data = json.loads(line[string_offset:])
                            except:
                                draft_data = process_json(line[string_offset:])

                            # V2 usually has PackCards as a string "1,2,3" inside JSON
                            cards_raw = json_find("PackCards", draft_data)
                            if not cards_raw:
                                continue

                            pack_cards = str(cards_raw).split(",")
                            pack = json_find("SelfPack", draft_data)
                            pick = json_find("SelfPick", draft_data)
                            draft_id = json_find("draftId", draft_data) or json_find(
                                "DraftId", draft_data
                            )

                            pack_index = (pick - 1) % self.number_of_players

                            if self.current_pack != pack:
                                self.initial_pack = [[]] * self.number_of_players

                            if len(self.initial_pack[pack_index]) == 0:
                                self.initial_pack[pack_index] = pack_cards

                            self._check_and_wipe_stale_pool(pack, pick, draft_id)
                            self.pack_cards[pack_index] = pack_cards
                            self.current_pack = pack
                            self.current_pick = pick
                            self._record_pack(pack, pick, pack_cards)

                            if self.step_through:
                                break
                        except Exception as e:
                            logger.error(f"V2 Pack Error: {e}")

        except Exception as e:
            logger.error(f"V2 Pack Search Error: {e}")

    def __draft_picked_search_premier_v2(self):
        offset = self.pick_offset
        try:
            with open(self.arena_file, "r", encoding="utf-8", errors="replace") as log:
                log.seek(offset)
                while True:
                    line = log.readline()
                    if not line:
                        break
                    offset = log.tell()

                    # Use new pick string
                    if detect_string(line, [constants.DRAFT_PICK_STRING_PREMIER]) != -1:
                        self.pick_offset = offset
                        self.draft_log.info(line)
                        try:
                            string_offset = detect_string(
                                line, [constants.DRAFT_PICK_STRING_PREMIER]
                            )
                            draft_data = process_json(line[string_offset:])

                            # Handle V2 structure which might be nested differently
                            # Look for keys recursively
                            pack = int(
                                json_find("Pack", draft_data)
                                or json_find("packNumber", draft_data)
                                or 0
                            )
                            pick = int(
                                json_find("Pick", draft_data)
                                or json_find("pickNumber", draft_data)
                                or 0
                            )

                            cards = []
                            grp_ids = json_find("GrpIds", draft_data) or json_find(
                                "cardIds", draft_data
                            )
                            if grp_ids:
                                cards = [str(x) for x in grp_ids]
                            else:
                                grp_id = (
                                    json_find("GrpId", draft_data)
                                    or json_find("cardId", draft_data)
                                    or json_find("PickGrpId", draft_data)
                                )
                                if grp_id:
                                    cards = [str(grp_id)]

                            if not cards or not pack or not pick:
                                continue

                            pack_index = (pick - 1) % self.number_of_players

                            if self.previous_picked_pack != pack:
                                self.picked_cards = [
                                    [] for _ in range(self.number_of_players)
                                ]

                            self.picked_cards[pack_index].extend(cards)
                            self.taken_cards.extend(cards)
                            self.previous_picked_pack = pack
                            self.current_picked_pick = pick

                            if self.step_through:
                                break
                        except Exception as e:
                            logger.error(f"V2 Pick Error: {e}")

        except Exception as e:
            logger.error(f"V2 Pick Search Error: {e}")

    def __draft_pack_search_quick(self):
        offset = self.pack_offset
        try:
            with open(self.arena_file, "r", encoding="utf-8", errors="replace") as log:
                log.seek(offset)
                while True:
                    line = log.readline()
                    if not line:
                        break
                    offset = log.tell()

                    if detect_string(line, [constants.DRAFT_PACK_STRING_QUICK]) != -1:
                        self.pack_offset = offset
                        self.draft_log.info(line)
                        start_offset = line.find('{"CurrentModule"')
                        if start_offset == -1:
                            start_offset = detect_string(
                                line, [constants.DRAFT_PACK_STRING_QUICK]
                            )

                        entry_string = line[start_offset:]
                        draft_data = process_json(entry_string)
                        draft_status = json_find("DraftStatus", draft_data)

                        if draft_status == "PickNext":
                            try:
                                cards = json_find("DraftPack", draft_data)
                                pack_cards = [str(c) for c in cards]

                                pack = int(json_find("PackNumber", draft_data)) + 1
                                pick = int(json_find("PickNumber", draft_data)) + 1
                                pack_index = (pick - 1) % self.number_of_players

                                if self.current_pack != pack:
                                    self.initial_pack = [[]] * self.number_of_players

                                if len(self.initial_pack[pack_index]) == 0:
                                    self.initial_pack[pack_index] = pack_cards

                                self._check_and_wipe_stale_pool(pack, pick)
                                self.pack_cards[pack_index] = pack_cards
                                self.current_pack = pack
                                self.current_pick = pick
                                self._record_pack(pack, pick, pack_cards)

                                # Catch up taken cards if needed (Fix for QuickDraft test failure)
                                picked = json_find("PickedCards", draft_data)
                                if picked and len(picked) > len(self.taken_cards):
                                    # Sync taken_cards with the log's PickedCards list
                                    # The log's PickedCards is authoritative for the current state
                                    self.taken_cards = [str(c) for c in picked]
                                    # Also need to update picked_cards (seat based)
                                    # For quick draft, usually single seat (index 0) matters
                                    self.picked_cards[0] = self.taken_cards

                                if self.step_through:
                                    break
                            except Exception as e:
                                logger.error(f"Quick Pack Error: {e}")

        except Exception as e:
            logger.error(f"Quick Pack Search Error: {e}")

    def __draft_picked_search_quick(self):
        offset = self.pick_offset
        try:
            with open(self.arena_file, "r", encoding="utf-8", errors="replace") as log:
                log.seek(offset)
                while True:
                    line = log.readline()
                    if not line:
                        break
                    offset = log.tell()

                    if detect_string(line, [constants.DRAFT_PICK_STRING_QUICK]) != -1:
                        self.pick_offset = offset
                        self.draft_log.info(line)
                        try:
                            string_offset = detect_string(
                                line, [constants.DRAFT_PICK_STRING_QUICK]
                            )
                            draft_data = process_json(line[string_offset:])

                            pack = int(json_find("PackNumber", draft_data)) + 1
                            pick = int(json_find("PickNumber", draft_data)) + 1

                            cards = []
                            cids = json_find("CardIds", draft_data)
                            if cids:
                                cards = [str(x) for x in cids]
                            else:
                                cid = json_find("CardId", draft_data)
                                if cid:
                                    cards = [str(cid)]

                            pack_index = (pick - 1) % self.number_of_players

                            if self.previous_picked_pack != pack:
                                self.picked_cards = [
                                    [] for _ in range(self.number_of_players)
                                ]

                            self.picked_cards[pack_index].extend(cards)
                            self.taken_cards.extend(cards)
                            self.previous_picked_pack = pack
                            self.current_picked_pick = pick

                            if self.step_through:
                                break
                        except Exception as e:
                            logger.error(f"Quick Pick Error: {e}")

        except Exception as e:
            logger.error(f"Quick Pick Search Error: {e}")

    def __draft_pack_search_traditional_p1p1(self):
        offset = self.pack_offset
        try:
            with open(self.arena_file, "r", encoding="utf-8", errors="replace") as log:
                log.seek(offset)
                while True:
                    line = log.readline()
                    if not line:
                        break
                    offset = log.tell()

                    if detect_string(line, [constants.DRAFT_P1P1_STRING_PREMIER]) != -1:
                        self.pack_offset = offset
                        self.draft_log.info(line)
                        string_offset = detect_string(
                            line, [constants.DRAFT_P1P1_STRING_PREMIER]
                        )
                        draft_data = process_json(line[string_offset:])

                        try:
                            cards = json_find("CardsInPack", draft_data)
                            if not cards:
                                continue
                            pack_cards = [str(c) for c in cards]

                            pack = json_find("PackNumber", draft_data)
                            pick = json_find("PickNumber", draft_data)

                            if pack != 1 or pick != 1:
                                continue

                            pack_index = (pick - 1) % self.number_of_players
                            self._check_and_wipe_stale_pool(pack, pick)
                            self.pack_cards[pack_index] = pack_cards
                            self.initial_pack[pack_index] = pack_cards
                            self.current_pack, self.current_pick = pack, pick
                            self._record_pack(pack, pick, pack_cards)

                            if self.step_through:
                                break
                        except Exception as e:
                            logger.error(f"Trad P1P1 Error: {e}")

        except Exception as e:
            logger.error(f"Trad P1P1 Search Error: {e}")

    def __draft_pack_search_traditional(self):
        # Traditional draft pack logic is generally same as Premier V2 logic in new logs
        # But for safety, we implement it similarly to V2
        offset = self.pack_offset
        try:
            with open(self.arena_file, "r", encoding="utf-8", errors="replace") as log:
                log.seek(offset)
                while True:
                    line = log.readline()
                    if not line:
                        break
                    offset = log.tell()

                    if detect_string(line, [constants.DRAFT_PACK_STRING_PREMIER]) != -1:
                        self.pack_offset = offset
                        self.draft_log.info(line)
                        string_offset = detect_string(
                            line, [constants.DRAFT_PACK_STRING_PREMIER]
                        )

                        try:
                            draft_data = process_json(line[string_offset:])

                            cards_raw = json_find("PackCards", draft_data)
                            if not cards_raw:
                                continue
                            pack_cards = str(cards_raw).split(",")

                            pack = json_find("SelfPack", draft_data)
                            pick = json_find("SelfPick", draft_data)
                            draft_id = json_find("draftId", draft_data) or json_find(
                                "DraftId", draft_data
                            )

                            pack_index = (pick - 1) % self.number_of_players

                            if self.current_pack != pack:
                                self.initial_pack = [[]] * self.number_of_players

                            if len(self.initial_pack[pack_index]) == 0:
                                self.initial_pack[pack_index] = pack_cards

                            self._check_and_wipe_stale_pool(pack, pick, draft_id)
                            self.pack_cards[pack_index] = pack_cards
                            self.current_pack = pack
                            self.current_pick = pick
                            self._record_pack(pack, pick, pack_cards)

                            if self.step_through:
                                break
                        except Exception as e:
                            logger.error(f"Trad Pack Error: {e}")

        except Exception as e:
            logger.error(f"Trad Pack Search Error: {e}")

    def __draft_picked_search_traditional(self):
        offset = self.pick_offset
        try:
            with open(self.arena_file, "r", encoding="utf-8", errors="replace") as log:
                log.seek(offset)
                while True:
                    line = log.readline()
                    if not line:
                        break
                    offset = log.tell()

                    if detect_string(line, [constants.DRAFT_PICK_STRING_PREMIER]) != -1:
                        self.pick_offset = offset
                        self.draft_log.info(line)
                        try:
                            string_offset = detect_string(
                                line, [constants.DRAFT_PICK_STRING_PREMIER]
                            )
                            draft_data = process_json(line[string_offset:])

                            pack = int(
                                json_find("Pack", draft_data)
                                or json_find("packNumber", draft_data)
                                or 0
                            )
                            pick = int(
                                json_find("Pick", draft_data)
                                or json_find("pickNumber", draft_data)
                                or 0
                            )

                            cards = []
                            grp_ids = json_find("GrpIds", draft_data)
                            if grp_ids:
                                cards = [str(x) for x in grp_ids]
                            else:
                                grp_id = json_find("GrpId", draft_data) or json_find(
                                    "PickGrpId", draft_data
                                )
                                if grp_id:
                                    cards = [str(grp_id)]

                            if not cards or not pack or not pick:
                                continue

                            pack_index = (pick - 1) % self.number_of_players

                            if self.previous_picked_pack != pack:
                                self.picked_cards = [
                                    [] for _ in range(self.number_of_players)
                                ]

                            self.picked_cards[pack_index].extend(cards)
                            self.taken_cards.extend(cards)
                            self.previous_picked_pack = pack
                            self.current_picked_pick = pick

                            if self.step_through:
                                break
                        except Exception as e:
                            logger.error(f"Trad Pick Error: {e}")
        except Exception as e:
            logger.error(f"Trad Pick Search Error: {e}")

    def __sealed_pack_search(self):
        offset = self.pack_offset
        draft_string = f'"InternalEventName":"{self.event_string}"'
        update = False
        try:
            with open(self.arena_file, "r", encoding="utf-8", errors="replace") as log:
                log.seek(offset)
                while True:
                    line = log.readline()
                    if not line:
                        break
                    offset = log.tell()

                    if (draft_string in line) and ("CardPool" in line):
                        try:
                            self.pack_offset = offset
                            self.draft_log.info(line)

                            if "Courses" in line:
                                start_offset = line.find('{"Courses"')
                                course_data = json.loads(line[start_offset:])
                                for course in course_data["Courses"]:
                                    if course["InternalEventName"] == self.event_string:
                                        card_pool = [str(x) for x in course["CardPool"]]
                                        if self.__sealed_update(card_pool):
                                            update = True
                            elif "Course" in line:
                                start_offset = line.find('{"Course"')
                                if start_offset != -1:
                                    # Use json.loads directly if possible to handle strict JSON
                                    try:
                                        course_data = json.loads(line[start_offset:])
                                    except:
                                        course_data = process_json(line[start_offset:])

                                    # Ensure course_data is a dictionary
                                    if isinstance(course_data, dict):
                                        if (
                                            course_data["Course"]["InternalEventName"]
                                            == self.event_string
                                        ):
                                            card_pool = [
                                                str(x)
                                                for x in course_data["Course"][
                                                    "CardPool"
                                                ]
                                            ]
                                            if self.__sealed_update(card_pool):
                                                update = True
                        except Exception as error:
                            logger.error(f"Sealed Search Error: {error}")

        except Exception as error:
            logger.error(f"Sealed File Error: {error}")
        return update

    def __sealed_update(self, cards):
        updated = False
        if not self.taken_cards:
            self.taken_cards.extend(cards)
            updated = True
        elif sorted(self.taken_cards) != sorted(cards):
            self.taken_cards = cards
            updated = True
        return updated

    def retrieve_data_sources(self):
        """Return a list of set files that can be used with the current active draft"""
        data_sources = {}
        try:
            file_list, error_list = retrieve_local_set_list()
            for error_string in error_list:
                logger.error(error_string)

            if self.draft_type != constants.LIMITED_TYPE_UNKNOWN:
                draft_list = list(constants.LIMITED_TYPES_DICT.keys())
                # Reverse mapping search
                found_types = [
                    k
                    for k, v in constants.LIMITED_TYPES_DICT.items()
                    if v == self.draft_type
                ]

                # Heuristic sort: prefer matching draft types
                if file_list:
                    file_list.sort(
                        key=lambda x: (
                            0 if x[1] in found_types else 1,
                            datetime.strptime(x[4], "%Y-%m-%d"),
                        ),
                        reverse=True,
                    )
                    file_list.sort(
                        key=lambda x: x[7], reverse=True
                    )  # Sort by collection date

            for file in file_list:
                set_code = file[0]
                event_type = file[1]
                user_group = file[2]
                location = file[6]
                if re.search(r"^[Yy]\d{2}", set_code):
                    type_string = f"[{set_code[0:6]}] {event_type} ({user_group})"
                else:
                    type_string = f"[{set_code}] {event_type} ({user_group})"
                data_sources[type_string] = location

        except Exception as error:
            logger.error(error)

        if not data_sources:
            data_sources = constants.DATA_SOURCES_NONE

        return data_sources

    def retrieve_set_data(self, file):
        result = Result.ERROR_MISSING_FILE
        self.set_data.clear()
        try:
            result = self.set_data.open_file(file)
        except Exception as error:
            logger.error(error)
        return result

    def retrieve_set_metrics(self):
        return SetMetrics(self.set_data)

    def retrieve_tier_data(self):
        event_set, _ = self.retrieve_current_limited_event()
        data, _ = self.tier_list.retrieve_data(event_set)
        return data

    def retrieve_color_win_rate(self, label_type):
        deck_colors = {}
        try:
            ratings = self.set_data.get_color_ratings() if self.set_data else {}

            for filter_key in constants.DECK_FILTERS:
                std_key = normalize_color_string(filter_key)
                display_label = std_key

                if (label_type == constants.DECK_FILTER_FORMAT_NAMES) and (
                    std_key in constants.COLOR_NAMES_DICT
                ):
                    display_label = constants.COLOR_NAMES_DICT[std_key]
                elif label_type == constants.DECK_FILTER_FORMAT_COLORS:
                    display_label = std_key

                # Always include Auto and All Decks
                if filter_key in [
                    constants.FILTER_OPTION_AUTO,
                    constants.FILTER_OPTION_ALL_DECKS,
                ]:
                    if std_key in ratings:
                        display_label = f"{display_label} ({ratings[std_key]}%)"
                    deck_colors[filter_key] = display_label
                # Only include specific color pairs if they exist in the downloaded ratings
                elif std_key in ratings:
                    winrate = ratings[std_key]
                    display_label = f"{display_label} ({winrate}%)"
                    deck_colors[filter_key] = display_label

        except Exception as error:
            logger.error(error)

        return {v: k for k, v in deck_colors.items()}

    def retrieve_current_picked_cards(self):
        picked_cards = []
        pack_index = max(self.current_pick - 1, 0) % self.number_of_players
        if pack_index < len(self.picked_cards):
            picked_cards = self.set_data.get_data_by_id(self.picked_cards[pack_index])
        return picked_cards

    def retrieve_current_missing_cards(self):
        missing_cards = []
        try:
            pack_index = max(self.current_pick - 1, 0) % self.number_of_players
            if pack_index < len(self.pack_cards):
                current_pack_cards = self.pack_cards[pack_index]
            if pack_index < len(self.initial_pack):
                initial_pack_cards = self.initial_pack[pack_index]
            card_list = [x for x in initial_pack_cards if x not in current_pack_cards]
            missing_cards = self.set_data.get_data_by_id(card_list)
        except Exception as error:
            logger.error(error)
        return missing_cards

    def retrieve_current_pack_cards(self):
        pack_cards = []
        pack_index = max(self.current_pick - 1, 0) % self.number_of_players
        if pack_index < len(self.pack_cards):
            pack_cards = self.set_data.get_data_by_id(self.pack_cards[pack_index])
        return pack_cards

    def retrieve_taken_cards(self):
        taken_cards = self.set_data.get_data_by_id(self.taken_cards)
        return taken_cards

    def retrieve_current_pack_and_pick(self):
        return self.current_pack, self.current_pick

    def retrieve_current_limited_event(self):
        event_set = ""
        event_type = ""
        try:
            event_set = self.draft_sets[0] if self.draft_sets else ""
            event_type = self.draft_label
        except Exception as error:
            logger.error(error)
        return event_set, event_type

    def _record_pack(self, pack, pick, card_ids):
        if not self.draft_history or (
            self.draft_history[-1]["Pack"] != pack
            or self.draft_history[-1]["Pick"] != pick
        ):
            self.draft_history.append({"Pack": pack, "Pick": pick, "Cards": card_ids})

    def retrieve_draft_history(self):
        return self.draft_history

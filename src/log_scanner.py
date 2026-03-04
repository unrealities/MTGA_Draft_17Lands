"""
src/log_scanner.py

This module contains the ArenaScanner class used for parsing the Arena log
and managing the state of the current draft (packs, picks, event info).
"""

import os
import json
import re
import logging
import threading
import time
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

        # CENTRAL DATA LOCK: Co-ordinates UI and Background Threading
        self.lock = threading.RLock()

        self.logging_enabled = False
        self.step_through = step_through
        self.set_data = Dataset(retrieve_unknown)
        self.tier_list = TierList()
        self.draft_type = constants.LIMITED_TYPE_UNKNOWN

        # File Pointers
        self.pick_offset = 0
        self.pack_offset = 0
        self.p1p1_offset = 0
        self.search_offset = 0
        self.draft_start_offset = 0
        self.file_size = 0

        # State Trackers
        self.draft_sets = []
        self.current_pick = 0
        self.current_pack = 0
        self.number_of_players = 8

        self.picked_cards = [[] for _ in range(self.number_of_players)]
        self.pack_cards = [[] for _ in range(self.number_of_players)]
        self.initial_pack = [[] for _ in range(self.number_of_players)]
        self.taken_cards = []
        self.sideboard = []

        self.previous_scanned_pack = 0
        self.previous_picked_pack = 0
        self.current_picked_pick = 0

        self.data_source = "None"
        self.event_string = ""
        self.draft_label = ""
        self.draft_history = []
        self.current_draft_id = ""

    def set_arena_file(self, filename):
        """Updates the log path and resets pointers for a clean scan."""
        with self.lock:
            if self.arena_file != filename:
                logger.info(f"Scanner path updated to: {filename}")
                self.arena_file = filename
                self.search_offset = 0
                self.draft_start_offset = 0
                self.file_size = 0
                self.clear_draft(True)

    def log_enable(self, enable):
        """Enable/disable the application draft log feature"""
        with self.lock:
            self.logging_enabled = enable
            self.log_suspend(not enable)

    def log_suspend(self, suspended):
        """Prevents the application from updating the draft log file"""
        with self.lock:
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
        with self.lock:
            if full_clear:
                self.search_offset = 0
                self.draft_start_offset = 0
                self.file_size = 0
            self.set_data.clear()
            self.draft_type = constants.LIMITED_TYPE_UNKNOWN
            self.pick_offset = 0
            self.pack_offset = 0
            self.p1p1_offset = 0
            self.draft_sets = None
            self.current_pick = 0
            self.current_pack = 0
            self.previous_scanned_pack = 0
            self.previous_picked_pack = 0
            self.current_picked_pick = 0
            self.number_of_players = 8
            self.picked_cards = [[] for _ in range(self.number_of_players)]
            self.pack_cards = [[] for _ in range(self.number_of_players)]
            self.initial_pack = [[] for _ in range(self.number_of_players)]
            self.taken_cards = []
            self.sideboard = []
            self.data_source = "None"
            self.draft_label = ""
            self.draft_history = []
            self.current_draft_id = ""
            self.event_string = ""

    def draft_start_search(self):
        """Search for the string that represents the start of a draft"""
        with self.lock:
            update = False
            event_type = ""
            event_line = ""
            draft_id = ""

            try:
                arena_file_size = os.path.getsize(self.arena_file)
                if self.file_size > arena_file_size:
                    self.clear_draft(True)
                    logger.info(
                        "New Arena Log Detected (%d), (%d)",
                        self.file_size,
                        arena_file_size,
                    )
                self.file_size = arena_file_size

                offset = self.search_offset
                with open(
                    self.arena_file, "r", encoding="utf-8", errors="replace"
                ) as log:
                    log.seek(offset)
                    while True:
                        line = log.readline()
                        if not line:
                            break
                        offset = log.tell()
                        self.search_offset = offset

                        start_offset = detect_string(
                            line, constants.DRAFT_START_STRINGS
                        )

                        if start_offset != -1:
                            entry_string = line[start_offset:]
                            event_data = process_json(entry_string)
                            is_new, et, did = self.__check_event(event_data)
                            if is_new:
                                update = True
                                event_type = et
                                draft_id = did
                                event_line = line
                                self.draft_start_offset = offset

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
                                        is_new, et, did = self.__check_event(
                                            dummy_payload
                                        )
                                        if is_new:
                                            update = True
                                            event_type = et
                                            draft_id = did
                                            event_line = line
                                            self.draft_start_offset = offset
                                            card_pool = json_find(
                                                "CardPool", event_data
                                            )
                                            if card_pool:
                                                self.taken_cards = [
                                                    str(c) for c in card_pool
                                                ]
                            except Exception as e:
                                logger.error(f"Error parsing Deck Recovery line: {e}")

                if update:
                    self.__new_log(self.draft_sets[0], event_type, draft_id)
                    self.draft_log.info(event_line.strip())
                    self.pick_offset = self.draft_start_offset
                    self.pack_offset = self.draft_start_offset
                    self.p1p1_offset = self.draft_start_offset
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
        for event in self.set_list.special_events:
            if event.type in constants.LIMITED_TYPES_DICT and all(
                x in event_name for x in event.keywords
            ):
                number_of_players = (
                    4
                    if constants.PICK_TWO_EVENT_STRING in event_name
                    else event.number_of_players
                )
                return (
                    True,
                    event.type,
                    event.label[:12],
                    [event.set_code],
                    number_of_players,
                )
        return False, "", "", "", 8

    def __check_standard_event(self, event_name):
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
            events.append(constants.LIMITED_TYPE_STRING_DRAFT_PREMIER)

        if events:
            upper_sections = [sec.upper() for sec in event_sections]
            for i in sorted(
                self.set_list.data.values(), key=lambda v: len(v.set_code), reverse=True
            ):
                if not i.set_code:
                    continue
                normalized_code = i.set_code.replace("-", " ").replace("CUBE", " CUBE ")
                code_parts = normalized_code.split()
                if all(
                    any(part.upper() in sec for sec in upper_sections)
                    for part in code_parts
                ):
                    event_set = [i.set_code]
                    break

            if not event_set:
                for section in event_sections:
                    if any(ev in section for ev in events) or section.isdigit():
                        continue
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

    # =========================================================================
    # CORE MODULAR LOGIC ENGINES
    # =========================================================================

    def _scan_log_for_events(self, offset_attr: str, search_strings: list):
        """A robust generator that handles all file IO and yielding of JSON payloads."""
        offset = getattr(self, offset_attr, 0)
        try:
            with open(self.arena_file, "r", encoding="utf-8", errors="replace") as log:
                log.seek(offset)
                while True:
                    line = log.readline()
                    if not line:
                        break

                    current_pos = log.tell()
                    setattr(self, offset_attr, current_pos)

                    start_idx = detect_string(line, search_strings)
                    if start_idx != -1:
                        self.draft_log.info(line.strip())
                        yield line[start_idx:]
        except Exception as e:
            logger.error(f"Error scanning {search_strings}: {e}")

    def _process_pack_data(
        self,
        pack: int,
        pick: int,
        pack_cards: list,
        draft_id: str = None,
        is_p1p1_fallback: bool = False,
    ):
        """Universal handler for processing pack permutations across all Draft formats."""
        if not pack or not pick or not pack_cards:
            return

        # 1. Protect against old time-travel data
        if pack < self.current_pack or (
            pack == self.current_pack and pick < self.current_pick
        ):
            return

        pack_index = (pick - 1) % self.number_of_players

        # 2. Handle Pack Transitions securely (Prevents freezing on previous packs)
        if self.previous_scanned_pack != pack:
            self.initial_pack = [[] for _ in range(self.number_of_players)]
            self.pack_cards = [[] for _ in range(self.number_of_players)]
            self.previous_scanned_pack = pack

        # 3. P1P1 Telemetry Fallback Guard (Prevents overwriting good Draft.Notify data)
        if is_p1p1_fallback:
            if not ((pack == 1 and pick == 1) or len(self.pack_cards[pack_index]) == 0):
                return

        # 4. Wipe Check (New Draft Identifiers)
        self._check_and_wipe_stale_pool(pack, pick, draft_id)

        # 5. Commit Data safely
        if len(self.initial_pack[pack_index]) == 0:
            self.initial_pack[pack_index] = pack_cards

        self.pack_cards[pack_index] = pack_cards

        # 6. Update High Watermark
        if pack > self.current_pack or (
            pack == self.current_pack and pick >= self.current_pick
        ):
            self.current_pack, self.current_pick = pack, pick

        # 7. Record History
        self._record_pack(pack, pick, pack_cards)

    def _process_pick_data(
        self, pack: int, pick: int, cards: list, draft_id: str = None
    ):
        """Universal handler for processing human and bot picks."""
        if not cards or not pack or not pick:
            return

        self._check_and_wipe_stale_pool(pack, pick, draft_id)

        pack_index = (pick - 1) % self.number_of_players

        if self.previous_picked_pack != pack:
            self.picked_cards = [[] for _ in range(self.number_of_players)]

        self.picked_cards[pack_index].extend(cards)
        self.taken_cards.extend(cards)

        self.previous_picked_pack = pack
        self.current_picked_pick = pick

        if pack > self.current_pack or (
            pack == self.current_pack and pick >= self.current_pick
        ):
            self.current_pack, self.current_pick = pack, pick

    def _check_and_wipe_stale_pool(self, pack, pick, draft_id=None):
        wipe = False

        # Trust the ID if present
        if draft_id and self.current_draft_id and draft_id != self.current_draft_id:
            wipe = True
        # Fallback for old formats
        elif pack == 1 and pick == 1:
            if self.current_pack > 1 or self.current_pick > 1:
                wipe = True
            elif len(self.taken_cards) > 0:
                if (
                    draft_id
                    and self.current_draft_id
                    and draft_id == self.current_draft_id
                ):
                    wipe = False
                else:
                    wipe = True

        if wipe:
            logger.info("New Draft Start detected. Wiping stale card pool.")
            self.taken_cards = []
            self.picked_cards = [[] for _ in range(self.number_of_players)]
            self.draft_history = []
            self.sideboard = []
            self.current_pack = 0
            self.current_pick = 0
            self.previous_picked_pack = 0
            self.previous_scanned_pack = 0
            self.initial_pack = [[] for _ in range(self.number_of_players)]
            self.pack_cards = [[] for _ in range(self.number_of_players)]

        if draft_id and draft_id != self.current_draft_id:
            self.current_draft_id = draft_id

    # =========================================================================
    # EVENT DISPATCHER
    # =========================================================================

    def draft_data_search(
        self, use_ocr=False, save_screenshot=False, status_callback=None
    ):
        update = False
        if use_ocr:
            if self.run_ocr_workflow(save_screenshot, status_callback):
                update = True

        changes = self.__perform_search_logic()

        with self.lock:
            if self.draft_type == constants.LIMITED_TYPE_UNKNOWN:
                self.draft_start_search()
            if changes:
                update = True

        return update

    def __perform_search_logic(self):
        """Dispatches log scanning safely lock-free."""
        with self.lock:
            pk, pi = self.current_pack, self.current_pick
            pp = self.current_picked_pick

        explicit_update = False

        if self.draft_type == constants.LIMITED_TYPE_DRAFT_PREMIER_V1:
            self._search_pick_v1()
            self._search_pack_p1p1()
            self._search_pack_notify()
        elif self.draft_type in [
            constants.LIMITED_TYPE_DRAFT_PREMIER_V2,
            constants.LIMITED_TYPE_DRAFT_PICK_TWO,
            constants.LIMITED_TYPE_DRAFT_TRADITIONAL,
            constants.LIMITED_TYPE_DRAFT_PICK_TWO_TRAD,
        ]:
            self._search_pick_human()
            self._search_pack_p1p1()
            self._search_pack_notify()
        elif self.draft_type in [
            constants.LIMITED_TYPE_DRAFT_QUICK,
            constants.LIMITED_TYPE_DRAFT_PICK_TWO_QUICK,
        ]:
            self._search_pick_bot()
            self._search_pack_bot()
        elif self.draft_type in [
            constants.LIMITED_TYPE_SEALED,
            constants.LIMITED_TYPE_SEALED_TRADITIONAL,
        ]:
            explicit_update = self._search_sealed_pool()

        with self.lock:
            return (
                (pk != self.current_pack)
                or (pi != self.current_pick)
                or (pp != self.current_picked_pick)
                or explicit_update
            )

    # =========================================================================
    # MODULAR PARSERS
    # =========================================================================

    def _search_pack_p1p1(self):
        for payload in self._scan_log_for_events(
            "p1p1_offset", [constants.DRAFT_P1P1_STRING_PREMIER]
        ):
            try:
                draft_data = process_json(payload)
                cards = json_find(constants.DRAFT_P1P1_STRING_PREMIER, draft_data)
                if not cards:
                    continue
                self._process_pack_data(
                    pack=json_find("PackNumber", draft_data),
                    pick=json_find("PickNumber", draft_data),
                    pack_cards=[str(c) for c in cards],
                    draft_id=json_find("DraftId", draft_data)
                    or json_find("draftId", draft_data)
                    or "",
                    is_p1p1_fallback=True,
                )
            except Exception as e:
                logger.error(f"P1P1 Error: {e}")

    def _search_pack_notify(self):
        for payload in self._scan_log_for_events(
            "pack_offset", [constants.DRAFT_PACK_STRING_PREMIER]
        ):
            try:
                try:
                    draft_data = json.loads(payload)
                except:
                    draft_data = process_json(payload)

                cards_raw = json_find("PackCards", draft_data)
                if not cards_raw:
                    continue
                self._process_pack_data(
                    pack=json_find("SelfPack", draft_data),
                    pick=json_find("SelfPick", draft_data),
                    pack_cards=str(cards_raw).split(","),
                    draft_id=json_find("DraftId", draft_data)
                    or json_find("draftId", draft_data)
                    or "",
                )
                if self.step_through:
                    break
            except Exception as e:
                logger.error(f"Pack Notify Error: {e}")

    def _search_pick_human(self):
        for payload in self._scan_log_for_events(
            "pick_offset", [constants.DRAFT_PICK_STRING_PREMIER]
        ):
            try:
                draft_data = process_json(payload)
                cards = []

                grp_ids = json_find("GrpIds", draft_data) or json_find(
                    "cardIds", draft_data
                )
                if "GrpIds" in draft_data and isinstance(draft_data["GrpIds"], list):
                    cards = [str(x) for x in draft_data["GrpIds"]]
                elif grp_ids:
                    cards = [str(x) for x in grp_ids]
                else:
                    grp_id = (
                        json_find("GrpId", draft_data)
                        or json_find("cardId", draft_data)
                        or json_find("PickGrpId", draft_data)
                    )
                    if grp_id:
                        cards = [str(grp_id)]

                self._process_pick_data(
                    pack=int(
                        json_find("Pack", draft_data)
                        or json_find("packNumber", draft_data)
                        or 0
                    ),
                    pick=int(
                        json_find("Pick", draft_data)
                        or json_find("pickNumber", draft_data)
                        or 0
                    ),
                    cards=cards,
                    draft_id=json_find("DraftId", draft_data)
                    or json_find("draftId", draft_data)
                    or "",
                )
                if self.step_through:
                    break
            except Exception as e:
                logger.error(f"Pick Human Error: {e}")

    def _search_pick_v1(self):
        for payload in self._scan_log_for_events(
            "pick_offset", [constants.DRAFT_PICK_STRING_PREMIER_OLD]
        ):
            try:
                draft_data = process_json(payload)
                self._process_pick_data(
                    pack=int(json_find("Pack", draft_data) or 0),
                    pick=int(json_find("Pick", draft_data) or 0),
                    cards=[str(json_find("GrpId", draft_data))],
                    draft_id=json_find("DraftId", draft_data)
                    or json_find("draftId", draft_data)
                    or "",
                )
                if self.step_through:
                    break
            except Exception as e:
                logger.error(f"Pick V1 Error: {e}")

    def _search_pack_bot(self):
        for payload in self._scan_log_for_events(
            "pack_offset", [constants.DRAFT_PACK_STRING_QUICK]
        ):
            try:
                draft_data = process_json(payload)
                if json_find("DraftStatus", draft_data) == "PickNext":
                    cards = json_find("DraftPack", draft_data)
                    if not cards:
                        continue
                    pack = int(json_find("PackNumber", draft_data) or 0) + 1
                    pick = int(json_find("PickNumber", draft_data) or 0) + 1

                    self._process_pack_data(pack, pick, [str(c) for c in cards])

                    # Quick draft explicit taken cards sync
                    picked = json_find("PickedCards", draft_data)
                    if picked and len(picked) > len(self.taken_cards):
                        self.taken_cards = [str(c) for c in picked]
                        self.picked_cards[0] = self.taken_cards

                    if self.step_through:
                        break
            except Exception as e:
                logger.error(f"Pack Bot Error: {e}")

    def _search_pick_bot(self):
        for payload in self._scan_log_for_events(
            "pick_offset", [constants.DRAFT_PICK_STRING_QUICK]
        ):
            try:
                draft_data = process_json(payload)
                cards = []
                cids = json_find("CardIds", draft_data)
                if cids:
                    cards = [str(x) for x in cids]
                else:
                    cid = json_find("CardId", draft_data)
                    if cid:
                        cards = [str(cid)]

                self._process_pick_data(
                    pack=int(json_find("PackNumber", draft_data) or 0) + 1,
                    pick=int(json_find("PickNumber", draft_data) or 0) + 1,
                    cards=cards,
                )
                if self.step_through:
                    break
            except Exception as e:
                logger.error(f"Pick Bot Error: {e}")

    def _search_sealed_pool(self):
        update = False
        for payload in self._scan_log_for_events("pack_offset", ['"CardPool":[']):
            try:
                data = process_json(payload)
                pool = []
                course = data.get("Course", data.get("Courses", {}))

                if isinstance(course, list):
                    for c in course:
                        if (
                            not self.event_string
                            or c.get("InternalEventName") == self.event_string
                        ):
                            pool.extend(c.get("CardPool", []))
                elif isinstance(course, dict):
                    if (
                        not self.event_string
                        or course.get("InternalEventName") == self.event_string
                    ):
                        pool.extend(course.get("CardPool", []))

                if pool:
                    pool_strs = [str(x) for x in pool]
                    if not self.taken_cards or sorted(self.taken_cards) != sorted(
                        pool_strs
                    ):
                        self.taken_cards = pool_strs
                        update = True
            except Exception as e:
                logger.error(f"Sealed Search Error: {e}")
        return update

    # =========================================================================
    # DATA RETRIEVAL
    # =========================================================================

    def run_ocr_workflow(self, persist, status_callback=None):
        with self.lock:
            if (
                self.current_pack == 1
                and self.current_pick == 1
                and len(self.pack_cards[0]) > 0
            ):
                if status_callback:
                    status_callback("Already Scanned")
                return False
            if self.current_pack > 1 or self.current_pick > 1:
                return False
            card_names = self.set_data.get_all_names()
            if not card_names:
                return False

        try:
            if status_callback:
                status_callback("Capturing Screen...")
            screenshot = capture_screen_base64str(persist)
            if status_callback:
                status_callback("Calling Cloud...")
            received_names = OCR().get_pack(card_names, screenshot)
            if status_callback:
                status_callback("Processing Data...")

            with self.lock:
                pack_cards = self.set_data.get_ids_by_name(received_names)
                if not pack_cards:
                    if status_callback:
                        status_callback("No Cards Found")
                    time.sleep(1.5)
                    return False

                self._check_and_wipe_stale_pool(1, 1)
                self.initial_pack[0] = pack_cards
                self.pack_cards[0] = pack_cards
                self.current_pack, self.current_pick = 1, 1
                self._record_pack(1, 1, pack_cards)

                if status_callback:
                    status_callback("Success!")
                time.sleep(0.5)
                return True
        except Exception as error:
            logger.error(f"OCR Error: {error}")
            if status_callback:
                status_callback("OCR Failed")
            time.sleep(1.5)
            return False

    def retrieve_data_sources(self):
        data_sources = {}
        try:
            file_list, error_list = retrieve_local_set_list()
            if self.draft_type != constants.LIMITED_TYPE_UNKNOWN:
                found_types = [
                    k
                    for k, v in constants.LIMITED_TYPES_DICT.items()
                    if v == self.draft_type
                ]
                if file_list:
                    file_list.sort(
                        key=lambda x: (
                            0 if x[1] in found_types else 1,
                            datetime.strptime(x[4], "%Y-%m-%d"),
                        ),
                        reverse=True,
                    )
                    file_list.sort(key=lambda x: x[7], reverse=True)
            for file in file_list:
                set_code, event_type, user_group, location = (
                    file[0],
                    file[1],
                    file[2],
                    file[6],
                )
                prefix = (
                    f"[{set_code[0:6]}]"
                    if re.search(r"^[Yy]\d{2}", set_code)
                    else f"[{set_code}]"
                )
                data_sources[f"{prefix} {event_type} ({user_group})"] = location
        except Exception as error:
            logger.error(error)
        return data_sources if data_sources else constants.DATA_SOURCES_NONE

    def retrieve_set_data(self, file):
        with self.lock:
            self.set_data.clear()
            result = self.set_data.open_file(file)
            self._metrics_cache = SetMetrics(self.set_data)
            return result

    def retrieve_set_metrics(self):
        with self.lock:
            if not hasattr(self, "_metrics_cache") or self._metrics_cache is None:
                self._metrics_cache = SetMetrics(self.set_data)
            return self._metrics_cache

    def retrieve_tier_data(self):
        with self.lock:
            event_set, _ = self.retrieve_current_limited_event()
            data, _ = self.tier_list.retrieve_data(event_set)
            return data

    def retrieve_color_win_rate(self, label_type):
        with self.lock:
            deck_colors = {}
            try:
                ratings = self.set_data.get_color_ratings()
                for filter_key in constants.DECK_FILTERS:
                    std_key = normalize_color_string(filter_key)
                    display_label = std_key
                    if (label_type == constants.DECK_FILTER_FORMAT_NAMES) and (
                        std_key in constants.COLOR_NAMES_DICT
                    ):
                        display_label = constants.COLOR_NAMES_DICT[std_key]
                    if filter_key in [
                        constants.FILTER_OPTION_AUTO,
                        constants.FILTER_OPTION_ALL_DECKS,
                    ]:
                        if std_key in ratings:
                            display_label = f"{display_label} ({ratings[std_key]}%)"
                        deck_colors[filter_key] = display_label
                    elif std_key in ratings:
                        deck_colors[filter_key] = (
                            f"{display_label} ({ratings[std_key]}%)"
                        )
            except Exception as error:
                logger.error(error)
            return {v: k for k, v in deck_colors.items()}

    def retrieve_current_picked_cards(self):
        with self.lock:
            pack_index = max(self.current_pick - 1, 0) % self.number_of_players
            if pack_index < len(self.picked_cards):
                return self.set_data.get_data_by_id(self.picked_cards[pack_index])
            return []

    def retrieve_current_missing_cards(self):
        with self.lock:
            try:
                pack_index = max(self.current_pick - 1, 0) % self.number_of_players
                if pack_index < len(self.pack_cards) and pack_index < len(
                    self.initial_pack
                ):
                    card_list = [
                        x
                        for x in self.initial_pack[pack_index]
                        if x not in self.pack_cards[pack_index]
                    ]
                    return self.set_data.get_data_by_id(card_list)
            except Exception as error:
                logger.error(error)
            return []

    def retrieve_current_pack_cards(self):
        with self.lock:
            if self.current_pick == 0:
                return []
            pack_index = (self.current_pick - 1) % self.number_of_players
            if pack_index < len(self.pack_cards):
                cards = self.pack_cards[pack_index]
                expected_max = 15 - ((self.current_pick - 1) // self.number_of_players)
                if self.current_pick > 1 and len(cards) > expected_max:
                    return []
                return self.set_data.get_data_by_id(cards)
            return []

    def retrieve_taken_cards(self):
        with self.lock:
            return self.set_data.get_data_by_id(self.taken_cards)

    def retrieve_current_pack_and_pick(self):
        with self.lock:
            return self.current_pack, self.current_pick

    def retrieve_current_limited_event(self):
        with self.lock:
            return (self.draft_sets[0] if self.draft_sets else ""), self.draft_label

    def _record_pack(self, pack, pick, card_ids):
        if (
            self.draft_history
            and self.draft_history[-1]["Pack"] == pack
            and self.draft_history[-1]["Pick"] == pick
        ):
            return
        if not self.draft_history or (
            self.draft_history[-1]["Pack"] != pack
            or self.draft_history[-1]["Pick"] != pick
        ):
            self.draft_history.append({"Pack": pack, "Pick": pick, "Cards": card_ids})

    def retrieve_draft_history(self):
        with self.lock:
            return self.draft_history

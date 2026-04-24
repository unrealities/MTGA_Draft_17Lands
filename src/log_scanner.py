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
from src.tier_list import TierList
from src.utils import (
    process_json,
    json_find,
    retrieve_local_set_list,
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
        db_path: str = None,
    ):
        self.arena_file = filename
        self.set_list = set_list
        self.draft_log = logging.getLogger(LOG_TYPE_DRAFT)
        self.draft_log.setLevel(logging.INFO)
        self.sets_location = sets_location
        self.state_file = os.path.join(constants.TEMP_FOLDER, "active_draft_state.json")

        # CENTRAL DATA LOCK: Co-ordinates UI and Background Threading
        self.lock = threading.RLock()

        self.logging_enabled = False
        self.step_through = step_through
        self.set_data = Dataset(retrieve_unknown, db_path)
        self.tier_list = TierList()
        self.draft_type = constants.LIMITED_TYPE_UNKNOWN

        # File Pointers
        self.pick_offset = 0
        self.pack_offset = 0
        self.pool_offset = 0
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
        self.current_transaction_id = ""
        self.draft_label = ""
        self.draft_history = []
        self.current_draft_id = ""
        self.draft_start_time = ""
        self._last_seen_timestamp = "Unknown"
        self._load_state()

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

                # Do not write to past draft logs
                if os.path.basename(filename).startswith("DraftLog_"):
                    self.log_enable(False)

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
        if not self.logging_enabled:
            return

        try:
            log_name = f"DraftLog_{card_set}_{event}_{draft_id}.log"
            log_path = os.path.join(constants.DRAFT_LOG_FOLDER, log_name)

            # Prevent writing to the file we are currently reading
            if os.path.abspath(self.arena_file) == os.path.abspath(log_path):
                return

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

    def _load_state(self, target_draft_id=None):
        """Recovers the active draft state if the app was closed mid-draft."""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, "r", encoding="utf-8") as f:
                    state = json.load(f)

                # If an ID is provided, strictly match it.
                if target_draft_id is not None and str(
                    state.get("current_draft_id", "")
                ) != str(target_draft_id):
                    return False

                self.draft_type = state.get(
                    "draft_type", constants.LIMITED_TYPE_UNKNOWN
                )
                self.draft_sets = state.get("draft_sets", [])
                self.draft_label = state.get("draft_label", "")
                self.event_string = state.get("event_string", "")
                self.current_draft_id = state.get("current_draft_id", "")
                self.current_transaction_id = state.get("current_transaction_id", "")
                self.number_of_players = state.get("number_of_players", 8)
                self.taken_cards = state.get("taken_cards", [])
                self.picked_cards = state.get(
                    "picked_cards", [[] for _ in range(self.number_of_players)]
                )
                self.initial_pack = state.get(
                    "initial_pack", [[] for _ in range(self.number_of_players)]
                )
                self.pack_cards = state.get(
                    "pack_cards", [[] for _ in range(self.number_of_players)]
                )
                self.current_pack = state.get("current_pack", 0)
                self.current_pick = state.get("current_pick", 0)
                self.previous_scanned_pack = state.get("previous_scanned_pack", 0)
                self.previous_picked_pack = state.get("previous_picked_pack", 0)
                self.current_picked_pick = state.get("current_picked_pick", 0)
                self.draft_history = state.get("draft_history", [])
                self.draft_start_time = state.get("draft_start_time", "")

                if self.draft_type != constants.LIMITED_TYPE_UNKNOWN:
                    logger.info(
                        f"Restored previous draft state: {self.event_string} (Pack {self.current_pack}, Pick {self.current_pick})"
                    )

                return True
        except Exception as e:
            logger.error(f"Failed to load draft state: {e}")
        return False

    def _save_state(self):
        """Persists the memory state to disk to survive application crashes."""
        try:
            state = {
                "draft_type": self.draft_type,
                "draft_sets": self.draft_sets,
                "draft_label": self.draft_label,
                "event_string": self.event_string,
                "current_draft_id": self.current_draft_id,
                "current_transaction_id": getattr(self, "current_transaction_id", ""),
                "number_of_players": self.number_of_players,
                "taken_cards": self.taken_cards,
                "picked_cards": self.picked_cards,
                "initial_pack": self.initial_pack,
                "pack_cards": self.pack_cards,
                "current_pack": self.current_pack,
                "current_pick": self.current_pick,
                "previous_scanned_pack": self.previous_scanned_pack,
                "previous_picked_pack": self.previous_picked_pack,
                "current_picked_pick": self.current_picked_pick,
                "draft_history": self.draft_history,
                "draft_start_time": self.draft_start_time,
            }
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(state, f)
        except Exception as e:
            logger.error(f"Failed to save draft state: {e}")

    def clear_draft(self, full_clear):
        with self.lock:
            if full_clear:
                self.search_offset = 0
                self.draft_start_offset = 0
                self.file_size = 0
                self.current_transaction_id = ""
                if os.path.exists(self.state_file):
                    try:
                        os.remove(self.state_file)
                    except:
                        pass
                self.set_data.clear()

            self.draft_type = constants.LIMITED_TYPE_UNKNOWN
            self.pick_offset = 0
            self.pack_offset = 0
            self.pool_offset = 0
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
            self.draft_start_time = ""
            if not full_clear:
                self._save_state()

    def draft_start_search(self):
        """Search for the string that represents the start of a draft"""

        with self.lock:
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
            except Exception:
                return False

        update = False
        event_type = ""
        event_line = ""
        draft_id = ""

        try:
            with open(self.arena_file, "r", encoding="utf-8", errors="replace") as log:
                log.seek(offset)
                while True:
                    line = log.readline()
                    if not line:
                        break
                    if not line.endswith("\n") and not line.endswith("\r"):
                        break

                    offset = log.tell()

                    with self.lock:
                        self.search_offset = offset

                    if line.startswith("[UnityCrossThreadLogger]"):
                        content = line[24:].strip()
                        if content and content[0].isdigit() and (":" in content):
                            with self.lock:
                                self._last_seen_timestamp = content

                    start_offset = detect_string(line, constants.DRAFT_START_STRINGS)

                    if start_offset != -1:
                        entry_string = line[start_offset:]
                        event_data = process_json(entry_string)
                        is_new, et, did = self.__check_event(event_data)
                        if is_new:
                            update = True
                            event_type = et
                            draft_id = did
                            event_line = line
                            with self.lock:
                                self.draft_start_offset = offset
                                self.draft_start_time = self._last_seen_timestamp

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
                                        card_pool = json_find("CardPool", event_data)
                                        with self.lock:
                                            self.draft_start_offset = offset
                                            if card_pool:
                                                self.taken_cards = [
                                                    str(c) for c in card_pool
                                                ]
                        except Exception as e:
                            logger.error(f"Error parsing Deck Recovery line: {e}")

            if update:
                with self.lock:
                    if self.draft_sets:
                        self.__new_log(self.draft_sets[0], event_type, draft_id)
                    self.draft_log.info(event_line.strip())
                    self.pick_offset = self.draft_start_offset
                    self.pack_offset = self.draft_start_offset
                    self.pool_offset = self.draft_start_offset
        except Exception as error:
            logger.error(error)

        return update

    def __check_event(self, event_data):
        """Parse a draft start string and extract pertinent information"""
        update = False
        event_type = ""
        draft_id = ""
        try:
            raw_id = json_find("id", event_data)
            draft_id = str(raw_id) if raw_id is not None else ""
            event_name = json_find("EventName", event_data)

            with self.lock:
                current_event_string = self.event_string
                current_transaction_id = str(
                    getattr(self, "current_transaction_id", "")
                )

            if current_event_string == event_name:
                if current_transaction_id == draft_id:
                    return update, event_type, draft_id
                if json_find("EntryCurrencyType", event_data) is None:
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
                with self.lock:
                    self.draft_type = constants.LIMITED_TYPES_DICT[event_type]
                    self.draft_sets = event_set
                    self.draft_label = event_label
                    self.event_string = event_name
                    self.current_transaction_id = draft_id
                    self.number_of_players = number_of_players
                    self._save_state()
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
                    if section.upper() in ["TRAD", "COMP", "BOT", "PICK", "TWO"]:
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
        """A robust generator that handles all file IO and yielding of JSON payloads. Completely lock-free during IO."""
        offset = getattr(self, offset_attr, 0)

        try:
            with open(self.arena_file, "r", encoding="utf-8", errors="replace") as log:
                log.seek(offset)
                while True:
                    line = log.readline()
                    if not line:
                        break
                    if not line.endswith("\n") and not line.endswith("\r"):
                        break

                    current_pos = log.tell()
                    setattr(self, offset_attr, current_pos)

                    if line.startswith("[UnityCrossThreadLogger]"):
                        content = line[24:].strip()
                        if content and content[0].isdigit() and (":" in content):
                            self._last_seen_timestamp = content

                    start_idx = detect_string(line, search_strings)
                    if start_idx != -1:
                        self.draft_log.info(line.strip())
                        # Ensure we grab the start of the valid JSON dictionary
                        json_start = line.find("{")
                        if json_start != -1:
                            yield line[json_start:]
                        else:
                            yield line[start_idx:]
        except Exception as e:
            logger.error(f"Error scanning {search_strings}: {e}")

    def _parse_events(
        self, offset_attr: str, search_strings: list, extractor_func: callable
    ) -> bool:
        """Generic event processor that DRYs up JSON parsing, looping, and error handling."""
        update = False

        flat_search = []
        for s in search_strings:
            if isinstance(s, list):
                flat_search.extend(s)
            else:
                flat_search.append(s)

        for payload in self._scan_log_for_events(offset_attr, flat_search):
            try:
                draft_data = process_json(payload)
                if not draft_data:
                    try:
                        draft_data = json.loads(payload)
                    except Exception:
                        pass

                if draft_data and extractor_func(draft_data):
                    update = True

                if self.step_through:
                    break
            except Exception as e:
                logger.error(f"Parse Error for {flat_search}: {e}")
        return update

    def _process_pack_data(
        self,
        pack: int,
        pick: int,
        pack_cards: list,
        draft_id: str = None,
    ):
        """Universal handler for processing pack permutations across all Draft formats."""
        if not pack or not pick or not pack_cards:
            return False

        with self.lock:
            self._check_and_wipe_stale_pool(pack, pick, pack_cards, draft_id)

            expected_players = (
                4
                if self.draft_type
                in [
                    constants.LIMITED_TYPE_DRAFT_PICK_TWO,
                    constants.LIMITED_TYPE_DRAFT_PICK_TWO_TRAD,
                    constants.LIMITED_TYPE_DRAFT_PICK_TWO_QUICK,
                ]
                else 8
            )
            self.number_of_players = expected_players

            # Handle Pack Transitions securely
            if (
                pack > self.previous_scanned_pack
                or len(self.initial_pack) != expected_players
            ):
                self.initial_pack = [[] for _ in range(expected_players)]
                self.pack_cards = [[] for _ in range(expected_players)]
                self.previous_scanned_pack = pack
            elif pack < self.previous_scanned_pack:
                # Ignore severely delayed logs from a completely different pack to prevent memory corruption
                return False

            pack_index = (pick - 1) % expected_players

            # Prevent duplicate processing of the exact same pack
            if (
                len(self.pack_cards) > pack_index
                and self.pack_cards[pack_index] == pack_cards
            ):
                return False

            # Commit Data safely
            if len(self.initial_pack[pack_index]) == 0 and pick <= expected_players:
                self.initial_pack[pack_index] = pack_cards

            self.pack_cards[pack_index] = pack_cards

            # Update High Watermark
            is_new_high_watermark = False
            if pack > self.current_pack or (
                pack == self.current_pack and pick >= self.current_pick
            ):
                self.current_pack, self.current_pick = pack, pick
                is_new_high_watermark = True

            # Record History
            self._record_pack(pack, pick, pack_cards)
            self._save_state()

        return is_new_high_watermark

    def _process_pick_data(
        self, pack: int, pick: int, cards: list, draft_id: str = None
    ):
        """Universal handler for processing human and bot picks."""
        if not cards or not pack or not pick:
            return False

        with self.lock:
            self._check_and_wipe_stale_pool(pack, pick, cards, draft_id)

            # DYNAMIC EVENT UPGRADE: If MTGA mislabels a Pick-Two draft as a standard draft,
            # detect it based on the number of cards in the first pick payload.
            if len(cards) >= 2 and self.draft_type not in [
                constants.LIMITED_TYPE_DRAFT_PICK_TWO,
                constants.LIMITED_TYPE_DRAFT_PICK_TWO_TRAD,
                constants.LIMITED_TYPE_DRAFT_PICK_TWO_QUICK,
            ]:
                logger.info(
                    f"Dynamically upgrading event to Pick-Two based on payload size: {len(cards)}"
                )
                if self.draft_type == constants.LIMITED_TYPE_DRAFT_TRADITIONAL:
                    self.draft_type = constants.LIMITED_TYPE_DRAFT_PICK_TWO_TRAD
                elif self.draft_type == constants.LIMITED_TYPE_DRAFT_QUICK:
                    self.draft_type = constants.LIMITED_TYPE_DRAFT_PICK_TWO_QUICK
                else:
                    self.draft_type = constants.LIMITED_TYPE_DRAFT_PICK_TWO

            # Enforce maximum cards per pick to prevent MTGA JSON array-bloat bugs
            cards = cards[: self.cards_per_pick]

            expected_players = (
                4
                if self.draft_type
                in [
                    constants.LIMITED_TYPE_DRAFT_PICK_TWO,
                    constants.LIMITED_TYPE_DRAFT_PICK_TWO_TRAD,
                    constants.LIMITED_TYPE_DRAFT_PICK_TWO_QUICK,
                ]
                else 8
            )
            self.number_of_players = expected_players

            # Prevent duplicate processing of historical picks when reconstructing state
            if pack < self.previous_picked_pack:
                return False
            if pack == self.previous_picked_pack and pick <= self.current_picked_pick:
                return False

            pack_index = (pick - 1) % expected_players

            if (
                pack > self.previous_picked_pack
                or len(self.picked_cards) != expected_players
            ):
                self.picked_cards = [[] for _ in range(expected_players)]

            self.picked_cards[pack_index].extend(cards)
            self.taken_cards.extend(cards)

            self.previous_picked_pack = pack
            self.current_picked_pick = pick

            if pack > self.current_pack or (
                pack == self.current_pack and pick >= self.current_pick
            ):
                self.current_pack, self.current_pick = pack, pick

            self._save_state()
        return True

    def _check_and_wipe_stale_pool(self, pack, pick, current_cards, draft_id=None):
        wipe = False
        str_draft_id = str(draft_id) if draft_id else ""
        str_current_id = str(self.current_draft_id) if self.current_draft_id else ""

        # 1. Draft ID Exact Match Protection
        if str_draft_id and str_current_id:
            if str_draft_id != str_current_id:
                wipe = True
            else:
                return  # Exact match! We are definitely re-reading history. Do not wipe!
        elif str_draft_id and not str_current_id:
            if not self._load_state(str_draft_id) and self.taken_cards:
                wipe = True

            # 2. Time-Travel Protection (When Draft ID is missing or new)
            if not wipe:
                if pack == 1 and pick == 1 and len(self.taken_cards) > 0:
                    # STRICT WIPE: It is P1P1, but we have cards from an old draft.
                    wipe = True
                elif pack < self.current_pack or (
                    pack == self.current_pack and pick < self.current_pick
                ):
                    # We are seeing an older pack/pick.
                    is_historical = False
                    if not current_cards:
                        is_historical = True
                    elif self.draft_history:
                        for entry in self.draft_history:
                            if entry["Pack"] == pack and entry["Pick"] == pick:
                                if any(c in entry["Cards"] for c in current_cards):
                                    is_historical = True
                                break

                    if not is_historical:
                        wipe = True

            elif pack == 1 and pick == 1 and self.taken_cards:
                # If we see P1P1 and we already have a massive pool, we missed the end of the last draft.
                if (
                    len(self.taken_cards) > 15
                    or self.current_pack > 1
                    or self.current_pick > 1
                ):
                    wipe = True

        if wipe:
            logger.info(
                f"Stale Pool Wiped. Trigger: Pack {pack} Pick {pick} vs Current P{self.current_pack}P{self.current_pick}"
            )
            self.taken_cards = []
            self.picked_cards = [[] for _ in range(self.number_of_players)]
            self.draft_history = []
            self.sideboard = []
            self.current_pack = 0
            self.current_pick = 0
            self.previous_picked_pack = 0
            self.previous_scanned_pack = 0
            self.current_picked_pick = 0
            self.initial_pack = [[] for _ in range(self.number_of_players)]
            self.pack_cards = [[] for _ in range(self.number_of_players)]

        if str_draft_id and str_draft_id != str_current_id:
            self.current_draft_id = str_draft_id
            self._save_state()

    # =========================================================================
    # EVENT DISPATCHER
    # =========================================================================

    def draft_data_search(self):
        update = False
        changes = self.__perform_search_logic()

        is_unknown = False
        with self.lock:
            is_unknown = self.draft_type == constants.LIMITED_TYPE_UNKNOWN

        if is_unknown:
            self.draft_start_search()

        with self.lock:
            if changes:
                update = True

        return update

    def __perform_search_logic(self):
        """Dispatches log scanning safely lock-free."""
        with self.lock:
            pk, pi = self.current_pack, self.current_pick
            pp = self.current_picked_pick

        explicit_update = False

        # RECOVERY MODE: If the app restarts mid-draft and misses EventJoin,
        # infer the draft type from the active log events.
        if self.draft_type == constants.LIMITED_TYPE_UNKNOWN:
            if self._search_pack_notify() or self._search_pick_human():
                self.draft_type = constants.LIMITED_TYPE_DRAFT_PREMIER_V2
                self.number_of_players = 8
                explicit_update = True
            elif self._search_pack_bot() or self._search_pick_bot():
                self.draft_type = constants.LIMITED_TYPE_DRAFT_QUICK
                self.number_of_players = 8
                explicit_update = True
            elif self._search_card_pool():
                self.draft_type = constants.LIMITED_TYPE_SEALED
                explicit_update = True

        if self.draft_type == constants.LIMITED_TYPE_DRAFT_PREMIER_V1:
            explicit_update |= self._search_pick_v1()
            explicit_update |= self._search_pack_notify()
            explicit_update |= self._search_card_pool()
        elif self.draft_type in [
            constants.LIMITED_TYPE_DRAFT_PREMIER_V2,
            constants.LIMITED_TYPE_DRAFT_PICK_TWO,
            constants.LIMITED_TYPE_DRAFT_TRADITIONAL,
            constants.LIMITED_TYPE_DRAFT_PICK_TWO_TRAD,
        ]:
            explicit_update |= self._search_pick_human()
            explicit_update |= self._search_pack_notify()
            explicit_update |= self._search_card_pool()
        elif self.draft_type in [
            constants.LIMITED_TYPE_DRAFT_QUICK,
            constants.LIMITED_TYPE_DRAFT_PICK_TWO_QUICK,
        ]:
            explicit_update |= self._search_pick_bot()
            explicit_update |= self._search_pack_bot()
            explicit_update |= self._search_card_pool()
        elif self.draft_type in [
            constants.LIMITED_TYPE_SEALED,
            constants.LIMITED_TYPE_SEALED_TRADITIONAL,
        ]:
            explicit_update |= self._search_card_pool()

        with self.lock:
            return bool(
                (pk != self.current_pack)
                or (pi != self.current_pick)
                or (pp != self.current_picked_pick)
                or explicit_update
            )

    # =========================================================================
    # MODULAR PARSERS
    # =========================================================================

    def _search_pack_notify(self) -> bool:
        def _extract(data):
            cards_raw = json_find("PackCards", data)
            if not cards_raw:
                return False

            p_val = json_find("SelfPack", data)
            pi_val = json_find("SelfPick", data)
            pack = int(p_val) if p_val is not None else 0
            pick = int(pi_val) if pi_val is not None else 0

            draft_id = json_find("DraftId", data)
            if draft_id is None:
                draft_id = json_find("draftId", data)

            pack_cards = (
                [str(c) for c in cards_raw]
                if isinstance(cards_raw, list)
                else str(cards_raw).split(",")
            )

            return self._process_pack_data(
                pack=pack,
                pick=pick,
                pack_cards=pack_cards,
                draft_id=str(draft_id) if draft_id else "",
            )

        return self._parse_events(
            "pack_offset", [constants.DRAFT_PACK_STRING_PREMIER], _extract
        )

    def _search_pick_human(self) -> bool:
        def _extract(data):
            grp_ids = json_find("GrpIds", data)
            if grp_ids is None:
                grp_ids = json_find("cardIds", data)

            if grp_ids is not None and isinstance(grp_ids, list):
                cards = [str(x) for x in grp_ids if str(x) != "0"]
            else:
                grp_id = json_find("GrpId", data)
                if grp_id is None:
                    grp_id = json_find("cardId", data)
                if grp_id is None:
                    grp_id = json_find("PickGrpId", data)
                cards = (
                    [str(grp_id)] if grp_id is not None and str(grp_id) != "0" else []
                )

            if not cards:
                return False

            p_val = json_find("Pack", data)
            if p_val is None:
                p_val = json_find("packNumber", data)
            pi_val = json_find("Pick", data)
            if pi_val is None:
                pi_val = json_find("pickNumber", data)

            pack = int(p_val) if p_val is not None else 0
            pick = int(pi_val) if pi_val is not None else 0

            draft_id = json_find("DraftId", data)
            if draft_id is None:
                draft_id = json_find("draftId", data)

            return self._process_pick_data(
                pack=pack,
                pick=pick,
                cards=cards,
                draft_id=str(draft_id) if draft_id else "",
            )

        return self._parse_events(
            "pick_offset", [constants.DRAFT_PICK_STRING_PREMIER], _extract
        )

    def _search_pick_v1(self) -> bool:
        def _extract(data):
            p_val = json_find("Pack", data)
            pi_val = json_find("Pick", data)
            pack = int(p_val) if p_val is not None else 0
            pick = int(pi_val) if pi_val is not None else 0

            grp_id = json_find("GrpId", data)
            cards = [str(grp_id)] if grp_id is not None and str(grp_id) != "0" else []
            if not cards:
                return False

            draft_id = json_find("DraftId", data)
            if draft_id is None:
                draft_id = json_find("draftId", data)

            return self._process_pick_data(
                pack=pack,
                pick=pick,
                cards=cards,
                draft_id=str(draft_id) if draft_id else "",
            )

        return self._parse_events(
            "pick_offset", [constants.DRAFT_PICK_STRING_PREMIER_OLD], _extract
        )

    def _search_pack_bot(self) -> bool:
        def _extract(data):
            if json_find("DraftStatus", data) != "PickNext":
                return False
            cards = json_find("DraftPack", data)
            if not cards:
                return False

            p_val = json_find("PackNumber", data)
            pi_val = json_find("PickNumber", data)
            # Bot drafts are 0-indexed! So we add 1.
            pack = int(p_val) + 1 if p_val is not None else 1
            pick = int(pi_val) + 1 if pi_val is not None else 1

            pack_cards = (
                [str(c) for c in cards]
                if isinstance(cards, list)
                else str(cards).split(",")
            )
            changed = self._process_pack_data(pack, pick, pack_cards)

            # Quick draft explicit taken cards sync
            picked = json_find("PickedCards", data)
            if picked:
                picked_list = (
                    [str(c) for c in picked]
                    if isinstance(picked, list)
                    else str(picked).split(",")
                )
                if len(picked_list) > len(self.taken_cards):
                    self.taken_cards = picked_list
                    self.picked_cards[0] = self.taken_cards
                    changed = True
            return changed

        return self._parse_events(
            "pack_offset", [constants.DRAFT_PACK_STRING_QUICK], _extract
        )

    def _search_pick_bot(self) -> bool:
        def _extract(data):
            cids = json_find("CardIds", data)
            if cids is None:
                cids = json_find("cardIds", data)

            if cids is not None and isinstance(cids, list):
                cards = [str(x) for x in cids if str(x) != "0"]
            else:
                cid = json_find("CardId", data)
                if cid is None:
                    cid = json_find("cardId", data)
                cards = [str(cid)] if cid is not None and str(cid) != "0" else []

            if not cards:
                return False

            p_val = json_find("PackNumber", data)
            pi_val = json_find("PickNumber", data)
            pack = int(p_val) + 1 if p_val is not None else 1
            pick = int(pi_val) + 1 if pi_val is not None else 1

            return self._process_pick_data(
                pack=pack,
                pick=pick,
                cards=cards,
            )

        return self._parse_events(
            "pick_offset", [constants.DRAFT_PICK_STRING_QUICK], _extract
        )

    def _search_card_pool(self):
        update = False
        for payload in self._scan_log_for_events("pool_offset", ['"CardPool":[']):
            try:
                data = process_json(payload)
                if not data:
                    continue
                pool = []

                with self.lock:
                    current_event_string = self.event_string

                # Check root first
                if "CardPool" in data and "InternalEventName" in data:
                    detected_event_name = data.get("InternalEventName")
                    if (
                        not current_event_string
                        or detected_event_name == current_event_string
                    ):
                        pool.extend(data.get("CardPool", []))
                else:
                    course = data.get("Course", data.get("Courses", {}))
                    if isinstance(course, list):
                        for c in course:
                            name = c.get("InternalEventName")
                            if not current_event_string or name == current_event_string:
                                detected_event_name = name
                                pool.extend(c.get("CardPool", []))
                                break
                    elif isinstance(course, dict):
                        name = course.get("InternalEventName")
                        if not current_event_string or name == current_event_string:
                            detected_event_name = name
                            pool.extend(course.get("CardPool", []))

                # RECOVERY: If we found a pool but didn't have an event registered, register it now
                if pool and not current_event_string and detected_event_name:
                    dummy_payload = {"EventName": detected_event_name}
                    self.__check_event(dummy_payload)

                if pool:
                    pool_strs = [str(x) for x in pool]
                    with self.lock:
                        if not self.taken_cards or sorted(self.taken_cards) != sorted(
                            pool_strs
                        ):
                            self.taken_cards = pool_strs
                            self._save_state()
                            update = True
            except Exception as e:
                logger.error(f"Card Pool Search Error: {e}")
        return update

    # =========================================================================
    # DATA RETRIEVAL
    # =========================================================================

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
            if self.current_pick == 0:
                return []

            expected_players = (
                4
                if self.draft_type
                in [
                    constants.LIMITED_TYPE_DRAFT_PICK_TWO,
                    constants.LIMITED_TYPE_DRAFT_PICK_TWO_TRAD,
                    constants.LIMITED_TYPE_DRAFT_PICK_TWO_QUICK,
                ]
                else 8
            )

            pack_index = (self.current_pick - 1) % expected_players
            if pack_index < len(self.picked_cards):
                return self.set_data.get_data_by_id(self.picked_cards[pack_index])
            return []

    def retrieve_current_missing_cards(self):
        with self.lock:
            try:
                expected_players = (
                    4
                    if self.draft_type
                    in [
                        constants.LIMITED_TYPE_DRAFT_PICK_TWO,
                        constants.LIMITED_TYPE_DRAFT_PICK_TWO_TRAD,
                        constants.LIMITED_TYPE_DRAFT_PICK_TWO_QUICK,
                    ]
                    else 8
                )

                pack_index = (self.current_pick - 1) % expected_players
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

            expected_players = (
                4
                if self.draft_type
                in [
                    constants.LIMITED_TYPE_DRAFT_PICK_TWO,
                    constants.LIMITED_TYPE_DRAFT_PICK_TWO_TRAD,
                    constants.LIMITED_TYPE_DRAFT_PICK_TWO_QUICK,
                ]
                else 8
            )

            pack_index = (self.current_pick - 1) % expected_players
            if pack_index < len(self.pack_cards):
                # We return copies of the card dicts so the UI can mutate them (e.g. for display names)
                raw_cards = self.set_data.get_data_by_id(self.pack_cards[pack_index])
                pack_cards = []

                # WHEEL PREDICTION: Cross-reference initial_pack slots to see which cards might come back.
                rotation_size = expected_players

                returnable_picks_by_name = {}
                for i, slot_ids in enumerate(self.initial_pack):
                    if i == pack_index or not slot_ids:
                        continue
                    # A pack from slot i wheels back at pick (i+1) + rotation_size
                    return_pick = (i + 1) + rotation_size
                    if return_pick > self.current_pick:
                        picked_from_slot = set(
                            self.picked_cards[i] if i < len(self.picked_cards) else []
                        )
                        remaining_ids = [
                            cid for cid in slot_ids if cid not in picked_from_slot
                        ]
                        for name in self.set_data.get_names_by_id(remaining_ids):
                            returnable_picks_by_name.setdefault(name, []).append(
                                return_pick
                            )

                for card in raw_cards:
                    card_copy = dict(card)
                    name = card.get(constants.DATA_FIELD_NAME, "")
                    card_copy["returnable_at"] = sorted(
                        returnable_picks_by_name.get(name, [])
                    )
                    pack_cards.append(card_copy)

                return pack_cards
            return []

    @property
    def cards_per_pick(self):
        """Returns the number of cards taken per passing round (usually 1, or 2 for PickTwo)."""
        if self.draft_type in [
            constants.LIMITED_TYPE_DRAFT_PICK_TWO,
            constants.LIMITED_TYPE_DRAFT_PICK_TWO_TRAD,
            constants.LIMITED_TYPE_DRAFT_PICK_TWO_QUICK,
        ]:
            return 2
        return 1

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

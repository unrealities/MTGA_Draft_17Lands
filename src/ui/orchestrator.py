import os
import logging
import threading
import time
import queue
from src.configuration import write_configuration

logger = logging.getLogger(__name__)


class DraftOrchestrator(threading.Thread):
    def __init__(self, scanner, configuration, refresh_callback):
        super().__init__()
        self.scanner = scanner
        self.config = configuration
        self.refresh_callback = refresh_callback

        self.loading = False
        self.new_event_detected = False

        self._stop_event = threading.Event()
        self._force_math_event = threading.Event()
        self._force_full_scan_event = threading.Event()

        self.daemon = True
        self.update_queue = queue.Queue()
        self._last_file_size = -1

        # Thread-safe queue for file swaps
        self._file_swap_queue = queue.Queue()

        # Live tracking
        self.live_log_path = configuration.settings.arena_log_location
        self._last_live_file_size = -1
        if self.live_log_path and os.path.exists(self.live_log_path):
            self._last_live_file_size = os.path.getsize(self.live_log_path)

    def set_file_and_scan(self, filepath):
        """Thread-safe way for the UI to request a log file change."""
        self._file_swap_queue.put(filepath)

    def trigger_full_scan(self):
        """Thread-safe way for the UI to demand a deep log scan."""
        self._force_full_scan_event.set()

    def stop(self):
        self._stop_event.set()

    def request_math_update(self):
        self._force_math_event.set()

    def run(self):
        logger.info("Background Watchdog started.")
        while not self._stop_event.is_set():

            # Automatically snap back to the live draft log if activity is detected
            if getattr(self, "live_log_path", None) and os.path.exists(
                self.live_log_path
            ):
                try:
                    current_live_size = os.path.getsize(self.live_log_path)
                    if self.scanner.arena_file != self.live_log_path:
                        # We are looking at a past log. Check for live activity.
                        if (
                            self._last_live_file_size != -1
                            and current_live_size != self._last_live_file_size
                        ):
                            logger.info(
                                "Live log activity detected. Snapping back to live draft."
                            )
                            self._last_live_file_size = current_live_size
                            self.set_file_and_scan(self.live_log_path)
                    else:
                        self._last_live_file_size = current_live_size
                except Exception:
                    pass

            # 1. Safely execute file swaps on the background thread
            new_file = None
            try:
                # Flush the queue to only process the very LAST click (prevents queue buildup)
                while not self._file_swap_queue.empty():
                    new_file = self._file_swap_queue.get_nowait()
            except queue.Empty:
                pass

            if new_file:
                self.loading = True
                self.update_queue.put({"status": "Scanning Log..."})
                try:
                    self.scanner.set_arena_file(new_file)

                    if new_file != getattr(self, "live_log_path", None):
                        self.scanner.log_enable(False)
                    else:
                        self.scanner.log_enable(self.config.settings.draft_log_enabled)

                    self.scanner.draft_start_search()
                    self.sync_dataset_to_event()

                    self.update_queue.put({"status": "Parsing Picks..."})
                    self.scanner.draft_data_search(False, False)
                except Exception as e:
                    logger.error(f"Error processing file swap: {e}")
                finally:
                    self.loading = False
                    self.update_queue.put("REFRESH")

            # 2. Check if file changed OR if a manual event was triggered
            if not self.loading and (
                self._file_has_changed()
                or self._force_full_scan_event.is_set()
                or self._force_math_event.is_set()
            ):
                # Acquire lock briefly, do work, release
                self.step_process()

            # Yield to the UI thread between polls
            time.sleep(0.5)

    def _file_has_changed(self):
        """Returns True if the log file size has changed since the last scan.
        Does NOT mutate _last_file_size — that is owned by check_for_updates()."""
        try:
            current_size = os.path.getsize(self.scanner.arena_file)
            return current_size != self._last_file_size
        except:
            pass
        return False

    def step_process(self):
        if not self.loading:
            try:
                # Check our flag safely on the background thread
                force = self._force_full_scan_event.is_set()
                if force:
                    self._force_full_scan_event.clear()

                log_changed = self.check_for_updates(force=force)
                if log_changed or self._force_math_event.is_set():
                    self._force_math_event.clear()
                    self.update_queue.put("REFRESH")
            except Exception as e:
                logger.error(f"Logic Step Error: {e}")

    def check_for_updates(self, force=False):
        """
        Scans for changes. If 'force' is True, bypasses the file-size check.
        """
        try:
            current_size = os.path.getsize(self.scanner.arena_file)
            if not force and current_size == self._last_file_size:
                return False

            # Define first_run for the Mock-Safe check below
            first_run = self._last_file_size == -1
            self._last_file_size = current_size
        except:
            return False

        changed = False
        # SEARCH 1: Did the user join a new event?
        if self.scanner.draft_start_search():
            changed, self.new_event_detected = True, True
            self.sync_dataset_to_event()  # Guarantee card dictionary is mapped immediately

        # SEARCH 2: Is there new pack/pick data?
        if self.scanner.draft_data_search(use_ocr=False, save_screenshot=False):
            changed = True

        # MOCK-SAFE FIRST RUN CHECK:
        # We use try/except to handle MagicMocks in unit tests
        if first_run:
            try:
                # Check pack/pick/pool. If any exist, force a refresh for tests
                pk, _ = self.scanner.retrieve_current_pack_and_pick()
                pool = self.scanner.retrieve_taken_cards()
                if (pk and int(pk) > 0) or pool:
                    changed = True
            except (TypeError, ValueError):
                # Fallback for MagicMocks or non-integer values
                changed = True
        return changed

    def sync_dataset_to_event(
        self, target_set=None, target_format=None, target_user=None
    ):
        with self.scanner.lock:
            event_set, _ = self.scanner.retrieve_current_limited_event()
            s_code = target_set or event_set
            if not s_code:
                return False
            sources = self.scanner.retrieve_data_sources()
            for label, path in sources.items():
                if f"[{s_code.upper()}]" in label.upper():
                    # CACHE HIT: Skip reading the massive 25MB JSON file!
                    if (
                        self.config.card_data.latest_dataset == os.path.basename(path)
                        and self.scanner.set_data._dataset is not None
                    ):
                        return True

                    # Notify UI of heavy operation
                    self.update_queue.put({"status": f"Loading {s_code} Dataset..."})

                    self.scanner.retrieve_set_data(path)
                    self.config.card_data.latest_dataset = os.path.basename(path)
                    write_configuration(self.config)
                    return True
            return False

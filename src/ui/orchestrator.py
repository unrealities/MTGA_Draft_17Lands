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
        self.scanner, self.config, self.refresh_callback = (
            scanner,
            configuration,
            refresh_callback,
        )
        self.loading, self.new_event_detected = False, False
        self._stop_event, self._force_math_event = threading.Event(), threading.Event()
        self.daemon, self.update_queue, self._last_file_size = True, queue.Queue(), -1
        self._force_full_scan_event = threading.Event()

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
            # Check if file changed OR if a manual event was triggered
            if (
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

        with self.scanner.lock:
            changed = False
            # SEARCH 1: Did the user join a new event?
            if self.scanner.draft_start_search():
                changed, self.new_event_detected = True, True
                self.sync_dataset_to_event()

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
                    self.scanner.retrieve_set_data(path)
                    self.config.card_data.latest_dataset = os.path.basename(path)
                    write_configuration(self.config)
                    return True
            return False

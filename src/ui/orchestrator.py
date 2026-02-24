import os
import logging
from src.configuration import write_configuration

logger = logging.getLogger(__name__)


class DraftOrchestrator:
    def __init__(self, scanner, configuration, refresh_callback):
        self.scanner = scanner
        self.config = configuration
        self.refresh_callback = refresh_callback
        self.loading = False
        self.new_event_detected = False

    def update_cycle(self):
        """Standard check for log updates."""
        if self.loading:
            return False

        try:
            current_size = os.path.getsize(self.scanner.arena_file)
            if current_size == getattr(self, "_last_file_size", -1):
                return False  # File hasn't grown; skip the expensive open/read/close operations
            self._last_file_size = current_size
        except OSError:
            return False

        changed = False
        self.new_event_detected = False

        # 1. New Event Detection
        if self.scanner.draft_start_search():
            logger.info("New event detected in logs.")
            changed = True
            self.new_event_detected = True
            # Sync automatically based on scanner state
            self.sync_dataset_to_event()

        # 2. New Data Detection (Pack/Pick)
        if self.scanner.draft_data_search(use_ocr=False, save_screenshot=False):
            changed = True

        if changed:
            self.refresh_callback()

        return changed

    def sync_dataset_to_event(
        self, target_set=None, target_format=None, target_user=None
    ):
        """
        Aligns the active JSON dataset.
        If targets are provided (e.g. from tests/notifications), it uses them.
        Otherwise, it retrieves current state from the scanner.
        """
        event_set, event_format = self.scanner.retrieve_current_limited_event()

        s_code = target_set or event_set
        f_code = target_format or event_format
        u_code = target_user or "All"

        if not s_code:
            return False

        sources = self.scanner.retrieve_data_sources()

        exact_match = None
        format_match = None
        set_match = None

        set_prefix = f"[{s_code}]"

        for label, path in sources.items():
            if set_prefix in label:
                if not set_match:
                    set_match = path

                if f_code and f_code in label:
                    if not format_match:
                        format_match = path

                    if f"({u_code})" in label:
                        exact_match = path
                        break

        final_path = exact_match or format_match or set_match

        if final_path:
            logger.info(f"Syncing dataset to: {final_path}")
            self.scanner.retrieve_set_data(final_path)
            self.config.card_data.latest_dataset = os.path.basename(final_path)
            write_configuration(self.config)
            return True

        return False

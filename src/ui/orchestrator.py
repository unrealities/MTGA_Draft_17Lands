"""
src/ui/orchestrator.py
Logic Controller for the MTGA Draft Tool.
"""

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

    def update_cycle(self):
        """Standard check for log updates."""
        if self.loading:
            return False

        changed = False
        # 1. New Event Detection
        if self.scanner.draft_start_search():
            logger.info("New event detected in logs.")
            changed = True
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
        if not s_code:
            return False

        sources = self.scanner.retrieve_data_sources()

        # Priority Search: Try to find [SET] + (All) specifically first
        priority_match = None
        fallback_match = None

        for label, path in sources.items():
            # Matches based on the [SET] prefix in the source label
            if f"[{s_code}]" in label:
                if "(All)" in label:
                    priority_match = path
                else:
                    fallback_match = path

        final_path = priority_match or fallback_match

        if final_path:
            logger.info(f"Syncing dataset to: {final_path}")
            self.scanner.retrieve_set_data(final_path)
            self.config.card_data.latest_dataset = os.path.basename(final_path)
            write_configuration(self.config)
            return True

        return False

# -*- coding: utf-8 -*-
import sys
import os
import tkinter.messagebox
from datetime import datetime, date, timedelta
from src.configuration import Configuration, write_configuration, read_configuration
from src.app_update import AppUpdate
from src.logger import create_logger
from src.utils import retrieve_local_set_list, read_dataset_info
from src.seventeenlands import Seventeenlands
from src.ui.windows.download import DownloadWindow, DatasetArgs
from src.constants import (
    PLATFORM_ID_WINDOWS,
    APPLICATION_VERSION,
    START_DATE_DEFAULT,
    LIMITED_TYPE_STRING_DRAFT_PREMIER,
    LIMITED_USER_GROUP_ALL,
    LIMITED_TYPE_STRING_DRAFT_QUICK,
    LIMITED_TYPE_STRING_DRAFT_BOT,
)

logger = create_logger()


class Notifications:
    def __init__(
        self,
        root,
        expansions,
        configuration: Configuration,
        dataset_window: DownloadWindow,
    ):
        self.configuration = configuration
        self.root = root
        self.expansions = (
            {v.seventeenlands[0]: k for k, v in expansions.data.items()}
            if expansions
            else {}
        )
        self.dataset_window = dataset_window
        self.update = AppUpdate()

    def check_for_updates(self):
        if self.check_application():
            return False
        if self.check_arena_log():
            return True
        self.check_dataset()
        return True

    def prompt_missing_dataset(self, set_code, current_event_type, full_set_name=None):
        """Displays a prompt allowing users to immediately route to the Dataset window for a missing set."""
        display_name = full_set_name if full_set_name else set_code

        msg = (
            f"No dataset found for {display_name} ({current_event_type}).\n\n"
            f"Would you like to automatically download the 17Lands 'All Users' data for this event?"
        )

        if tkinter.messagebox.askyesno("Missing Dataset", msg):
            args = DatasetArgs(
                draft_set=set_code,
                draft=current_event_type if current_event_type else "PremierDraft",
                start=str(
                    date.today() - timedelta(days=90)
                ),  # Will mostly be overwritten by dataset manager dropdown logic
                end=str(date.today()),
                user_group="All",
                game_count=0,
                color_ratings=None,
            )
            # Switch to the Data tab in the UI
            if hasattr(self.root, "event_generate"):
                self.root.event_generate("<<ShowDataTab>>")

            self.dataset_window.enter(args)

    def check_dataset(self):
        if (
            self.configuration.settings.update_notifications_enabled
            and self.configuration.card_data.latest_dataset
        ):
            import threading

            threading.Thread(target=self.update_dataset, daemon=True).start()

    def update_dataset(self):
        try:
            from src.dataset_updater import DatasetUpdater

            def silent_progress(msg):
                pass

            updater = DatasetUpdater(self.configuration)
            updater.sync_datasets(silent_progress)

        except Exception as e:
            logger.error(f"Notification error: {e}")

    def update_latest_dataset(self, path):
        name = os.path.basename(path)
        if self.configuration.card_data.latest_dataset != name:
            self.configuration.card_data.latest_dataset = name
            write_configuration(self.configuration)

    def check_arena_log(self) -> bool:
        return not bool(self.configuration.settings.arena_log_location)

    def check_application(self) -> bool:
        return False

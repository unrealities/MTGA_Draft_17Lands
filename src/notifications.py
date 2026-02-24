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

    def prompt_missing_dataset(self, current_set, current_event_type):
        """Displays a prompt allowing users to immediately route to the Dataset window for a missing set."""
        if tkinter.messagebox.askyesno(
            "Missing Dataset",
            f"No dataset found for expansion {current_set} ({current_event_type}).\n\nWould you like to open the Dataset Manager to download it now?",
        ):
            args = DatasetArgs(
                draft_set=current_set,
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
            self.update_dataset()

    def update_dataset(self):
        try:
            current_time = datetime.now().timestamp()
            if (
                self.configuration.card_data.last_auto_check
                and (current_time - self.configuration.card_data.last_auto_check)
                < 86400
            ):
                return

            dataset_info = read_dataset_info(
                self.configuration.card_data.latest_dataset
            )
            if not dataset_info:
                return

            set_name = dataset_info[0]
            event_type = dataset_info[1]
            user_group = dataset_info[2]

            logger.info(
                f"Checking updates for {set_name} {event_type} ({user_group} players)..."
            )

            # Fetch summary only (fast check)
            color_ratings, game_count = Seventeenlands().download_color_ratings(
                dataset_info[0],
                dataset_info[1],
                dataset_info[3],
                str(date.today()),
                dataset_info[2],
            )

            # Local game count (index 5) vs Remote game count
            local_count = dataset_info[5]

            # Update timestamp to prevent spam
            self.configuration.card_data.last_auto_check = current_time
            write_configuration(self.configuration)

            if game_count > local_count:
                logger.info(
                    f"New data found for {set_name} {event_type} ({user_group} players): "
                    f"Local {local_count} vs Remote {game_count}"
                )

                prompt_msg = (
                    f"New data available for {set_name} - {event_type} ({user_group} players).\n\n"
                    f"Local Games: {local_count:,}\n"
                    f"Remote Games: {game_count:,}\n\n"
                    f"Would you like to update now?"
                )

                if tkinter.messagebox.askyesno("Dataset Update", prompt_msg):
                    args = DatasetArgs(
                        dataset_info[0],
                        dataset_info[1],
                        str(date.today()),
                        str(date.today()),
                        dataset_info[2],
                        game_count,
                        color_ratings,
                    )

                    # Switch to the Data tab in the UI
                    if hasattr(self.root, "event_generate"):
                        self.root.event_generate("<<ShowDataTab>>")

                    self.dataset_window.enter(args)
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

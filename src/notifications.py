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

    def check_dataset(self):
        if (
            self.configuration.settings.update_notifications_enabled
            and self.configuration.card_data.latest_dataset
        ):
            self.update_dataset()

    def update_dataset(self):
        try:
            current_time = datetime.now().timestamp()
            if (current_time - self.configuration.card_data.last_auto_check) < 86400:
                return

            self.configuration.card_data.last_auto_check = current_time
            write_configuration(self.configuration)

            dataset_info = read_dataset_info(
                self.configuration.card_data.latest_dataset
            )
            if not dataset_info:
                return

            color_ratings, game_count = Seventeenlands().download_color_ratings(
                dataset_info[0],
                dataset_info[1],
                dataset_info[3],
                str(date.today()),
                dataset_info[2],
            )

            if game_count > dataset_info[5]:
                if tkinter.messagebox.askyesno(
                    "Dataset Update",
                    f"New data available for {dataset_info[0]}. Update now?",
                ):
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

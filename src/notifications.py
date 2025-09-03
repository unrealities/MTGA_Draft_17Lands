# -*- coding: utf-8 -*-
import sys
import os
import tkinter.messagebox
from datetime import datetime, date
from src.configuration import Configuration
from src.app_update import AppUpdate
from src.logger import create_logger
from src.constants import PLATFORM_ID_WINDOWS, APPLICATION_VERSION, START_DATE_DEFAULT, LIMITED_TYPE_STRING_DRAFT_PREMIER, LIMITED_USER_GROUP_ALL
from src.utils import retrieve_local_set_list, read_dataset_info
from src.configuration import write_configuration, read_configuration
from src.seventeenlands import Seventeenlands
from src.download_dataset import DownloadDatasetWindow, DatasetArgs
try:
    import win32api
except ImportError:
    pass

logger = create_logger()

NOTIFICATION_DATASET_RATE_LIMIT_SEC = 3600 # 1 hour

class Notifications:
    """Handles app notifications"""
    def __init__(self, root, expansions, configuration: Configuration, dataset_window: DownloadDatasetWindow):
        self.configuration = configuration
        self.root = root
        self.new_version = ""
        self.file_location = ""
        self.expansions = {v.seventeenlands[0] : k for k,v in expansions.data.items()}
        self.dataset_window = dataset_window
        self.update = AppUpdate()

    def check_for_updates(self) -> bool:
        """Entry point for the class"""
        if self._check_application():
            return False
        if self._check_arena_log():
            return True
        self._check_dataset()
        return True

    def check_for_missing_dataset(self, expansion_code: str, dataset_location: str):
        """Check if a dataset exists for this event."""
        try:
            if not expansion_code:
                return
            if self.dataset_window.check_instance_open():
                return

            dataset_name = os.path.basename(dataset_location)
            self.configuration, _ = read_configuration()

            if self.configuration.card_data.latest_dataset != dataset_name:
                self.configuration.card_data.latest_dataset = dataset_name
                write_configuration(self.configuration)
            else:
                return

            if self.configuration.card_data.latest_dataset:
                return
            logger.info("No dataset found for expansion {self.expansions[expansion_code]}.")
            message_string = (
                f"No dataset found for the {self.expansions[expansion_code]} expansion.\n\n"
                "Downloading a dataset may take 1-2 minutes.\n\n"
                "Would you like to download the dataset now?\n\n"
                "Tip: To stop seeing this message, open the Settings menu and uncheck 'Enable Missing Dataset Notifications'."
            )
            if tkinter.messagebox.askyesno(
                title="Missing Dataset",
                message=message_string
            ):
                dataset_args = DatasetArgs(
                    draft_set=expansion_code,
                    draft=LIMITED_TYPE_STRING_DRAFT_PREMIER,
                    user_group=LIMITED_USER_GROUP_ALL,
                    start=START_DATE_DEFAULT,
                    end=str(date.today()),
                    game_count=0,
                    color_ratings=None
                )
                self.dataset_window.enter(dataset_args)
        except Exception as error:
            logger.error(error)

    def _check_dataset(self):
        """Check if a new version of the dataset is available."""
        if (
            self.configuration.settings.update_notifications_enabled and 
            self.configuration.card_data.latest_dataset
        ):
            self._update_dataset()
        elif self.configuration.settings.missing_notifications_enabled:
            file_list, _ = retrieve_local_set_list()
            if not file_list:
                if tkinter.messagebox.askyesno(
                    title="No Datasets Found",
                    message="No datasets detected. This application cannot function without them.\n\n"
                    "Would you like to download a dataset now?\n\n"
                    "Tip: To stop seeing this message, open the Settings menu and uncheck 'Enable Missing Dataset Notifications'."
                ):
                    self.dataset_window.enter()

    def _update_dataset(self):
        try:
            current_time = datetime.now().timestamp()
            time_difference = current_time - self.configuration.card_data.last_auto_check
            if time_difference < NOTIFICATION_DATASET_RATE_LIMIT_SEC:
                return
            self.configuration.card_data.last_auto_check = current_time
            write_configuration(self.configuration)

            dataset_info = read_dataset_info(self.configuration.card_data.latest_dataset)
            if not dataset_info:
                return
            logger.info(f"Checking dataset {self.configuration.card_data.latest_dataset} for updates")
            current_date = str(date.today())
            color_ratings, game_count = Seventeenlands().download_color_ratings(dataset_info[0], dataset_info[1], dataset_info[3], current_date, dataset_info[2])
            if game_count > dataset_info[5]:
                message_string = (
                    f"New data is available for the last dataset you downloaded: {dataset_info[0]} / {dataset_info[1]} / {dataset_info[2]} / {dataset_info[3]}.\n\n"
                    "Would you like to update the dataset?\n\n"
                    "Tip: This notification can be disabled by unchecking 'Enable Dataset Update Notifications' in the settings menu."
                )
                if tkinter.messagebox.askyesno(title="Dataset Update Available", message=message_string):
                    dataset_args = DatasetArgs(
                        draft_set=dataset_info[0],
                        draft=dataset_info[1],
                        user_group=dataset_info[2],
                        start=dataset_info[3],
                        end=current_date,
                        game_count=game_count,
                        color_ratings=color_ratings
                    )
                    self.dataset_window.enter(dataset_args)
        except Exception as error:
            logger.error(error)

    def _check_arena_log(self) -> bool:
        """Notify the user if the Arena log file is missing."""
        if self.configuration.settings.arena_log_location:
            logger.info("Arena Player Log Location: %s", self.configuration.settings.arena_log_location)
            return False
        else:
            logger.error("Arena Player Log Missing")
            tkinter.messagebox.showinfo(
                title="Arena Player Log Missing", message="Unable to locate the Arena player log.\n\n"
                "Please set the log location by clicking File->Read Player.log and selecting the Arena log file (Player.log).\n\n"
                "This log is typically located at the following location:\n"
                " - PC: <Drive>/Users/<User>/AppData/LocalLow/Wizards Of The Coast/MTGA\n"
                " - MAC: <User>/Library/Logs/Wizards Of The Coast/MTGA"
            )
            return True

    def _check_application(self) -> bool:
        """Update the UI if available."""
        try:
            if self._check_version():
                if sys.platform == PLATFORM_ID_WINDOWS:
                    if self._update_executable():
                        return True
                else:
                    message_string = f"Update {self.new_version} is now available.\n\nCheck https://github.com/unrealities/MTGA_Draft_17Lands/releases for more details."
                    tkinter.messagebox.showinfo(title="Update", message=message_string)
        except Exception as error:
            logger.error(error)
        return False

    def _update_executable(self) -> bool:
        """Update the executable if available."""
        message_string = f"Version {self.new_version} is now available. Would you like to upgrade?"
        message_box = tkinter.messagebox.askyesno(title="Update", message=message_string)
        if message_box:
            output_location = self.update.download_file(self.file_location)
            if output_location:
                self.root.destroy()
                win32api.ShellExecute(0, "open", output_location, None, None, 10)
                return True
            else:
                tkinter.messagebox.showerror(
                    title="Download Failed",
                    message="Visit https://github.com/unrealities/MTGA_Draft_17Lands/releases to manually download the new version."
                )
        return False
    def _check_version(self) -> bool:
        """Compare the application version and the latest version in the repository"""
        result = False
        file_version, self.file_location = self.update.retrieve_file_version()
        if file_version:
            file_version = int(file_version)
            client_version = round(float(APPLICATION_VERSION) * 100)
            if file_version > client_version:
                result = True

            self.new_version = round(float(file_version) / 100.0, 2)
        return result

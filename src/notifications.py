# -*- coding: utf-8 -*-
import sys
import os
import tkinter.messagebox
from datetime import datetime, date, timedelta
from src.configuration import Configuration
from src.app_update import AppUpdate
from src.logger import create_logger
from src.utils import retrieve_local_set_list, read_dataset_info
from src.configuration import write_configuration, read_configuration
from src.seventeenlands import Seventeenlands
from src.download_dataset import DownloadDatasetWindow, DatasetArgs
from src.constants import (
    PLATFORM_ID_WINDOWS,
    APPLICATION_VERSION,
    START_DATE_DEFAULT,
    LIMITED_TYPE_STRING_DRAFT_PREMIER,
    LIMITED_TYPE_STRING_DRAFT_QUICK,
    LIMITED_TYPE_STRING_DRAFT_BOT,
    LIMITED_USER_GROUP_ALL
)
try:
    import win32api
except ImportError:
    pass

logger = create_logger()

NOTIFICATION_DATASET_RATE_LIMIT_SEC = 86400 # 24 hours
NOTIFICATION_DATASET_MISSING_CHECK_LIST = [LIMITED_TYPE_STRING_DRAFT_QUICK, LIMITED_TYPE_STRING_DRAFT_BOT]

class Notifications:
    """Handles app notifications"""
    def __init__(self, root, expansions, configuration: Configuration, dataset_window: DownloadDatasetWindow):
        self.configuration = configuration
        self.root = root
        self.new_version = ""
        self.file_location = ""
        self.expansions = {v.set_code : k for k,v in expansions.data.items()} if expansions else None
        self.dataset_window = dataset_window
        self.update = AppUpdate()

    def check_for_updates(self) -> bool:
        """Entry point for the class"""
        if self.check_application():
            return False
        if self.check_arena_log():
            return True
        self.check_dataset()
        return True
    
    def check_and_pull_recent_sets(self):
        """
        Check if `last_auto_check` is 0 and `latest_dataset` is empty, then identify
        the most recent set created within the last two weeks from the `Sets` directory.

        If a recent set is found, update the `latest_dataset` in the configuration.
        """
        if (
            self.configuration.card_data.last_auto_check != 0 or 
            self.configuration.card_data.latest_dataset != ""
        ):
            return

        try:
            latest_file = self._find_latest_file()

            # Process the latest file if found
            if latest_file:
                logger.info(f"Recent set found: {latest_file}")
                self.configuration.card_data.latest_dataset = os.path.basename(latest_file[6])
                write_configuration(self.configuration)

        except Exception as error:
            logger.error(f"Failed to retrieve recent sets: {error}")

    def _find_latest_file(self):
        """
        Find the most recent file from the list of files based on the cutoff time.

        Args:
            file_list (list): List of files to check.
            check_cutoff (datetime): The cutoff time for filtering files.

        """
        latest_file = None
        latest_file_time = None

        # Get the current time and calculate the cutoff time
        check_cutoff = datetime.now() - timedelta(weeks=2)

        # Retrieve the list of local set files
        file_list, _ = retrieve_local_set_list()

        for file in file_list:
            try:
                # Parse the timestamp (2025-11-26 06:36:37.300875) into a datetime object
                file_mod_time = datetime.strptime(file[7], "%Y-%m-%d %H:%M:%S.%f")
                if file_mod_time >= check_cutoff:
                    # Update the latest file if this file is newer
                    if latest_file_time is None or file_mod_time > latest_file_time:
                        latest_file = file
                        latest_file_time = file_mod_time
            except ValueError as parse_error:
                logger.error(f"Error parsing timestamp for file {file}: {parse_error}")

        return latest_file

    def check_for_missing_dataset(self, expansion_code: str, event_type: str):
        """Check if a dataset exists for this event."""
        try:
            if (
                not expansion_code or
                not self.expansions or
                expansion_code not in self.expansions or
                event_type not in NOTIFICATION_DATASET_MISSING_CHECK_LIST or
                self.dataset_window.check_instance_open()
            ):
                return

            if self.configuration.card_data.latest_dataset:
                return
            logger.info(f"No dataset found for expansion {self.expansions[expansion_code]}.")
            message_string = (
                f"No dataset found for expansion {self.expansions[expansion_code]}.\n\n"
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

    def update_latest_dataset(self, dataset_location: str):
        """Update the latest dataset in the configuration."""
        dataset_name = os.path.basename(dataset_location)
        self.configuration, _ = read_configuration()

        if self.configuration.card_data.latest_dataset != dataset_name:
            self.configuration.card_data.latest_dataset = dataset_name
            write_configuration(self.configuration)
            return True
        else:
            return False

    def check_dataset(self):
        """Check if a new version of the dataset is available."""
        self.check_and_pull_recent_sets()
        if (
            self.configuration.settings.update_notifications_enabled and 
            self.configuration.card_data.latest_dataset
        ):
            self.update_dataset()
        elif self.configuration.settings.missing_notifications_enabled:
            file_list, _ = retrieve_local_set_list()
            if not file_list:
                if tkinter.messagebox.askyesno(
                    title="No Datasets Found",
                    message="No datasets detected.\n\n"
                    "Would you like to download a dataset now?\n\n"
                    "Tip: To stop seeing this message, open the Settings menu and uncheck 'Enable Missing Dataset Notifications'."
                ):
                    self.dataset_window.enter()

    def update_dataset(self):
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
            if (
                not self.expansions or
                dataset_info[0] not in self.expansions
            ):
                return
            if game_count > dataset_info[5]:
                message_string = (
                    f"New data available for {self.expansions[dataset_info[0]]}.\n\n"
                    "Would you like to update your dataset?\n\n"
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

    def check_arena_log(self) -> bool:
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

    def check_application(self) -> bool:
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

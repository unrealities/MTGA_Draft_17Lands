"""
main.py

Entry point for the MTGA Draft Tool.
Initializes configuration, scanner, and the main UI application.
"""

import sys
import argparse
import tkinter
import time  # Import time for UX pacing
from src.configuration import read_configuration
from src.limited_sets import LimitedSets
from src.log_scanner import ArenaScanner
from src.file_extractor import search_arena_log_locations, retrieve_arena_directory
from src.ui.app import DraftApp
from src.ui.windows.splash import SplashWindow
from src.ui.styles import Theme
from src.logger import create_logger

logger = create_logger()


def load_data(args, config, progress_callback):
    """
    Blocking function to load all necessary data.
    Returns a dictionary of initialized components.
    """
    # Step 1: Logs
    progress_callback("Locating Logs...")
    logger.info("load_data: Step 1 - Locating Logs")

    log_path = search_arena_log_locations(
        [args.file, config.settings.arena_log_location]
    )

    if log_path:
        config.settings.arena_log_location = log_path
        logger.info(f"Log found at: {log_path}")
    else:
        logger.warning("Player.log not found.")

    # Step 2: Data Directory
    progress_callback("Checking Data Directory...")
    logger.info("load_data: Step 2 - Locating Data Directory")

    if args.data:
        config.settings.database_location = args.data
    elif log_path:
        config.settings.database_location = retrieve_arena_directory(log_path)

    # Step 3: Sets
    progress_callback("Loading Sets (Checking 17Lands)...")
    logger.info("load_data: Step 3 - Retrieving Limited Sets (Network Call)")

    # This fetches data from 17Lands/Scryfall
    limited_sets = LimitedSets().retrieve_limited_sets()

    # Step 4: Scanner
    progress_callback("Initializing Scanner...")
    logger.info("load_data: Step 4 - Initializing ArenaScanner")

    scanner = ArenaScanner(
        filename=log_path,
        set_list=limited_sets,
        step_through=args.step,
        retrieve_unknown=True,
    )

    progress_callback("Launching...")
    logger.info("load_data: Complete")
    return {"scanner": scanner}


def main():
    logger.info("Application Startup")

    parser = argparse.ArgumentParser(description="MTGA Draft Tool")
    parser.add_argument("-f", "--file", help="Path to Player.log file")
    parser.add_argument("-d", "--data", help="Path to MTGA Data directory")
    parser.add_argument(
        "--step", action="store_true", help="Enable step-through debugging"
    )
    args, unknown = parser.parse_known_args()

    config, success = read_configuration()

    root = tkinter.Tk()

    current_theme = getattr(config.settings, "theme", "Dark")
    Theme.apply(root, current_theme)

    def on_loaded(data):
        logger.info("Initializing DraftApp UI")
        app = DraftApp(root, data["scanner"], config)

    splash = SplashWindow(
        root, task=lambda cb: load_data(args, config, cb), on_complete=on_loaded
    )

    logger.info("Entering Main Loop")
    root.mainloop()


if __name__ == "__main__":
    main()

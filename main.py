"""
main.py
MTGA Draft Tool - Entry Point.
Handles Robust Path Discovery and Splash Lifecycle.
"""

import ttkbootstrap as ttk
import argparse
import os
import logging
from src import constants
from src.configuration import read_configuration, write_configuration
from src.limited_sets import LimitedSets
from src.log_scanner import ArenaScanner
from src.file_extractor import search_arena_log_locations, retrieve_arena_directory
from src.ui.app import DraftApp
from src.ui.windows.splash import SplashWindow
from src.ui.styles import Theme

logger = logging.getLogger(__name__)


def load_data(args, config, progress_callback):
    """Background Task: Robustly locate logs and index current dataset."""

    # 1. ROBUST LOG SEARCH
    # We prioritize: 1. Manual Flag (-f), 2. System Default (Real Path), 3. Config Fallback
    progress_callback("Locating Arena Logs...")
    log_path = search_arena_log_locations(
        args.file,  # Manual override
        config.settings.arena_log_location,  # Stored fallback
    )

    if log_path:
        logger.info(f"Using log file: {log_path}")
        config.settings.arena_log_location = log_path
        # Persist the valid path immediately
        write_configuration(config)

    # 2. GAME FILE INDEXING
    progress_callback("Checking Game Files...")
    db_loc = args.data or (retrieve_arena_directory(log_path) if log_path else None)
    if db_loc:
        config.settings.database_location = db_loc

    # 3. METADATA REFRESH
    progress_callback("Checking 17Lands for New Sets...")
    limited_sets = LimitedSets().retrieve_limited_sets()

    # 4. SCANNER INITIALIZATION
    progress_callback("Initializing Scanner...")
    scanner = ArenaScanner(
        filename=log_path, set_list=limited_sets, retrieve_unknown=True
    )

    # 5. DATASET PRE-LOAD
    # Attempt to load the most recently used dataset so the app isn't empty on launch
    last_dataset = config.card_data.latest_dataset
    if last_dataset:
        progress_callback(f"Indexing {last_dataset.split('_')[0]}...")
        sources = scanner.retrieve_data_sources()
        for label, path in sources.items():
            if os.path.basename(path) == last_dataset:
                scanner.retrieve_set_data(path)
                break

    return {"scanner": scanner, "config": config}


def main():
    # CLI Argument Parsing
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--file", help="Path to Player.log")
    parser.add_argument("-d", "--data", help="Path to MTGA Data")
    args, _ = parser.parse_known_args()

    # Load Config
    config, _ = read_configuration()

    root = ttk.Window(themename="darkly")
    root.withdraw()

    # Initialize Styling Engine
    # We apply a baseline theme so the splash screen matches the app
    Theme.apply(
        root,
        engine=getattr(config.settings, "theme_base", "clam"),
        palette=getattr(config.settings, "theme", "Neutral"),
    )

    def on_ready(data, splash):
        """Handoff from splash thread to Main UI thread."""
        try:
            DraftApp(root, data["scanner"], data["config"], splash)
        except Exception as e:
            logger.error(f"Failed to launch DraftApp: {e}", exc_info=True)
            root.destroy()

    # Launch non-blocking Splash
    SplashWindow(
        root, task=lambda cb: load_data(args, config, cb), on_complete=on_ready
    )

    root.mainloop()


if __name__ == "__main__":
    main()

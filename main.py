"""
main.py
MTGA Draft Tool - Entry Point.
Handles Robust Path Discovery and Splash Lifecycle.
"""

import locale

# Intercept unsupported locale settings that cause ttkbootstrap to crash on certain Windows regions.
_original_setlocale = locale.setlocale


def _safe_setlocale(category, loc=None):
    try:
        return _original_setlocale(category, loc)
    except locale.Error:
        # Fallback to the safe 'C' standard locale if the system's regional setting is unsupported
        return _original_setlocale(category, "C")


locale.setlocale = _safe_setlocale

import ttkbootstrap as ttk
import argparse
import os
import sys
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
        write_configuration(config)

    # 3. METADATA REFRESH
    progress_callback("Checking 17Lands for New Sets...")
    limited_sets = LimitedSets().retrieve_limited_sets()

    # 4. SCANNER INITIALIZATION
    progress_callback("Initializing Scanner...")
    scanner = ArenaScanner(
        filename=log_path, set_list=limited_sets, retrieve_unknown=True
    )

    # 5. DRAFT DISCOVERY (Deep Scan)
    # We scan the logs while the splash is active to prevent the main UI from hanging.
    progress_callback("Searching for active draft...")
    if scanner.draft_start_search():
        # Identify the event
        e_set, e_type = scanner.retrieve_current_limited_event()
        progress_callback(f"Found {e_set} {e_type}...")

        # Auto-load the correct dataset for this draft
        sources = scanner.retrieve_data_sources()
        for label, path in sources.items():
            if f"[{e_set.upper()}]" in label.upper():
                scanner.retrieve_set_data(path)
                config.card_data.latest_dataset = os.path.basename(path)
                break

        # Deep-scan for the current pack/pick state
        scanner.draft_data_search()
        pk, pi = scanner.retrieve_current_pack_and_pick()
        if pk > 0:
            progress_callback(f"Loading {e_set} - Pack {pk} Pick {pi}...")
    else:
        # Fallback 1: Check if we successfully recovered a draft state from a previous session
        e_set, e_type = scanner.retrieve_current_limited_event()
        if e_set:
            progress_callback(f"Recovered Session: {e_set} {e_type}...")
            sources = scanner.retrieve_data_sources()
            for label, path in sources.items():
                if f"[{e_set.upper()}]" in label.upper():
                    scanner.retrieve_set_data(path)
                    config.card_data.latest_dataset = os.path.basename(path)
                    break

            # Deep-scan to catch up on any missed picks while the application was closed/restarting
            scanner.draft_data_search()
            pk, pi = scanner.retrieve_current_pack_and_pick()
            if pk > 0:
                progress_callback(f"Loading {e_set} - Pack {pk} Pick {pi}...")
        else:
            # Fallback 2: Look for the most recent log in Logs/ and load it automatically
            progress_callback("Checking for past drafts...")
            past_logs = []
            if os.path.exists(constants.DRAFT_LOG_FOLDER):
                for f in os.listdir(constants.DRAFT_LOG_FOLDER):
                    if f.startswith("DraftLog_") and f.endswith(".log"):
                        past_logs.append(os.path.join(constants.DRAFT_LOG_FOLDER, f))

            if past_logs:
                past_logs.sort(key=os.path.getmtime, reverse=True)
                most_recent_log = past_logs[0]
                progress_callback("Loading most recent draft...")

                scanner.set_arena_file(most_recent_log)
                if scanner.draft_start_search():
                    e_set, e_type = scanner.retrieve_current_limited_event()
                    sources = scanner.retrieve_data_sources()
                    for label, path in sources.items():
                        if f"[{e_set.upper()}]" in label.upper():
                            scanner.retrieve_set_data(path)
                            config.card_data.latest_dataset = os.path.basename(path)
                            break
                    scanner.draft_data_search()
            else:
                # Absolute fallback: load the most recently used dataset
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
    import time
    from src import constants

    # 30-day draft log cleanup
    if os.path.exists(constants.DRAFT_LOG_FOLDER):
        try:
            now = time.time()
            for f in os.listdir(constants.DRAFT_LOG_FOLDER):
                if f.startswith("DraftLog_") and f.endswith(".log"):
                    filepath = os.path.join(constants.DRAFT_LOG_FOLDER, f)
                    try:
                        # 30 days * 24h * 60m * 60s = 2592000 seconds
                        if now - os.path.getmtime(filepath) > 2592000:
                            os.remove(filepath)
                    except Exception:
                        pass
        except Exception as e:
            logger.error(f"Failed cleaning old draft logs: {e}")

    # CLI Argument Parsing
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--file", help="Path to Player.log")
    parser.add_argument("-d", "--data", help="Path to MTGA Data")
    args, _ = parser.parse_known_args()

    # Load Config
    config, _ = read_configuration()
    root = None

    def launch_ui(is_safe_mode=False):
        nonlocal root
        if is_safe_mode:
            logger.info("Attempting safe-mode UI launch with default theme.")
            config.settings.theme = "Neutral"
            config.settings.theme_base = "clam"
            config.settings.theme_custom_path = ""
            write_configuration(config)
            if root:
                try:
                    root.destroy()
                except Exception:
                    pass

        root = ttk.Window(themename="cyborg")
        root.withdraw()

        # Initialize Styling Engine
        # We apply a baseline theme so the splash screen matches the app
        Theme.apply(
            root,
            engine=getattr(config.settings, "theme_base", "clam"),
            palette=getattr(config.settings, "theme", "Neutral"),
        )

        def on_ready(data, splash):
            try:
                splash.close()
                app = DraftApp(root, data["scanner"], data["config"])

                # 1. Show the window skeleton immediately
                root.deiconify()

                # 2. Immediately trigger Phase 1 (Geometry & Data Sync)
                # We use a very short delay (10ms) to ensure the window is 'active'
                root.after(10, app._perform_boot_sync)

            except Exception as e:
                logger.error(f"Launch Error: {e}", exc_info=True)
                root.destroy()

        # Launch non-blocking Splash
        SplashWindow(
            root, task=lambda cb: load_data(args, config, cb), on_complete=on_ready
        )

    try:
        launch_ui(is_safe_mode=False)
    except Exception as e:
        logger.error(f"Fatal error during UI initialization: {e}", exc_info=True)
        # Guarantee the user is never permanently locked out due to a corrupted theme
        launch_ui(is_safe_mode=True)

    try:
        if root:
            root.mainloop()
    except KeyboardInterrupt:
        logger.info("Application stopped by user (KeyboardInterrupt).")
        if root:
            root.destroy()
        sys.exit(0)


if __name__ == "__main__":
    main()

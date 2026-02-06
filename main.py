"""
main.py

Entry point for the MTGA Draft Tool.
Initializes configuration, scanner, and the main UI application.
"""

import sys
import argparse
from src.configuration import read_configuration
from src.limited_sets import LimitedSets
from src.log_scanner import ArenaScanner
from src.file_extractor import search_arena_log_locations, retrieve_arena_directory
from src.ui.app import DraftApp
from src import constants


def main():
    # 1. Parse Arguments
    parser = argparse.ArgumentParser(description="MTGA Draft Tool")
    parser.add_argument("-f", "--file", help="Path to Player.log file")
    parser.add_argument("-d", "--data", help="Path to MTGA Data directory")
    parser.add_argument(
        "--step", action="store_true", help="Enable step-through debugging"
    )

    args, unknown = parser.parse_known_args()

    # 2. Load Configuration
    config, success = read_configuration()
    if not success:
        print("Warning: Failed to read configuration file. Using defaults.")

    # 3. Locate Arena Log
    # Order of precedence: CLI arg -> Config -> Auto-detect
    log_path = search_arena_log_locations(
        [args.file, config.settings.arena_log_location]
    )

    if log_path:
        config.settings.arena_log_location = log_path
    else:
        print("Warning: Player.log not found. Please locate it via the File menu.")

    # 4. Locate Data Directory
    if args.data:
        config.settings.database_location = args.data
    else:
        # Try to find data directory relative to log file
        config.settings.database_location = retrieve_arena_directory(log_path)

    # 5. Initialize Logic Components
    limited_sets = LimitedSets().retrieve_limited_sets()

    scanner = ArenaScanner(
        filename=log_path,
        set_list=limited_sets,
        step_through=args.step,
        retrieve_unknown=True,
    )

    # 6. Launch UI
    app = DraftApp(scanner, config)
    app.run()


if __name__ == "__main__":
    main()

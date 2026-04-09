import os
import json
import logging
import time
import traceback
from datetime import datetime, timezone

from server import config
from server.utils import APIClient
from server.extract import (
    extract_scryfall_data,
    extract_scryfall_tags,
    extract_17lands_data,
    extract_color_ratings,
    get_historical_start_dates,
)
from server.transform import transform_payload
from server.load import save_dataset, save_manifest, save_report, deploy_web_assets
from server.report import PipelineReport

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_scheduled_events(calendar_path="server/calendar.json") -> dict:
    logger.info(f"Loading scheduled events from {calendar_path}...")
    if not os.path.exists(calendar_path):
        logger.error(f"'{calendar_path}' not found! Cannot determine active events.")
        return {}

    try:
        with open(calendar_path, "r", encoding="utf-8") as f:
            calendar = json.load(f)
    except Exception as e:
        logger.error(f"Failed to parse {calendar_path}: {e}")
        return {}

    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    active_sets = {}

    for event in calendar.get("events", []):
        start = event.get("start_date")
        end = event.get("end_date")

        if start and end and (start <= today_str <= end):
            set_code = event["set_code"]
            if set_code not in active_sets:
                active_sets[set_code] = {"formats": set(), "start_date": start}
            active_sets[set_code]["formats"].update(event["formats"])

            if start < active_sets[set_code]["start_date"]:
                active_sets[set_code]["start_date"] = start

    for data in active_sets.values():
        data["formats"] = list(data["formats"])

    return active_sets


def load_existing_manifest() -> dict:
    filepath = os.path.join(config.OUTPUT_DIR, "manifest.json")
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load existing manifest, starting fresh: {e}")
    return {"datasets": {}}


def run_pipeline():
    logger.info("Starting Daily Calendar-Driven ETL Pipeline...")
    client = APIClient()

    report = PipelineReport()
    report.attach_log_handler()

    active_sets = get_scheduled_events("server/calendar.json")
    report.record_intent(active_sets, config.ARCHETYPES)

    if not active_sets:
        logger.warning("No active events found in the calendar for today. Exiting.")
        final_report = report.finalize(client)
        save_report(final_report)
        report.log_summary(final_report)
        return

    manifest = load_existing_manifest()
    manifest["updated_at"] = datetime.now(timezone.utc).isoformat()
    if "datasets" not in manifest:
        manifest["datasets"] = {}

    manifest["active_sets"] = list(active_sets.keys())

    end_date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    historical_dates = get_historical_start_dates(client)

    jobs = []
    for set_code, data in active_sets.items():
        if "CUBE" in set_code.upper():
            true_start_date_str = data["start_date"]
        else:
            if set_code in historical_dates:
                true_start_date_str = historical_dates[set_code].split("T")[0]
            else:
                true_start_date_str = data["start_date"]

        for draft_format in data["formats"]:
            for user_group in ["All", "Top"]:
                jobs.append((set_code, draft_format, user_group, true_start_date_str))

    scryfall_cache_mem = {}
    tags_cache_mem = {}

    for set_code, draft_format, user_group, start_date_str in jobs:
        logger.info(f"==== Processing {set_code} | {draft_format} | {user_group} ====")

        try:
            if set_code not in scryfall_cache_mem:
                scryfall_cache_mem[set_code] = extract_scryfall_data(client, set_code)
                tags_cache_mem[set_code] = extract_scryfall_tags(client, set_code)

            scryfall_cards = scryfall_cache_mem[set_code]
            card_tags = tags_cache_mem[set_code]

            if not scryfall_cards:
                logger.info(
                    f"   No Scryfall base cards found for {set_code}. Will rely on 17Lands card names."
                )

            color_ratings, games_played, total_games = extract_color_ratings(
                client, set_code, draft_format, user_group, start_date_str, end_date_str
            )

            valid_archetypes = ["All Decks"]
            skipped_count = 0
            for arch in config.ARCHETYPES:
                if arch == "All Decks":
                    continue

                # Verify using the blank mapping string
                games_played_key = "" if arch == "All Decks" else arch
                if games_played.get(games_played_key, 0) >= config.MIN_GAMES_THRESHOLD:
                    valid_archetypes.append(arch)
                else:
                    skipped_count += 1

            if skipped_count > 0:
                logger.info(
                    f"   Filtered out {skipped_count} archetypes ( < {config.MIN_GAMES_THRESHOLD} games)."
                )

            seventeenlands_data = extract_17lands_data(
                client,
                set_code,
                draft_format,
                valid_archetypes,
                user_group,
                start_date_str,
                end_date_str,
            )

            if not seventeenlands_data.get("All Decks"):
                logger.warning(
                    f"No baseline data for {set_code} {draft_format} ({user_group})."
                )
                continue

            missing_names = []
            for name in seventeenlands_data["All Decks"].keys():
                if name not in scryfall_cards:
                    missing_names.append(name)

            if missing_names:
                from server.extract import extract_scryfall_by_names

                logger.info(
                    f"   [Scryfall] Fetching {len(missing_names)} bonus sheet cards..."
                )
                bonus_cards = extract_scryfall_by_names(client, missing_names)
                scryfall_cards.update(bonus_cards)

            final_dataset = transform_payload(
                set_code,
                draft_format,
                scryfall_cards,
                seventeenlands_data,
                card_tags,
                color_ratings,
                start_date_str,
                end_date_str,
                total_games,
            )

            file_info = save_dataset(set_code, draft_format, user_group, final_dataset)

            manifest_key = f"{set_code}_{draft_format}_{user_group}"
            manifest["datasets"][manifest_key] = file_info

            card_count = len(final_dataset.get("card_ratings", {}))

            report.record_dataset(
                set_code,
                draft_format,
                user_group,
                file_info,
                card_count,
                start_date_str,
                end_date_str,
                total_games,
            )

            # Give the 17Lands/Cloudflare servers a short breather between major datasets
            time.sleep(15.0)

        except Exception as e:
            logger.error(
                f"Failed processing {set_code} {draft_format} ({user_group}): {e}"
            )
            logger.debug(traceback.format_exc())
            report.record_skipped(set_code, draft_format, f"Processing failed: {e}")

    try:
        save_manifest(manifest)
        report.record_warehouse_state(manifest)
    except Exception as e:
        logger.error(f"Critical failure saving manifest: {e}")

    logger.info("Pipeline Complete!")

    deploy_web_assets()
    report.log_summary(final_report)


if __name__ == "__main__":
    run_pipeline()

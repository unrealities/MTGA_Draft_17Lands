import os
import json
import logging
import traceback
from datetime import datetime, timezone

from server import config
from server.utils import APIClient
from server.extract import (
    extract_scryfall_data,
    extract_scryfall_tags,
    extract_17lands_data,
    extract_color_ratings,
)
from server.transform import transform_payload
from server.load import save_dataset, save_manifest, save_report
from server.report import PipelineReport

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_scheduled_events(calendar_path="calendar.json") -> dict:
    """
    Reads the manual calendar JSON and returns a dictionary of active events for TODAY.
    Format: { "TMNT": ["PremierDraft", "TradDraft"], "BLB": ["PremierDraft"] }
    """
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

        # Check if today falls within the active window
        if start and end and (start <= today_str <= end):
            set_code = event["set_code"]
            formats = event["formats"]

            if set_code not in active_sets:
                active_sets[set_code] = set()

            active_sets[set_code].update(formats)

    # Convert sets back to lists
    return {k: list(v) for k, v in active_sets.items()}


def load_existing_manifest() -> dict:
    """
    Loads the existing manifest so we don't delete historical/inactive formats
    when saving today's active formats.
    """
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

    # 1. Determine exactly what needs to be fetched today
    active_sets = get_scheduled_events("calendar.json")
    report.record_intent(active_sets, config.ARCHETYPES)

    if not active_sets:
        logger.warning("No active events found in the calendar for today. Exiting.")
        final_report = report.finalize(client)
        save_report(final_report)
        report.log_summary(final_report)
        return

    # 2. Load historical manifest to preserve older dataset entries
    manifest = load_existing_manifest()
    manifest["updated_at"] = datetime.now(timezone.utc).isoformat()
    if "datasets" not in manifest:
        manifest["datasets"] = {}

    # 3. Process the active scheduled sets
    for set_code, formats in active_sets.items():
        logger.info(f"==== PROCESSING SCHEDULED SET: {set_code} ====")

        try:
            scryfall_cards = extract_scryfall_data(client, set_code)
            if not scryfall_cards and set_code != "CUBE":
                logger.info(f"No Scryfall base cards found for {set_code}. Skipping.")
                report.record_skipped(set_code, None, "No Scryfall base cards found")
                continue

            card_tags = extract_scryfall_tags(client, set_code)

            for draft_format in formats:
                try:
                    logger.info(f"Processing Format: {draft_format}...")

                    seventeenlands_data = extract_17lands_data(
                        client, set_code, draft_format
                    )
                    if not seventeenlands_data.get("All Decks"):
                        logger.warning(
                            f"No baseline 17Lands data for {set_code} {draft_format}. Skipping format."
                        )
                        report.record_skipped(
                            set_code, draft_format, "No baseline 17Lands data yet"
                        )
                        continue

                    color_ratings = extract_color_ratings(
                        client, set_code, draft_format
                    )

                    final_dataset = transform_payload(
                        set_code,
                        draft_format,
                        scryfall_cards,
                        seventeenlands_data,
                        card_tags,
                        color_ratings,
                    )

                    # Save dataset to disk
                    file_info = save_dataset(set_code, draft_format, final_dataset)

                    # 4. Safely update the manifest with today's run, leaving historical intact
                    manifest_key = f"{set_code}_{draft_format}"
                    manifest["datasets"][manifest_key] = file_info

                    card_count = len(final_dataset.get("card_ratings", {}))
                    report.record_dataset(set_code, draft_format, file_info, card_count)

                except Exception as e:
                    logger.error(
                        f"Failed processing format {draft_format} for {set_code}: {e}"
                    )
                    logger.debug(traceback.format_exc())
                    report.record_skipped(
                        set_code, draft_format, f"Format processing failed: {e}"
                    )
                    # Continue to next format instead of crashing pipeline

        except Exception as e:
            logger.error(f"Failed processing set {set_code}: {e}")
            logger.debug(traceback.format_exc())
            report.record_skipped(set_code, None, f"Set processing failed: {e}")
            # Continue to next set instead of crashing pipeline

    # 5. Save the combined manifest
    try:
        save_manifest(manifest)
        report.record_warehouse_state(manifest)
    except Exception as e:
        logger.error(f"Critical failure saving manifest: {e}")

    logger.info("Pipeline Complete!")

    final_report = report.finalize(client)
    save_report(final_report)
    report.log_summary(final_report)


if __name__ == "__main__":
    run_pipeline()

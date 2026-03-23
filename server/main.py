import logging
import traceback
from datetime import datetime, timezone

from server.utils import APIClient
from server.extract import (
    extract_active_events,
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


def run_pipeline():
    logger.info("Starting Daily Exhaustive ETL Pipeline...")
    client = APIClient()

    report = PipelineReport()
    report.attach_log_handler()

    try:
        active_sets = extract_active_events(client)
    except Exception as e:
        logger.error(f"Critical failure fetching active events: {e}")
        
        final_report = report.finalize(client)
        save_report(final_report)
        report.log_summary(final_report)
        
        return  # Cannot proceed without knowing what events to process

    manifest = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "datasets": {},
    }

    for set_code, formats in active_sets.items():
        logger.info(f"==== PROCESSING SET: {set_code} ====")

        try:
            scryfall_cards = extract_scryfall_data(client, set_code)
            if not scryfall_cards:
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
                        report.record_skipped(set_code, draft_format, "No baseline 17Lands data")
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

                    file_info = save_dataset(set_code, draft_format, final_dataset)
                    manifest["datasets"][f"{set_code}_{draft_format}"] = file_info
                    
                    card_count = len(final_dataset.get("card_ratings", {}))
                    report.record_dataset(set_code, draft_format, file_info, card_count)

                except Exception as e:
                    logger.error(
                        f"Failed processing format {draft_format} for {set_code}: {e}"
                    )
                    logger.debug(traceback.format_exc())
                    report.record_skipped(set_code, draft_format, f"Format processing failed: {e}")
                    # Continue to next format instead of crashing pipeline

        except Exception as e:
            logger.error(f"Failed processing set {set_code}: {e}")
            logger.debug(traceback.format_exc())
            report.record_skipped(set_code, None, f"Set processing failed: {e}")
            # Continue to next set instead of crashing pipeline

    try:
        save_manifest(manifest)
    except Exception as e:
        logger.error(f"Critical failure saving manifest: {e}")

    logger.info("Pipeline Complete!")

    final_report = report.finalize(client)
    save_report(final_report)
    report.log_summary(final_report)


if __name__ == "__main__":
    run_pipeline()

"""
server/report.py

Collects and persists a highly structured, professional run-report
for each ETL pipeline execution.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)


class _ReportLogHandler(logging.Handler):
    """Passively captures WARNING and ERROR log records across the pipeline."""

    def __init__(self, report: "PipelineReport"):
        super().__init__(level=logging.WARNING)
        self._report = report

    def emit(self, record: logging.LogRecord):
        entry = {
            "time": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": self.format(record),
        }
        if record.levelno >= logging.ERROR:
            self._report._errors.append(entry)
        else:
            self._report._warnings.append(entry)


class PipelineReport:
    def __init__(self):
        self._started_at: datetime = datetime.now(timezone.utc)
        self._completed_at: Optional[datetime] = None

        self._intended_schedule: dict = {}
        self._intended_archetypes: list = []
        self._intended_user_types: list = ["All", "Top"]
        self._datasets: List[Dict] = []
        self._skipped: List[Dict] = []
        self._errors: List[Dict] = []
        self._warnings: List[Dict] = []
        self._warehouse_datasets: dict = {}

        self._handler: Optional[_ReportLogHandler] = None

    # ------------------------------------------------------------------
    # Setup & Logging Hooks
    # ------------------------------------------------------------------

    def attach_log_handler(self):
        self._handler = _ReportLogHandler(self)
        self._handler.setFormatter(logging.Formatter("%(message)s"))
        logging.getLogger().addHandler(self._handler)

    def detach_log_handler(self):
        if self._handler:
            logging.getLogger().removeHandler(self._handler)
            self._handler = None

    # ------------------------------------------------------------------
    # Data Collection Methods
    # ------------------------------------------------------------------

    def record_intent(self, active_sets: dict, archetypes: list):
        """Records what the pipeline is scheduled to process."""
        self._intended_schedule = active_sets
        self._intended_archetypes = archetypes

    def record_dataset(
        self,
        set_code: str,
        draft_format: str,
        file_info: dict,
        card_count: int,
        start_date: str,
        end_date: str,
        game_count: int,
    ):
        """Records a successfully updated dataset."""
        self._datasets.append(
            {
                "set": set_code,
                "format": draft_format,
                "filename": file_info["filename"],
                "size_kb": file_info["size_kb"],
                "card_count": card_count,
                "start_date": start_date,
                "end_date": end_date,
                "game_count": game_count,
                "status": "success",
            }
        )

    def record_skipped(self, set_code: str, draft_format: Optional[str], reason: str):
        """Records a dataset that was intentionally skipped or failed gracefully."""
        self._skipped.append(
            {
                "set": set_code,
                "format": draft_format,
                "reason": reason,
            }
        )

    def record_warehouse_state(self, manifest: dict):
        """Records the final state of the manifest (all available historical data)."""
        self._warehouse_datasets = manifest.get("datasets", {})

    # ------------------------------------------------------------------
    # Finalization & Output
    # ------------------------------------------------------------------

    def finalize(self, api_client=None) -> dict:
        self._completed_at = datetime.now(timezone.utc)
        self.detach_log_handler()

        duration_sec = round((self._completed_at - self._started_at).total_seconds(), 1)
        error_count = len(self._errors)
        skipped_count = len(self._skipped)

        if error_count == 0 and skipped_count == 0:
            status = "SUCCESS"
        elif len(self._datasets) == 0:
            status = "FAILED"
        else:
            status = "PARTIAL_SUCCESS"

        api_stats = {}
        if api_client:
            api_stats = {
                "total_requests": getattr(api_client, "request_count", 0),
                "failed_requests": getattr(api_client, "failed_request_count", 0),
                "cached_requests": getattr(api_client, "cached_request_count", 0),
            }

        return {
            "pipeline_run": {
                "started_at": self._started_at.isoformat(),
                "completed_at": self._completed_at.isoformat(),
                "duration_sec": duration_sec,
                "status": status,
            },
            "api_stats": api_stats,
            "intent": {
                "scheduled_events": self._intended_schedule,
                "archetypes_targeted": self._intended_archetypes,
                "user_types_targeted": self._intended_user_types,
            },
            "execution_summary": {
                "formats_updated": len(self._datasets),
                "formats_skipped": skipped_count,
                "total_output_kb": sum(d["size_kb"] for d in self._datasets),
                "total_cards_rated": sum(d["card_count"] for d in self._datasets),
                "total_errors": error_count,
                "total_warnings": len(self._warnings),
            },
            "warehouse_state": {
                "total_available_datasets": len(self._warehouse_datasets),
                "available_keys": list(self._warehouse_datasets.keys()),
            },
            "datasets_updated": self._datasets,
            "datasets_skipped": self._skipped,
            "errors": self._errors,
            "warnings": self._warnings,
        }

    def log_summary(self, report: dict):
        """Prints a highly professional, formatted summary to the pipeline log."""
        r = report["pipeline_run"]
        api = report.get("api_stats", {})
        intent = report["intent"]
        exec_sum = report["execution_summary"]
        wh_state = report["warehouse_state"]

        logger.info("")
        logger.info(
            "======================================================================"
        )
        logger.info("                  ETL PIPELINE EXECUTION REPORT")
        logger.info(
            "======================================================================"
        )
        logger.info(f" STATUS       : {r['status']}")
        logger.info(f" START TIME   : {r['started_at']}")
        logger.info(f" DURATION     : {r['duration_sec']} seconds")
        logger.info(
            f" API REQUESTS : {api.get('total_requests', 0)} made "
            f"({api.get('failed_requests', 0)} failed, {api.get('cached_requests', 0)} cached)"
        )
        logger.info(
            "----------------------------------------------------------------------"
        )
        logger.info(" [1] PIPELINE INTENT (CALENDAR SCOPE)")
        logger.info(
            "----------------------------------------------------------------------"
        )

        if not intent["scheduled_events"]:
            logger.info("   No active events scheduled for today.")
        else:
            for set_code, event_data in intent["scheduled_events"].items():
                logger.info(
                    f"   Target Set : {set_code:<6} -> {', '.join(event_data['formats'])}"
                )
        logger.info(
            f"   Archetypes : {len(intent['archetypes_targeted'])} configured (e.g. {', '.join(intent['archetypes_targeted'][:5])}...)"
        )
        logger.info(f"   User Types : {', '.join(intent['user_types_targeted'])}")

        logger.info(
            "----------------------------------------------------------------------"
        )
        logger.info(" [2] EXECUTION RESULTS")
        logger.info(
            "----------------------------------------------------------------------"
        )
        logger.info(f"   Updates    : {exec_sum['formats_updated']} formats updated.")
        logger.info(
            f"   Output     : {exec_sum['total_output_kb']} KB across {exec_sum['total_cards_rated']} total cards."
        )
        logger.info(
            f"   Issues     : {exec_sum['formats_skipped']} skipped | {exec_sum['total_errors']} errors | {exec_sum['total_warnings']} warnings."
        )

        if report["datasets_updated"]:
            logger.info("\n   UPDATED DATASETS:")
            for d in report["datasets_updated"]:
                logger.info(
                    f"     ✓ {d['set']:<5} - {d['format']:<18} "
                    f"({d['card_count']:>3} cards | Games: {d['game_count']:>6} | "
                    f"Dates: {d['start_date']} to {d['end_date']} | {d['size_kb']:>4} KB)"
                )

        if report["datasets_skipped"]:
            logger.info("\n   SKIPPED DATASETS:")
            for s in report["datasets_skipped"]:
                fmt = s.get("format") or "Entire Set"
                logger.info(
                    f"     ✗ {s['set']:<5} - {fmt:<18} ( Reason: {s['reason']} )"
                )

        logger.info(
            "----------------------------------------------------------------------"
        )
        logger.info(" [3] WAREHOUSE STATE (MANIFEST STATE)")
        logger.info(
            "----------------------------------------------------------------------"
        )
        logger.info(f"   Total Hosted Datasets: {wh_state['total_available_datasets']}")

        # Group warehouse data by Set for clean logging
        wh_sets = {}
        for key in wh_state["available_keys"]:
            set_code, _, fmt = key.partition("_")
            if set_code not in wh_sets:
                wh_sets[set_code] = []
            if fmt:
                wh_sets[set_code].append(fmt)

        if wh_sets:
            logger.info("   Currently Serving:")
            for set_code, formats in sorted(wh_sets.items()):
                logger.info(f"     • {set_code:<5}: {', '.join(formats)}")
        else:
            logger.info("   Warehouse is currently empty.")

        logger.info(
            "======================================================================"
        )
        logger.info("")

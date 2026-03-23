"""
server/report.py

Collects and persists a structured run-report for each ETL pipeline execution.

Usage (in main.py):
    report = PipelineReport()
    report.attach_log_handler()   # Auto-captures all WARNING/ERROR log records
    ...
    report.record_dataset(set_code, draft_format, file_info, card_count)
    report.record_skipped(set_code, draft_format, reason)
    ...
    report.finalize(api_client)
    save_report(report)
"""

import json
import logging
import os
import time
from datetime import datetime, timezone
from server import config

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Log handler — passively captures WARNING+ records from the whole pipeline
# ---------------------------------------------------------------------------

class _ReportLogHandler(logging.Handler):
    """Appends WARNING and ERROR records to the report's internal lists."""

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


# ---------------------------------------------------------------------------
# Main report class
# ---------------------------------------------------------------------------

class PipelineReport:
    def __init__(self):
        self._started_at: datetime = datetime.now(timezone.utc)
        self._completed_at: datetime | None = None
        self._datasets: list[dict] = []
        self._skipped: list[dict] = []
        self._errors: list[dict] = []
        self._warnings: list[dict] = []
        self._handler: _ReportLogHandler | None = None

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def attach_log_handler(self):
        """
        Installs a handler on the root logger so all WARNING/ERROR messages
        emitted anywhere in the pipeline are automatically captured.
        """
        self._handler = _ReportLogHandler(self)
        self._handler.setFormatter(logging.Formatter("%(message)s"))
        logging.getLogger().addHandler(self._handler)

    def detach_log_handler(self):
        if self._handler:
            logging.getLogger().removeHandler(self._handler)
            self._handler = None

    # ------------------------------------------------------------------
    # Explicit data collection hooks
    # ------------------------------------------------------------------

    def record_dataset(
        self,
        set_code: str,
        draft_format: str,
        file_info: dict,
        card_count: int,
    ):
        """Call after a dataset file is successfully written."""
        self._datasets.append(
            {
                "set": set_code,
                "format": draft_format,
                "filename": file_info["filename"],
                "size_kb": file_info["size_kb"],
                "hash": file_info["hash"],
                "card_count": card_count,
                "status": "success",
            }
        )

    def record_skipped(self, set_code: str, draft_format: str | None, reason: str):
        """Call whenever a set or format is skipped without generating a file."""
        self._skipped.append(
            {
                "set": set_code,
                "format": draft_format,
                "reason": reason,
            }
        )

    # ------------------------------------------------------------------
    # Finalization
    # ------------------------------------------------------------------

    def finalize(self, api_client=None) -> dict:
        """
        Locks in the completion timestamp and builds the final report dict.
        Optionally accepts the APIClient to pull request counters.
        """
        self._completed_at = datetime.now(timezone.utc)
        self.detach_log_handler()

        duration_sec = round(
            (self._completed_at - self._started_at).total_seconds(), 1
        )

        error_count = len(self._errors)
        warning_count = len(self._warnings)
        skipped_count = len(self._skipped)

        if error_count == 0 and skipped_count == 0:
            status = "success"
        elif len(self._datasets) == 0:
            status = "failed"
        else:
            status = "partial"

        api_stats = {}
        if api_client and hasattr(api_client, "request_count"):
            api_stats = {
                "total_requests": api_client.request_count,
                "failed_requests": api_client.failed_request_count,
            }

        total_output_kb = sum(d["size_kb"] for d in self._datasets)
        total_cards = sum(d["card_count"] for d in self._datasets)

        # Deduplicate sets/formats counts
        sets_processed = len({d["set"] for d in self._datasets})
        formats_processed = len(self._datasets)

        report = {
            "pipeline_run": {
                "started_at": self._started_at.isoformat(),
                "completed_at": self._completed_at.isoformat(),
                "duration_sec": duration_sec,
                "status": status,
            },
            "api_stats": api_stats,
            "summary": {
                "sets_processed": sets_processed,
                "formats_processed": formats_processed,
                "formats_skipped": skipped_count,
                "files_generated": len(self._datasets),
                "total_output_kb": total_output_kb,
                "total_cards_rated": total_cards,
                "total_errors": error_count,
                "total_warnings": warning_count,
            },
            "datasets": self._datasets,
            "skipped": self._skipped,
            "errors": self._errors,
            "warnings": self._warnings,
        }
        return report

    def log_summary(self, report: dict):
        """Prints a human-readable summary to the pipeline log."""
        run = report["pipeline_run"]
        s = report["summary"]
        logger.info("=" * 60)
        logger.info(f"  PIPELINE REPORT — {run['status'].upper()}")
        logger.info("=" * 60)
        logger.info(f"  Duration        : {run['duration_sec']}s")
        logger.info(f"  Sets processed  : {s['sets_processed']}")
        logger.info(f"  Formats done    : {s['formats_processed']}")
        logger.info(f"  Formats skipped : {s['formats_skipped']}")
        logger.info(f"  Files generated : {s['files_generated']}")
        logger.info(f"  Total output    : {s['total_output_kb']} KB")
        logger.info(f"  Cards rated     : {s['total_cards_rated']}")

        if report.get("api_stats"):
            api = report["api_stats"]
            logger.info(
                f"  API requests    : {api['total_requests']} "
                f"({api['failed_requests']} failed)"
            )

        logger.info(f"  Errors          : {s['total_errors']}")
        logger.info(f"  Warnings        : {s['total_warnings']}")

        for d in report["datasets"]:
            logger.info(
                f"    ✓ {d['set']} {d['format']:20s} "
                f"{d['card_count']:4d} cards  {d['size_kb']:5d} KB"
            )
        for sk in report["skipped"]:
            fmt = sk.get("format") or "—"
            logger.info(f"    ✗ {sk['set']} {fmt:20s} SKIPPED — {sk['reason']}")

        logger.info("=" * 60)

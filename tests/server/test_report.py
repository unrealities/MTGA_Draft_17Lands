import pytest
import logging
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from server.report import PipelineReport, _ReportLogHandler


def test_pipeline_report_initialization():
    report = PipelineReport()
    assert report._started_at is not None
    assert report._completed_at is None
    assert isinstance(report._datasets, list)


def test_log_handler_capture():
    report = PipelineReport()
    report.attach_log_handler()

    test_logger = logging.getLogger("test_report_logger")
    test_logger.warning("Test warning message")
    test_logger.error("Test error message")

    report.detach_log_handler()

    assert len(report._warnings) == 1
    assert "Test warning message" in report._warnings[0]["message"]

    assert len(report._errors) == 1
    assert "Test error message" in report._errors[0]["message"]


def test_record_intent():
    report = PipelineReport()
    report.record_intent({"M10": {"formats": ["PremierDraft"]}}, ["All Decks", "UB"])
    assert report._intended_schedule == {"M10": {"formats": ["PremierDraft"]}}
    assert report._intended_archetypes == ["All Decks", "UB"]


def test_record_dataset():
    report = PipelineReport()
    report.record_dataset(
        "M10",
        "PremierDraft",
        "All",
        {"filename": "M10_PremierDraft_All.json.gz", "size_kb": 1024},
        250,
        "2020-01-01",
        "2020-02-01",
        10000,
    )
    assert len(report._datasets) == 1
    assert report._datasets[0]["set"] == "M10"
    assert report._datasets[0]["size_kb"] == 1024


def test_record_skipped():
    report = PipelineReport()
    report.record_skipped("M10", "PremierDraft", "Not enough data")
    assert len(report._skipped) == 1
    assert report._skipped[0]["reason"] == "Not enough data"


def test_record_warehouse_state():
    report = PipelineReport()
    report.record_warehouse_state({"datasets": {"key1": {}}})
    assert "key1" in report._warehouse_datasets


def test_finalize_success():
    report = PipelineReport()
    report.record_dataset(
        "M10",
        "PremierDraft",
        "All",
        {"filename": "M10_PremierDraft_All.json.gz", "size_kb": 1024},
        250,
        "2020-01-01",
        "2020-02-01",
        10000,
    )
    final = report.finalize()
    assert final["pipeline_run"]["status"] == "SUCCESS"


def test_finalize_failed():
    report = PipelineReport()
    final = report.finalize()
    assert final["pipeline_run"]["status"] == "FAILED"


def test_finalize_partial_success():
    report = PipelineReport()
    report.record_dataset(
        "M10",
        "PremierDraft",
        "All",
        {"filename": "M10_PremierDraft_All.json.gz", "size_kb": 1024},
        250,
        "2020-01-01",
        "2020-02-01",
        10000,
    )
    report._errors.append({"message": "Something went wrong"})
    final = report.finalize()
    assert final["pipeline_run"]["status"] == "PARTIAL_SUCCESS"


def test_log_summary():
    report = PipelineReport()
    report.record_intent({"M10": {"formats": ["PremierDraft"]}}, ["All Decks", "UB"])
    report.record_dataset(
        "M10",
        "PremierDraft",
        "All",
        {"filename": "M10_PremierDraft_All.json.gz", "size_kb": 1024},
        250,
        "2020-01-01",
        "2020-02-01",
        10000,
    )
    report.record_skipped("M10", "QuickDraft", "No data")
    report.record_warehouse_state({"datasets": {"M10_PremierDraft_All": {}}})

    final = report.finalize()

    with patch("server.report.logger.info") as mock_info:
        report.log_summary(final)
        assert mock_info.call_count > 0

import hashlib
import json
from unittest.mock import patch

import pytest
from server.main import load_existing_manifest, run_pipeline


@pytest.fixture
def warehouse(tmp_path, monkeypatch):
    monkeypatch.setattr("server.config.OUTPUT_DIR", str(tmp_path))
    monkeypatch.delenv("ETL_ALLOW_INITIALIZE", raising=False)
    return tmp_path


def test_missing_manifest_requires_explicit_initialization(warehouse, monkeypatch):
    with pytest.raises(FileNotFoundError):
        load_existing_manifest()
    monkeypatch.setenv("ETL_ALLOW_INITIALIZE", "1")
    assert load_existing_manifest() == {"datasets": {}}


@pytest.mark.parametrize("content", ["invalid json", "[]", '{"datasets": []}', '{}'])
def test_corrupt_manifest_is_never_treated_as_initialization(warehouse, monkeypatch, content):
    (warehouse / "manifest.json").write_text(content)
    monkeypatch.setenv("ETL_ALLOW_INITIALIZE", "1")
    with pytest.raises(ValueError):
        load_existing_manifest()


def test_restore_requires_all_referenced_historical_files(warehouse):
    key = "MH3_PremierDraft_All"
    filename = key + "_Data.json.gz"
    manifest = {"datasets": {key: {"filename": filename, "hash": hashlib.sha256(b"historical").hexdigest()}}}
    (warehouse / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(FileNotFoundError, match="Missing historical dataset"):
        load_existing_manifest()
    (warehouse / filename).write_bytes(b"historical")
    assert load_existing_manifest() == manifest


@patch("server.main.save_report")
@patch("server.main.deploy_web_assets")
@patch("server.main.save_calendar")
@patch("server.main.fetch_event_calendar")
def test_restore_failure_stops_pipeline_before_mutating_warehouse(fetch, calendar, assets, report, warehouse):
    with pytest.raises(FileNotFoundError):
        run_pipeline()
    fetch.assert_not_called()
    calendar.assert_not_called()
    assets.assert_not_called()
    report.assert_called_once()


@patch("server.main.save_manifest", side_effect=OSError("Manifest is locked"))
@patch("server.main.load_existing_manifest", return_value={"datasets": {}})
@patch("server.main.fetch_event_calendar")
@patch("server.main.get_scheduled_events", return_value={"MH3": {"formats": [], "start_date": "2026-01-01"}})
@patch("server.main.get_historical_start_dates", return_value={})
@patch("server.main.save_calendar")
@patch("server.main.deploy_web_assets")
def test_manifest_save_failure_propagates_to_workflow(assets, calendar, dates, events, fetch, restore, save, warehouse):
    with pytest.raises(OSError, match="Manifest is locked"):
        run_pipeline()

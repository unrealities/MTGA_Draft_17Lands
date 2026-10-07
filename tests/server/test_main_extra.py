import pytest
import json
from unittest.mock import patch, MagicMock
from server.main import run_pipeline


@pytest.fixture(autouse=True)
def isolated_warehouse(tmp_path, monkeypatch):
    monkeypatch.setattr("server.config.OUTPUT_DIR", str(tmp_path))
    monkeypatch.setenv("ETL_ALLOW_INITIALIZE", "1")


@patch("server.main.get_scheduled_events")
@patch("server.main.fetch_event_calendar")
@patch("server.main.save_calendar")
@patch("server.main.load_existing_manifest")
@patch("server.main.extract_basic_lands")
@patch("server.main.extract_scryfall_data")
@patch("server.main.extract_scryfall_tags")
@patch("server.main.extract_color_ratings")
@patch("server.main.extract_17lands_data")
@patch("server.main.transform_payload")
@patch("server.main.save_dataset")
@patch("server.main.save_manifest")
@patch("server.main.save_report")
@patch("server.main.deploy_web_assets")
@patch("server.main.get_historical_start_dates")
@patch("server.main.APIClient")
def test_run_pipeline(
    mock_apiclient,
    mock_get_hist,
    mock_deploy,
    mock_save_report,
    mock_save_manifest,
    mock_save_dataset,
    mock_transform,
    mock_17lands,
    mock_color_ratings,
    mock_scryfall_tags,
    mock_scryfall_data,
    mock_basic_lands,
    mock_load_manifest,
    mock_save_calendar,
    mock_fetch_calendar,
    mock_scheduled,
):
    mock_scheduled.return_value = {
        "M10": {"formats": ["PremierDraft"], "start_date": "2020-01-01"}
    }
    mock_load_manifest.return_value = {"datasets": {}}
    mock_get_hist.return_value = {}
    mock_basic_lands.return_value = {"Island": {"arena_ids": [1]}}
    mock_scryfall_data.return_value = {"Bolt": {"arena_ids": [2]}}
    mock_scryfall_tags.return_value = {"Bolt": ["removal"]}
    mock_color_ratings.return_value = ({"WG": 55.0}, {"WG": 1000}, 10000)
    mock_17lands.return_value = {"All Decks": {"Bolt": {}}, "WG": {"Bolt": {}}}
    mock_transform.return_value = {"card_ratings": {}}
    mock_save_dataset.return_value = {"filename": "test.gz", "size_kb": 10}

    with patch("server.main.time.sleep"):
        run_pipeline()

    mock_save_manifest.assert_called_once()
    mock_save_report.assert_called_once()
    mock_deploy.assert_called_once()
    mock_save_calendar.assert_called_once_with(mock_fetch_calendar.return_value)
    mock_scheduled.assert_called_once_with(mock_fetch_calendar.return_value)


@patch("server.main.get_scheduled_events")
@patch("server.main.fetch_event_calendar")
@patch("server.main.save_calendar")
@patch("server.main.deploy_web_assets")
@patch("server.main.save_report")
def test_run_pipeline_no_events(mock_save_report, mock_deploy, mock_save_calendar, mock_fetch_calendar, mock_scheduled, tmp_path):
    mock_scheduled.return_value = {}
    filename = "OTJ_PremierDraft_All_Data.json.gz"
    (tmp_path / filename).write_bytes(b"historical dataset")
    datasets = {"OTJ_PremierDraft_All": {"filename": filename, "hash": "0" * 64}}
    (tmp_path / "manifest.json").write_text(json.dumps({
        "active_sets": ["OTJ"], "datasets": datasets, "updated_at": "old"
    }))
    run_pipeline()
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["active_sets"] == []
    assert manifest["datasets"] == datasets
    assert manifest["updated_at"] != "old"
    assert (tmp_path / filename).read_bytes() == b"historical dataset"
    mock_save_report.assert_called_once()
    mock_save_calendar.assert_called_once_with(mock_fetch_calendar.return_value)
    mock_deploy.assert_called_once()


@patch("server.main.fetch_event_calendar", side_effect=RuntimeError("Schedule unavailable"))
@patch("server.main.save_report")
@patch("server.main.save_calendar")
@patch("server.main.save_dataset")
def test_run_pipeline_stops_on_schedule_failure(mock_dataset, mock_calendar, mock_report, mock_fetch):
    with pytest.raises(RuntimeError, match="Schedule unavailable"):
        run_pipeline()
    mock_dataset.assert_not_called()
    mock_calendar.assert_not_called()
    mock_report.assert_called_once()

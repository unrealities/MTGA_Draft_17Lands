import pytest
from unittest.mock import patch, MagicMock
from server.main import run_pipeline


@patch("server.main.get_scheduled_events")
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


@patch("server.main.get_scheduled_events")
@patch("server.main.save_report")
def test_run_pipeline_no_events(mock_save_report, mock_scheduled):
    mock_scheduled.return_value = {}
    run_pipeline()
    mock_save_report.assert_called_once()

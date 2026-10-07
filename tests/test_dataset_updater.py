import pytest
import json
import gzip
import os
from unittest.mock import patch, MagicMock
from src.dataset_updater import DatasetUpdater
from src.configuration import Configuration, read_configuration, write_configuration


@pytest.fixture
def updater(tmp_path, monkeypatch):
    # Route the application's SETS_FOLDER to a temporary test directory
    monkeypatch.setattr("src.constants.SETS_FOLDER", str(tmp_path))
    return DatasetUpdater(config=Configuration())


@patch("src.dataset_updater.requests.get")
def test_sync_datasets_downloads_new_files(mock_get, updater, tmp_path):
    # 1. Mock the remote manifest response
    mock_manifest_response = MagicMock()
    mock_manifest_response.status_code = 200
    mock_manifest_response.json.return_value = {
        "active_sets": ["MH3"],
        "datasets": {
            "MH3_PremierDraft_All": {
                "hash": "fake_hash_123",
                "filename": "MH3_PremierDraft_All_Data.json.gz",
            }
        },
    }

    # 2. Mock the GZIP file download response
    mock_gz_response = MagicMock()
    mock_gz_response.status_code = 200
    mock_gz_response.content = gzip.compress(b'{"mock_card": "data"}')

    # Wire the mock to return manifest first, then gz data
    mock_get.side_effect = [
        MagicMock(
            status_code=200, json=lambda: {"pipeline_run": {"status": "SUCCESS"}}
        ),  # Health check
        mock_manifest_response,
        mock_gz_response,
    ]

    progress_mock = MagicMock()

    # Act
    updater.sync_datasets(progress_mock)

    # Assert
    # Verify the GZ file was extracted and saved correctly as a standard JSON
    target_file = tmp_path / "MH3_PremierDraft_All_Data.json"
    assert target_file.exists()

    with open(target_file, "r") as f:
        data = json.load(f)
        assert data["mock_card"] == "data"

    # Verify local manifest was updated
    local_manifest = updater.get_local_manifest()
    assert "MH3_PremierDraft_All" in local_manifest["datasets"]
    assert local_manifest["datasets"]["MH3_PremierDraft_All"]["hash"] == "fake_hash_123"


@patch("src.dataset_updater.requests.get")
def test_sync_datasets_skips_existing_hashes(mock_get, updater, tmp_path):
    # Arrange: Create a local manifest that already matches the remote hash
    updater.save_local_manifest(
        {"datasets": {"MH3_PremierDraft_All": {"hash": "matched_hash"}}}
    )

    # We must also create the local file so file_missing is False
    (tmp_path / "MH3_PremierDraft_All_Data.json").write_text("dummy")

    mock_manifest_response = MagicMock()
    mock_manifest_response.status_code = 200
    mock_manifest_response.json.return_value = {
        "datasets": {
            "MH3_PremierDraft_All": {
                "hash": "matched_hash",
                "filename": "MH3_PremierDraft_All_Data.json.gz",
            }
        }
    }

    # Mock sequence: Health check -> Manifest -> (NO GZIP DOWNLOAD EXPECTED)
    mock_get.side_effect = [
        MagicMock(
            status_code=200, json=lambda: {"pipeline_run": {"status": "SUCCESS"}}
        ),
        mock_manifest_response,
    ]

    progress_mock = MagicMock()

    # Act
    updater.sync_datasets(progress_mock)

    # Assert: Network was only hit twice (Health + Manifest), meaning file download was skipped
    assert mock_get.call_count == 2


@patch("src.dataset_updater.requests.get")
def test_deleted_dataset_stays_excluded_after_restart(mock_get, updater, tmp_path):
    filename = "HOB_PremierDraft_All_Data.json"
    updater.config.card_data.excluded_datasets = [filename]
    config_path = str(tmp_path / "config.json")
    assert write_configuration(updater.config, config_path)
    config, success = read_configuration(config_path)
    assert success
    restarted = DatasetUpdater(config)

    # Exclusions survive a missing manifest (e.g. after resetting the cache),
    # and are respected even when the server publishes a new hash.
    mock_get.side_effect = [
        MagicMock(status_code=200, json=lambda: {}),
        MagicMock(
            json=lambda: {
                "active_sets": ["HOB", "MSH"],
                "datasets": {
                    "HOB_PremierDraft_All": {
                        "hash": "new_hash",
                        "filename": filename + ".gz",
                    },
                    "MSH_PremierDraft_All": {
                        "hash": "msh_hash",
                        "filename": "MSH_PremierDraft_All_Data.json.gz",
                    },
                },
            }
        ),
        MagicMock(content=gzip.compress(b'{}')),
    ]
    restarted.sync_datasets(MagicMock())

    assert not (tmp_path / filename).exists()
    assert (tmp_path / "MSH_PremierDraft_All_Data.json").exists()
    assert mock_get.call_count == 3
    assert restarted.get_local_manifest()["active_sets"] == ["HOB", "MSH"]


@patch("src.dataset_updater.requests.get")
def test_deletion_during_download_does_not_restore_file(mock_get, updater, tmp_path):
    filename = "HOB_PremierDraft_All_Data.json"

    def download(*args, **kwargs):
        updater.config.card_data.excluded_datasets.append(filename)
        return MagicMock(content=gzip.compress(b'{}'))

    responses = iter([
        MagicMock(status_code=200, json=lambda: {}),
        MagicMock(
            json=lambda: {
                "datasets": {
                    "HOB_PremierDraft_All": {
                        "hash": "new",
                        "filename": filename + ".gz",
                    },
                }
            }
        ),
    ])

    def request(*args, **kwargs):
        # Exclude after the initial check but before the file is saved.
        if args[0].endswith(".gz"):
            return download(*args, **kwargs)
        return next(responses)

    mock_get.side_effect = request
    updater.sync_datasets(MagicMock())
    assert not (tmp_path / filename).exists()
    assert not (tmp_path / (filename + ".tmp")).exists()

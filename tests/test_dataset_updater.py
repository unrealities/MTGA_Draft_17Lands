import gzip
import hashlib
import json
from unittest.mock import MagicMock, patch

import pytest
from src.dataset_updater import DatasetUpdater
from src.configuration import Configuration, read_configuration, write_configuration

KEY = "MH3_PremierDraft_All"
FILENAME = KEY + "_Data.json.gz"


@pytest.fixture
def updater(tmp_path, monkeypatch):
    monkeypatch.setattr("src.constants.SETS_FOLDER", str(tmp_path))
    return DatasetUpdater(Configuration())


@pytest.fixture
def payload():
    return json.dumps({
        "meta": {"version": 3, "start_date": "2026-01-01", "end_date": "2026-01-02"},
        "card_ratings": {str(i): {"name": f"Card {i}", "deck_colors": {"All Decks": {"gihwr": 50}}} for i in range(10)},
        "color_ratings": {"WU": 50},
    }).encode()


def file_info(compressed, filename=FILENAME):
    return {"filename": filename, "hash": hashlib.sha256(compressed).hexdigest()}


def stream_response(compressed):
    response = MagicMock()
    response.__enter__.return_value = response
    response.iter_content.return_value = [compressed]
    return response


def mock_sync(mock_get, manifest, compressed):
    mock_get.side_effect = [
        MagicMock(status_code=200, json=lambda: {}),
        MagicMock(json=lambda: manifest),
        stream_response(compressed),
    ]


@patch("src.dataset_updater.requests.get")
def test_sync_datasets_downloads_new_files(mock_get, updater, tmp_path, payload):
    compressed = gzip.compress(payload)
    info = file_info(compressed)
    mock_sync(mock_get, {"active_sets": ["MH3"], "datasets": {KEY: info}}, compressed)
    updater.sync_datasets(MagicMock())
    assert (tmp_path / FILENAME[:-3]).read_bytes() == payload
    assert updater.get_local_manifest()["datasets"][KEY] == info
    assert updater.get_local_manifest()["active_sets"] == ["MH3"]
    assert not list(tmp_path.glob("*.tmp"))


@patch("src.dataset_updater.requests.get")
def test_sync_datasets_skips_existing_hashes(mock_get, updater, tmp_path, payload):
    info = file_info(gzip.compress(payload))
    updater.save_local_manifest({"datasets": {KEY: info}})
    (tmp_path / FILENAME[:-3]).write_bytes(payload)
    mock_sync(mock_get, {"datasets": {KEY: info}}, b"")
    updater.sync_datasets(MagicMock())
    assert mock_get.call_count == 2


@patch("src.dataset_updater.requests.get")
def test_deleted_dataset_stays_excluded_after_restart(mock_get, updater, tmp_path, payload):
    updater.config.card_data.excluded_datasets = [FILENAME[:-3]]
    config_path = str(tmp_path / "config.json")
    assert write_configuration(updater.config, config_path)
    config, success = read_configuration(config_path)
    assert success
    restarted = DatasetUpdater(config)
    compressed = gzip.compress(payload)
    other_key = "MSH_PremierDraft_All"
    manifest = {"active_sets": ["MH3", "MSH"], "datasets": {
        KEY: file_info(compressed),
        other_key: file_info(compressed, other_key + "_Data.json.gz"),
    }}
    mock_sync(mock_get, manifest, compressed)
    restarted.sync_datasets(MagicMock())
    assert not (tmp_path / FILENAME[:-3]).exists()
    assert (tmp_path / (other_key + "_Data.json")).exists()
    assert mock_get.call_count == 3
    assert restarted.get_local_manifest()["active_sets"] == ["MH3", "MSH"]


@patch("src.dataset_updater.requests.get")
def test_deletion_during_download_does_not_restore_file(mock_get, updater, tmp_path, payload):
    compressed = gzip.compress(payload)
    response = stream_response(compressed)
    def chunks(**kwargs):
        updater.config.card_data.excluded_datasets.append(FILENAME[:-3])
        return iter([compressed])
    response.iter_content.side_effect = chunks
    mock_get.side_effect = [MagicMock(status_code=200, json=lambda: {}),
                           MagicMock(json=lambda: {"datasets": {KEY: file_info(compressed)}}),
                           response]
    updater.sync_datasets(MagicMock())
    assert not (tmp_path / FILENAME[:-3]).exists()
    assert not list(tmp_path.glob("*.tmp"))
    assert KEY not in updater.get_local_manifest()["datasets"]


@pytest.mark.parametrize("filename", [
    "../outside.py.gz", r"..\outside.py.gz", "/tmp/outside.py.gz",
    r"C:\outside.py.gz", "MH3_PremierDraft_All_Data.json.gz/extra",
    "%2e%2e%2foutside.py.gz", "local_manifest.json.gz",
])
@patch("src.dataset_updater.requests.get")
def test_untrusted_filename_never_reaches_download(mock_get, filename, updater, tmp_path, payload):
    compressed = gzip.compress(payload)
    old = {"datasets": {}}
    updater.save_local_manifest(old)
    mock_sync(mock_get, {"datasets": {KEY: file_info(compressed, filename)}}, compressed)
    updater.sync_datasets(MagicMock())
    assert mock_get.call_count == 2
    assert updater.get_local_manifest() == old
    assert list(tmp_path.iterdir()) == [tmp_path / "local_manifest.json"]


@pytest.mark.parametrize("bad_hash", [None, "fake_hash", "g" * 64])
@patch("src.dataset_updater.requests.get")
def test_invalid_checksum_metadata_rejected(mock_get, bad_hash, updater, payload):
    compressed = gzip.compress(payload)
    info = file_info(compressed)
    info["hash"] = bad_hash
    mock_sync(mock_get, {"datasets": {KEY: info}}, compressed)
    updater.sync_datasets(MagicMock())
    assert mock_get.call_count == 2
    assert updater.get_local_manifest() == {"datasets": {}}


@pytest.mark.parametrize("key", ["../outside", r"..\outside", "C:outside", "%2e%2e", "bad.key"])
@patch("src.dataset_updater.requests.get")
def test_unsafe_key_rejected_even_when_filename_matches(mock_get, key, updater, payload):
    compressed = gzip.compress(payload)
    manifest = {"datasets": {key: file_info(compressed, key + "_Data.json.gz")}}
    mock_sync(mock_get, manifest, compressed)
    updater.sync_datasets(MagicMock())
    assert mock_get.call_count == 2
    assert updater.get_local_manifest() == {"datasets": {}}


@pytest.mark.parametrize("failure", [
    "checksum", "gzip", "json", "encoding", "schema", "card", "statistic",
    "infinity", "metadata_count", "metadata_timestamp", "compressed_limit",
    "decompressed_limit", "replace",
])
@patch("src.dataset_updater.requests.get")
def test_failed_update_preserves_cache_and_manifest(mock_get, failure, updater, tmp_path, payload, monkeypatch):
    target = tmp_path / FILENAME[:-3]
    target.write_bytes(payload)
    old_info = {"filename": FILENAME, "hash": "0" * 64}
    updater.save_local_manifest({"datasets": {KEY: old_info}})
    compressed = gzip.compress(payload)
    if failure == "gzip":
        compressed = b"not gzip"
    elif failure == "json":
        compressed = gzip.compress(b"not json")
    elif failure == "encoding":
        compressed = gzip.compress(payload.decode("utf-8").encode("utf-16"))
    elif failure == "schema":
        compressed = gzip.compress(b'{"meta": {}, "card_ratings": {}}')
    elif failure == "card":
        data = json.loads(payload)
        data["card_ratings"]["9"] = []
        compressed = gzip.compress(json.dumps(data).encode())
    elif failure == "statistic":
        data = json.loads(payload)
        data["card_ratings"]["9"]["deck_colors"]["All Decks"]["gihwr"] = "invalid"
        compressed = gzip.compress(json.dumps(data).encode())
    elif failure == "infinity":
        compressed = gzip.compress(payload.replace(b'"gihwr": 50', b'"gihwr": 1e999'))
    elif failure in ("metadata_count", "metadata_timestamp"):
        data = json.loads(payload)
        field = "game_count" if failure == "metadata_count" else "collection_date"
        data["meta"][field] = []
        compressed = gzip.compress(json.dumps(data).encode())
    info = file_info(compressed)
    if failure == "checksum":
        info["hash"] = "1" * 64
    elif failure == "compressed_limit":
        monkeypatch.setattr("src.dataset_updater.MAX_COMPRESSED_BYTES", 10)
    elif failure == "decompressed_limit":
        monkeypatch.setattr("src.dataset_updater.MAX_DATASET_BYTES", 10)
    elif failure == "replace":
        import os
        original_replace = os.replace
        def fail_dataset_replace(src, dst):
            if str(dst) == str(target):
                raise OSError("File is locked")
            return original_replace(src, dst)
        monkeypatch.setattr("src.dataset_updater.os.replace", fail_dataset_replace)
    mock_sync(mock_get, {"datasets": {KEY: info}}, compressed)
    progress = MagicMock()
    updater.sync_datasets(progress)
    assert target.read_bytes() == payload
    assert updater.get_local_manifest()["datasets"][KEY] == old_info
    assert not list(tmp_path.glob("*.tmp"))
    progress.assert_any_call("Skipped 1 dataset update(s). Kept cached data.")


@patch("src.dataset_updater.requests.get")
def test_rejected_dataset_does_not_block_other_updates(mock_get, updater, tmp_path, payload):
    compressed = gzip.compress(payload)
    other_key = "MH3_Sealed_All"
    bad_info = file_info(compressed)
    bad_info["hash"] = "1" * 64
    manifest = {"datasets": {KEY: bad_info, other_key: file_info(compressed, other_key + "_Data.json.gz")}}
    mock_sync(mock_get, manifest, compressed)
    mock_get.side_effect = [MagicMock(status_code=200, json=lambda: {}), MagicMock(json=lambda: manifest),
                           stream_response(compressed), stream_response(compressed)]
    updater.sync_datasets(MagicMock())
    assert not (tmp_path / FILENAME[:-3]).exists()
    assert (tmp_path / (other_key + "_Data.json")).read_bytes() == payload
    assert list(updater.get_local_manifest()["datasets"]) == [other_key]


@patch("src.dataset_updater.requests.get")
def test_cube_filename_is_supported(mock_get, updater, tmp_path, payload):
    key = "Cube - Powered_PremierDraft_All"
    filename = key + "_Data.json.gz"
    compressed = gzip.compress(payload)
    mock_sync(mock_get, {"datasets": {key: file_info(compressed, filename)}}, compressed)
    updater.sync_datasets(MagicMock())
    assert (tmp_path / filename[:-3]).read_bytes() == payload
    assert "Cube%20-%20Powered" in mock_get.call_args.args[0]


@patch("src.dataset_updater.requests.get")
def test_existing_symlink_cannot_escape_sets(mock_get, updater, tmp_path, payload):
    outside = tmp_path.parent / (tmp_path.name + "-outside.json")
    outside.write_bytes(b"untouched")
    try:
        (tmp_path / FILENAME[:-3]).symlink_to(outside)
    except OSError:
        pytest.skip("Creating symlinks requires permission on this platform")
    compressed = gzip.compress(payload)
    mock_sync(mock_get, {"datasets": {KEY: file_info(compressed)}}, compressed)
    updater.sync_datasets(MagicMock())
    assert mock_get.call_count == 2
    assert outside.read_bytes() == b"untouched"

import pytest
import os
from src.constants import SETS_FOLDER, BASE_DIR
from src.utils import retrieve_local_set_list, Result
from src.utils import normalize_color_string
from unittest.mock import patch

MOCKED_SET_CODES = ["MH3", "OTJ"]
MOCKED_DATASETS = [
    "MH3_PremierDraft_Data.json",
    "MH3_PremierDraft_All_Data.json",
    "MH3_PremierDraft_Side_Data.json",
    "MH3_PremierDraft_Top_Data.json",
    "OTJ_TradDraft_Middle_Data.json",
    "OTJ_PremierDraft_All.json",
    "OTJ_PremierDraft_All_Data.txt",
    "OTJ_QuickDraft_Bottom_Data.json",
    "OTJ_FakeDraft_All_Data.json",
]
MOCKED_DATASETS_LIST_VALID = [
    (
        "MH3",
        "PremierDraft",
        "All",
        "2019-01-01",
        "2024-07-11",
        0,
        os.path.join(SETS_FOLDER, "MH3_PremierDraft_All_Data.json"),
        "2025-11-28 10:15:45.788070",
    ),
    (
        "MH3",
        "PremierDraft",
        "Top",
        "2019-01-01",
        "2024-07-11",
        0,
        os.path.join(SETS_FOLDER, "MH3_PremierDraft_Top_Data.json"),
        "2025-11-28 10:15:45.788070",
    ),
    (
        "OTJ",
        "TradDraft",
        "Middle",
        "2019-01-01",
        "2024-07-11",
        0,
        os.path.join(SETS_FOLDER, "OTJ_TradDraft_Middle_Data.json"),
        "2025-11-28 10:15:45.788070",
    ),
    (
        "OTJ",
        "QuickDraft",
        "Bottom",
        "2019-01-01",
        "2024-07-11",
        0,
        os.path.join(SETS_FOLDER, "OTJ_QuickDraft_Bottom_Data.json"),
        "2025-11-28 10:15:45.788070",
    ),
]
MOCKED_DATASET_JSON = {
    "meta": {
        "version": 2,
        "start_date": "2019-01-01",
        "end_date": "2024-07-11",
        "collection_date": "2025-11-28 10:15:45.788070",
    }
}


@patch("src.utils.os.path.exists")
@patch("src.utils.os.listdir")
@patch("src.utils.check_file_integrity")
def test_retrieve_local_set_list_skip_old(mock_integrity, mock_listdir, mock_exists):
    """
    Verify that the function ignores old datasets
    """
    import src.utils

    src.utils._LOCAL_SET_CACHE = {"mtime": 0.0, "files": []}

    mock_exists.return_value = True
    mock_listdir.return_value = MOCKED_DATASETS
    mock_integrity.return_value = (Result.VALID, MOCKED_DATASET_JSON)

    file_list, error_list = retrieve_local_set_list(MOCKED_SET_CODES)

    assert not error_list
    assert file_list == MOCKED_DATASETS_LIST_VALID


@patch("src.utils.os.path.exists")
@patch("src.utils.os.listdir")
@patch("src.utils.check_file_integrity")
def test_retrieve_local_set_list_custom_preset_label(
    mock_integrity, mock_listdir, mock_exists
):
    """Custom datasets downloaded with a time_period preset must display the
    preset label (e.g. 'All (Latest Event)') instead of the placeholder date
    range, which no longer describes what was fetched."""
    import src.utils

    src.utils._LOCAL_SET_CACHE = {"mtime": 0.0, "files": []}

    mock_exists.return_value = True
    mock_listdir.return_value = ["MSH_ContenderDraft_All_Custom-LatestEvent-20260708_Data.json"]
    mock_integrity.return_value = (
        Result.VALID,
        {
            "meta": {
                "version": 3.0,
                "start_date": "2019-01-01",
                "end_date": "2026-07-08",
                "time_period": "LATEST_EVENT",
                "collection_date": "2026-07-08 19:36:27.000000",
            }
        },
    )

    file_list, error_list = retrieve_local_set_list(["MSH"])

    assert not error_list
    assert len(file_list) == 1
    assert file_list[0][2] == "All (Latest Event)"


@patch("src.utils.os.path.exists")
@patch("src.utils.os.listdir")
@patch("src.utils.check_file_integrity")
def test_retrieve_local_set_list_custom_legacy_date_label(
    mock_integrity, mock_listdir, mock_exists
):
    """Older custom datasets without meta.time_period keep the date-range label."""
    import src.utils

    src.utils._LOCAL_SET_CACHE = {"mtime": 0.0, "files": []}

    mock_exists.return_value = True
    mock_listdir.return_value = ["OTJ_PremierDraft_All_Custom-20240416-20240503_Data.json"]
    mock_integrity.return_value = (
        Result.VALID,
        {
            "meta": {
                "version": 2,
                "start_date": "2024-04-16",
                "end_date": "2024-05-03",
                "collection_date": "2024-05-03 10:15:45.788070",
            }
        },
    )

    file_list, error_list = retrieve_local_set_list(["OTJ"])

    assert not error_list
    assert len(file_list) == 1
    assert file_list[0][2] == "All (04/16-05/03)"


@pytest.mark.parametrize(
    "input_color, expected_output",
    [
        ("RW", "WR"),
        ("GW", "WG"),
        ("UG", "UG"),
        ("GU", "UG"),
        ("WUBRG", "WUBRG"),
        ("GRBUW", "WUBRG"),
        ("U", "U"),
        ("", ""),
        ("All Decks", "All Decks"),
        ("Auto", "Auto"),
    ],
)
def test_normalize_color_string(input_color, expected_output):
    """
    Verify that color strings are normalized to WUBRG order.
    """
    assert normalize_color_string(input_color) == expected_output


def test_purge_raw_cache_removes_files(tmp_path, monkeypatch):
    """The upgrade migration should clear stale raw-cache entries."""
    import src.constants as constants_module
    from src.utils import purge_raw_cache

    monkeypatch.setattr(constants_module, "BASE_DIR", str(tmp_path))
    cache_dir = tmp_path / "Temp" / "RawCache"
    cache_dir.mkdir(parents=True)
    (cache_dir / "otj_premierdraft_2024-01-01_2024-02-01_all_all.json").write_text("[]")
    (cache_dir / "otj_premierdraft_2024-01-02_2024-02-02_wu_all.json").write_text("[]")

    removed = purge_raw_cache()

    assert removed == 2
    assert list(cache_dir.iterdir()) == []


def test_purge_raw_cache_missing_dir_is_safe(tmp_path, monkeypatch):
    """A missing cache directory must not raise, just report nothing removed."""
    import src.constants as constants_module
    from src.utils import purge_raw_cache

    monkeypatch.setattr(constants_module, "BASE_DIR", str(tmp_path))
    assert purge_raw_cache() == 0


def test_clear_set_history_removes_datasets(tmp_path, monkeypatch):
    """Clearing set history deletes datasets and the manifest but leaves other files."""
    import src.utils as utils_module
    from src.utils import clear_set_history

    monkeypatch.setattr(utils_module, "SETS_FOLDER", str(tmp_path))
    (tmp_path / "MSH_PremierDraft_All_Data.json").write_text("{}")
    (tmp_path / "BLB_QuickDraft_Top_Data.json").write_text("{}")
    (tmp_path / "local_manifest.json").write_text("{}")
    (tmp_path / "unrelated.txt").write_text("keep me")

    removed = clear_set_history()

    assert removed == 2
    assert not (tmp_path / "MSH_PremierDraft_All_Data.json").exists()
    assert not (tmp_path / "local_manifest.json").exists()
    assert (tmp_path / "unrelated.txt").exists()


@patch("src.utils._save_persisted_index")
@patch("src.utils._load_persisted_index", return_value={})
@patch("src.utils.os.path.getmtime")
@patch("src.utils._file_stamp")
@patch("src.utils.os.path.exists")
@patch("src.utils.os.listdir")
@patch("src.utils.check_file_integrity")
def test_retrieve_local_set_list_reparses_only_changed_files(
    mock_integrity, mock_listdir, mock_exists, mock_stamp, mock_getmtime, _load, _save
):
    """A folder mtime bump (e.g. custom_cards.json being rewritten by the card
    resolver) must not re-read every dataset; only files whose own stamp
    changed are parsed again."""
    import os
    import src.utils

    src.utils._LOCAL_SET_CACHE = {"mtime": 0.0, "files": []}
    mock_exists.return_value = True
    mock_listdir.return_value = MOCKED_DATASETS
    mock_integrity.return_value = (Result.VALID, MOCKED_DATASET_JSON)
    mock_getmtime.return_value = 100.0
    mock_stamp.side_effect = lambda name: (1, 1)

    first, _ = retrieve_local_set_list(MOCKED_SET_CODES)
    parsed = mock_integrity.call_count
    assert parsed > 0

    # Sibling file rewritten: folder mtime changes, dataset stamps do not.
    mock_getmtime.return_value = 200.0
    second, _ = retrieve_local_set_list(MOCKED_SET_CODES)
    assert second == first
    assert mock_integrity.call_count == parsed

    # One dataset replaced: only that file is re-read.
    changed = os.path.basename(mock_integrity.call_args_list[0][0][0])
    mock_stamp.side_effect = lambda name: (2, 2) if name == changed else (1, 1)
    mock_getmtime.return_value = 300.0
    retrieve_local_set_list(MOCKED_SET_CODES)
    assert mock_integrity.call_count == parsed + 1


@patch("src.utils.os.path.getmtime")
@patch("src.utils._file_stamp")
@patch("src.utils.os.path.exists")
@patch("src.utils.os.listdir")
@patch("src.utils.check_file_integrity")
def test_retrieve_local_set_list_index_survives_restart(
    mock_integrity, mock_listdir, mock_exists, mock_stamp, mock_getmtime, tmp_path
):
    """The per-file index is persisted, so a fresh process (empty in-memory
    cache) parses nothing when no dataset changed. Boot used to cost ~0.1 s
    per dataset on the UI thread."""
    import src.utils

    index_file = tmp_path / "dataset_index.json"
    with patch("src.utils._index_path", return_value=str(index_file)):
        src.utils._LOCAL_SET_CACHE = {"mtime": 0.0, "files": []}
        mock_exists.return_value = True
        mock_listdir.return_value = MOCKED_DATASETS
        mock_integrity.return_value = (Result.VALID, MOCKED_DATASET_JSON)
        mock_getmtime.return_value = 100.0
        mock_stamp.side_effect = lambda name: (1, 1)

        first, _ = retrieve_local_set_list(MOCKED_SET_CODES)
        parsed = mock_integrity.call_count
        assert parsed > 0
        assert index_file.exists()

        # New process: in-memory cache empty, index on disk.
        src.utils._LOCAL_SET_CACHE = {"mtime": 0.0, "files": []}
        second, _ = retrieve_local_set_list(MOCKED_SET_CODES)
        assert second == first
        assert mock_integrity.call_count == parsed

        # A changed file is still re-read after a restart.
        import os

        changed = os.path.basename(mock_integrity.call_args_list[0][0][0])
        src.utils._LOCAL_SET_CACHE = {"mtime": 0.0, "files": []}
        mock_stamp.side_effect = lambda name: (2, 2) if name == changed else (1, 1)
        retrieve_local_set_list(MOCKED_SET_CODES)
        assert mock_integrity.call_count >= parsed + 1

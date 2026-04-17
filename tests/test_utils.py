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

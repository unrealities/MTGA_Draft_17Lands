import pytest
import unittest
from unittest.mock import patch, MagicMock
import os
from src.constants import SETS_FOLDER
from src.utils import capture_screen_base64str, retrieve_local_set_list, Result
from src.utils import normalize_color_string

SCREENSHOT_FOLDER = os.path.join(os.getcwd(), "Screenshots")
SCREENSHOT_PREFIX = "p1p1_screenshot_"

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


class TestCaptureScreenBase64str(unittest.TestCase):

    @patch("PIL.ImageGrab.grab")
    @patch("time.time")
    @patch("os.path.join")
    @patch("builtins.open", new_callable=unittest.mock.mock_open)
    def test_screenshot_persist(self, mock_open, mock_path_join, mock_time, mock_grab):
        # Arrange
        mock_image = MagicMock()
        mock_grab.return_value = mock_image
        mock_time.return_value = 1234567890
        mock_path_join.return_value = "/Screenshots/screenshot_1234567890.png"

        expected_filename = "/Screenshots/screenshot_1234567890.png"

        # Act
        base64str = capture_screen_base64str(True)

        # Assert
        mock_grab.assert_called_once()
        mock_time.assert_called_once()
        mock_path_join.assert_called_once_with(
            SCREENSHOT_FOLDER, SCREENSHOT_PREFIX + "1234567890.png"
        )
        mock_image.save.assert_any_call(expected_filename, format="PNG")
        self.assertIsInstance(base64str, str)

    @patch("PIL.ImageGrab.grab")
    @patch("time.time")
    @patch("os.path.join")
    @patch("builtins.open", new_callable=unittest.mock.mock_open)
    def test_screenshot_not_persist(
        self, mock_open, mock_path_join, mock_time, mock_grab
    ):
        # Arrange
        mock_image = MagicMock()
        mock_grab.return_value = mock_image

        # Act
        base64str = capture_screen_base64str(False)

        # Assert
        mock_grab.assert_called_once()
        mock_time.assert_not_called()
        mock_path_join.assert_not_called()
        self.assertIsInstance(base64str, str)


if __name__ == "__main__":
    unittest.main()


@patch("os.listdir")
@patch("src.utils.check_file_integrity")
def test_retrieve_local_set_list_skip_old(mock_integrity, mock_listdir):
    """
    Verify that the function ignores old datasets
    """
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

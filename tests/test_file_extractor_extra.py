import pytest
from unittest.mock import MagicMock, patch
from src.file_extractor import FileExtractor


def test_retrieve_17lands_data_success():
    extractor = FileExtractor(None, MagicMock(), MagicMock(), MagicMock())
    extractor.draft = "PremierDraft"
    extractor.start_date = "2020-01-01"
    extractor.end_date = "2020-02-01"
    extractor.user_group = "All"
    extractor.selected_sets = MagicMock(seventeenlands=["M10"])

    with patch("src.file_extractor.Seventeenlands") as mock_sl:
        mock_instance = mock_sl.return_value
        mock_instance.download_card_ratings.return_value = None

        result = extractor.retrieve_17lands_data(["M10"], ["All Decks"])
        assert result is True
        mock_instance.download_card_ratings.assert_called_once()


def test_retrieve_17lands_data_fail():
    extractor = FileExtractor(None, MagicMock(), MagicMock(), MagicMock())
    extractor.draft = "PremierDraft"
    extractor.start_date = "2020-01-01"
    extractor.end_date = "2020-02-01"
    extractor.user_group = "All"
    extractor.selected_sets = MagicMock(seventeenlands=["M10"])

    with patch("src.file_extractor.Seventeenlands") as mock_sl:
        mock_instance = mock_sl.return_value
        mock_instance.download_card_ratings.side_effect = Exception("API Error")

        with patch("src.constants.CARD_RATINGS_ATTEMPT_MAX", 1):
            with patch("src.file_extractor.time.sleep"):
                result = extractor.retrieve_17lands_data(["M10"], ["All Decks"])
                assert result is False


def test_check_set_data():
    from src.file_extractor import check_set_data

    check_set_data({"1": {"name": "Bolt"}}, ["Bolt", "Shock"])


def test_search_arena_log_locations_manual():
    from src.file_extractor import search_arena_log_locations

    with patch("src.file_extractor.os.path.exists", return_value=True):
        assert search_arena_log_locations("manual.log", "config.log") == "manual.log"


def test_retrieve_arena_directory():
    from src.file_extractor import retrieve_arena_directory
    from unittest.mock import mock_open

    mock_data = (
        "Garbage line 1\n"
        "Garbage line 2\n"
        "Some log line 'C:/Program Files/Wizards of the Coast/MTGA/MTGA_Data/Managed'\n"
    )
    with patch("builtins.open", mock_open(read_data=mock_data)):
        with patch("src.file_extractor.os.path.exists", return_value=True):
            with patch("sys.platform", "win32"):
                res = retrieve_arena_directory("log.txt")
                assert res == "C:/Program Files/Wizards of the Coast/MTGA/MTGA_Data"

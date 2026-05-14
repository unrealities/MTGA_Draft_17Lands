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


@patch("src.file_extractor.FileExtractor.export_card_data", return_value="output.json")
@patch("src.file_extractor.FileExtractor._inject_community_tags", return_value=[])
@patch(
    "src.file_extractor.FileExtractor._retrieve_local_arena_data",
    return_value=(True, "Success", 1024),
)
@patch("src.file_extractor.Seventeenlands.download_set_data")
def test_download_card_data_success_pipeline(
    mock_17l, mock_local_data, mock_tags, mock_export
):
    """Verify the entire file extractor pipeline processes successfully when components align."""
    extractor = FileExtractor(None, MagicMock(), MagicMock(), MagicMock())
    extractor.selected_sets = MagicMock(
        seventeenlands=["OTJ"], arena=["OTJ"], set_code="OTJ"
    )
    extractor.draft = "PremierDraft"
    extractor.start_date = "2024-01-01"
    extractor.end_date = "2024-02-01"

    # Mock local arena cards
    extractor.card_dict = {
        "123": {"name": "Lightning Bolt", "set": "OTJ"},
        "999": {
            "name": "Basic Plains",
            "set": "OTJ",
        },  # Should trigger fallback initialization
    }

    # Mock 17Lands response
    mock_17l.return_value = {
        "Lightning Bolt": {
            "deck_colors": {"All Decks": {"gihwr": 60.0}},
            "image": ["img_url"],
        }
    }

    # Force a color target
    extractor.combined_data["color_ratings"] = {"All Decks": 55.0}

    success, msg, size = extractor.download_card_data(0)

    assert success is True
    assert "Download Successful" in msg
    assert "123" in extractor.combined_data["card_ratings"]
    assert (
        extractor.combined_data["card_ratings"]["123"]["deck_colors"]["All Decks"][
            "gihwr"
        ]
        == 60.0
    )


@patch(
    "src.file_extractor.FileExtractor._retrieve_local_arena_data",
    return_value=(True, "Success", 1024),
)
@patch("src.file_extractor.Seventeenlands.download_set_data")
def test_download_card_data_api_failure_graceful_fallback(mock_17l, mock_local_data):
    """Verify that a 404 from 17Lands (e.g. Day 1 release) still saves the local card data for tooltips."""
    extractor = FileExtractor(None, MagicMock(), MagicMock(), MagicMock())
    extractor.selected_sets = MagicMock(
        seventeenlands=["OTJ"], arena=["OTJ"], set_code="OTJ"
    )

    extractor.card_dict = {"123": {"name": "New Card", "set": "OTJ"}}

    # Simulate 17Lands not having data yet
    mock_17l.side_effect = Exception("HTTP 404 Not Found")

    # We must patch export so it doesn't try to write to a real directory
    with patch(
        "src.file_extractor.FileExtractor.export_card_data", return_value="output.json"
    ):
        success, msg, size = extractor.download_card_data(0)

    # App MUST return True so it saves the JSON. The UI needs this JSON for card text/tooltips!
    assert success is True
    assert "17Lands data not yet available" in msg
    assert "123" in extractor.combined_data["card_ratings"]
    # Verify card was initialized safely
    assert "All Decks" in extractor.combined_data["card_ratings"]["123"]["deck_colors"]

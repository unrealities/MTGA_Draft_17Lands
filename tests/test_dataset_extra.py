import json
from unittest.mock import patch, MagicMock
from src.dataset import Dataset
from src.constants import DATA_FIELD_NAME


def test_resolve_unknown_id():
    dataset = Dataset(retrieve_unknown=True, db_path="/mock/path")

    with patch("os.path.exists", return_value=True):
        with patch("os.listdir", return_value=["Raw_CardDatabase_1.sqlite"]):
            with patch("os.path.getmtime", return_value=1.0):
                with patch("sqlite3.connect") as mock_connect:
                    mock_conn = MagicMock()
                    mock_cursor = MagicMock()
                    mock_connect.return_value = mock_conn
                    mock_conn.cursor.return_value = mock_cursor

                    # Mock finding the table (fetchall) and row (fetchone)
                    mock_cursor.fetchall.return_value = [("Localizations_enUS",)]
                    mock_cursor.fetchone.return_value = ("Lightning Bolt",)

                    result = dataset._resolve_unknown_id("123")
                    assert result == "Lightning Bolt"
                    assert dataset.unknown_id_cache["123"] == "Lightning Bolt"


def test_resolve_unknown_id_no_db_dir():
    """Verify graceful fallback if the MTGA_Data directory doesn't exist."""
    dataset = Dataset(retrieve_unknown=True, db_path="/fake/path")
    with patch("os.path.exists", return_value=False):
        assert dataset._resolve_unknown_id("999") == "999"


@patch("os.path.exists", return_value=True)
@patch("os.listdir")
@patch("os.path.getmtime")
@patch("sqlite3.connect")
def test_resolve_unknown_id_db_corrupted(
    mock_connect, mock_mtime, mock_listdir, mock_exists
):
    """Verify graceful fallback if sqlite throws an OperationalError (e.g. file locked)."""
    dataset = Dataset(retrieve_unknown=True, db_path="/mock/path")
    mock_listdir.return_value = ["Raw_CardDatabase_1.sqlite"]
    mock_connect.side_effect = Exception("database is locked")

    # Should catch exception, log it, and return the raw ID
    assert dataset._resolve_unknown_id("999") == "999"


@patch("src.dataset.Dataset._save_custom_cache")
@patch("src.dataset.Dataset._load_custom_cache")
@patch("requests.post")
def test_get_data_by_id_scryfall_bulk_fallback(mock_post, mock_load, mock_save):
    """Verify that unresolved IDs trigger a bulk Scryfall request that caches results."""
    dataset = Dataset(retrieve_unknown=True, db_path=None)  # No DB, forces Scryfall

    # Mock Scryfall API response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": [
            {
                "arena_id": 999,
                "name": "New Day 1 Card",
                "type_line": "Creature",
                "colors": ["G"],
                "cmc": 2,
                "mana_cost": "{1}{G}",
            }
        ]
    }
    mock_post.return_value = mock_response

    # Act: Request an ID we have no data for
    result = dataset.get_data_by_id(["999"])

    # Assert
    assert len(result) == 1
    assert result[0][DATA_FIELD_NAME] == "New Day 1 Card"

    # Verify it was saved to the custom fallback cache
    assert "999" in dataset._fallback_ratings
    assert dataset._fallback_ratings["999"][DATA_FIELD_NAME] == "New Day 1 Card"
    mock_save.assert_called_once()


@patch("src.dataset.Dataset._save_custom_cache")
@patch("src.dataset.Dataset._load_custom_cache")
@patch("requests.post")
def test_get_data_by_id_scryfall_api_failure(mock_post, mock_load, mock_save):
    """Verify that if Scryfall API crashes, it injects an empty dummy card to prevent UI KeyErrors."""
    dataset = Dataset(retrieve_unknown=True, db_path=None)
    mock_post.side_effect = Exception("Network Timeout")

    result = dataset.get_data_by_id(["999"])

    assert len(result) == 1
    assert result[0][DATA_FIELD_NAME] == "999"  # Falls back to the string ID
    assert "deck_colors" in result[0]  # Must be initialized safely!

import pytest
from unittest.mock import patch, MagicMock
from src.dataset import Dataset


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

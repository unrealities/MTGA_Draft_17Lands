import pytest
from unittest.mock import patch, MagicMock
from src.file_extractor import FileExtractor


@pytest.fixture
def extractor():
    return FileExtractor(None, MagicMock(), MagicMock(), MagicMock())


@patch("src.file_extractor.search_local_files")
@patch("src.file_extractor.os.path.getsize")
@patch("src.file_extractor.sqlite3.connect")
def test_retrieve_local_arena_data_success(
    mock_connect, mock_getsize, mock_search, extractor, tmp_path, monkeypatch
):
    """Verifies that MTGA SQLite data is correctly mapped into card dictionaries."""

    # Safely point the temporary output file to the pytest temp directory
    monkeypatch.setattr(
        "src.constants.TEMP_CARD_DATA_FILE", str(tmp_path / "temp_card_data.json")
    )

    # 1. Pretend we found the MTGA database file
    mock_search.return_value = ["/mock/path/Raw_CardDatabase_123.sqlite"]
    mock_getsize.return_value = 1024  # Triggers an update (size changed from 0)

    # 2. Mock the SQLite Connection and Cursor
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_connect.return_value = mock_conn

    # 3. Intercept SQL queries and return mock MTGA data
    def execute_side_effect(query, *args, **kwargs):
        if "Localizations" in query:
            return [
                {"LocId": 1, "Formatted": 1, "Loc": "Lightning Bolt"},
                {"LocId": 10, "Formatted": 1, "Loc": "Instant"},
                {"LocId": 20, "Formatted": 1, "Loc": "Red"},
            ]
        elif "Enums" in query:
            return [
                {"LocId": 10, "Type": "CardType", "Value": 1},
                {"LocId": 20, "Type": "Color", "Value": 2},
            ]
        elif "Cards" in query:
            return [
                {
                    "expansioncode": "M10",
                    "digitalreleaseset": "",
                    "grpid": 1001,
                    "istoken": 0,
                    "titleid": 1,
                    "cmc": 1,
                    "coloridentity": "2",  # Mapped to Red
                    "types": "1",  # Mapped to Instant
                    "oldschoolmanatext": "oR",
                    "rarity": 2,
                    "isprimarycard": 1,
                    "linkedfacegrpids": "",
                    "linkedfacetype": 0,
                }
            ]
        return []

    mock_cursor.execute = MagicMock(side_effect=execute_side_effect)

    # Restrict to just the M10 set
    extractor.selected_sets = MagicMock(arena=["M10"])

    # 4. Act: Instead of mocking open(), we let it write to the safe temp file
    result, msg, size = extractor._retrieve_local_arena_data(0)

    # 5. Assert: Verify the app successfully decoded the raw database
    assert result is True
    assert size == 1024

    # Card 1001 should be processed and stored in memory
    assert "1001" in extractor.card_dict
    card = extractor.card_dict["1001"]

    assert card["name"] == "Lightning Bolt"
    assert "Instant" in card["types"]
    assert "R" in card["colors"]
    assert card["cmc"] == 1


def test_extract_types_identifies_all_categories():
    """Verify string-based type extraction handles complex typelines."""
    from src.file_extractor import extract_types

    res1 = extract_types("Legendary Artifact Creature")
    assert "Creature" in res1
    assert "Artifact" in res1

    res2 = extract_types("Basic Snow Land")
    assert "Land" in res2

    res3 = extract_types("Sorcery")
    assert "Sorcery" in res3

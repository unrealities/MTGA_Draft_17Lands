import pytest
import json
import os
from unittest.mock import patch, MagicMock
from src.tier_list import TierList, Meta, Rating, TIER_FOLDER


@patch("src.tier_list.requests.get")
def test_tier_list_from_api(mock_get):
    """Verify 17Lands API parsing, including graceful handling of missing grades."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "name": "Pro Player Review",
        "expansion": "OTJ",
        "ratings": [
            {"name": "Great Card", "tier": "A+", "comment": "First pick."},
            {"name": "Bad Card", "tier": "Z", "comment": "Trash."},  # Invalid tier
        ],
    }
    mock_get.return_value = mock_response

    tl = TierList.from_api("https://www.17lands.com/tier_list/123456789")

    assert tl is not None
    assert tl.meta.label == "Pro Player Review"
    assert tl.meta.set == "OTJ"

    # Valid grade handled perfectly
    assert tl.ratings["Great Card"].rating == "A+"
    assert tl.ratings["Great Card"].comment == "First pick."

    # Invalid grade normalized to NA (space)
    assert tl.ratings["Bad Card"].rating == " "


def test_tier_list_file_io(tmp_path, monkeypatch):
    """Verify writing and reading tier lists to local disk."""
    monkeypatch.setattr("src.tier_list.TIER_FOLDER", str(tmp_path))

    tl = TierList(
        meta=Meta(label="File Test", set="M10"),
        ratings={"Bolt": Rating(rating="A+", comment="")},
    )

    filepath = str(tmp_path / "Tier_M10_123.txt")

    # Write
    tl.to_file(filepath)
    assert os.path.exists(filepath)

    # Read
    loaded_tl = TierList.from_file(filepath)
    assert loaded_tl is not None
    assert loaded_tl.meta.label == "File Test"
    assert loaded_tl.ratings["Bolt"].rating == "A+"


@patch("src.tier_list.os.path.getmtime", return_value=12345.0)
@patch("src.tier_list.os.listdir")
@patch("src.tier_list.TierList.from_file")
def test_tier_list_retrieve_files(
    mock_from_file, mock_listdir, mock_mtime, monkeypatch
):
    """Verify the file scanning logic correctly identifies valid tier lists."""
    mock_listdir.return_value = [
        "Tier_M10_123.txt",
        "Random_File.txt",
        "Tier_OTJ_456.txt",
    ]

    mock_tl_m10 = MagicMock()
    mock_tl_m10.meta.set = "M10"
    mock_tl_m10.meta.label = "M10 Review"
    mock_tl_m10.meta.collection_date = "2024-01-01 12:00:00"

    mock_tl_otj = MagicMock()
    mock_tl_otj.meta.set = "OTJ"
    mock_tl_otj.meta.label = "OTJ Review"
    mock_tl_otj.meta.collection_date = "2024-05-01 12:00:00"

    # Return different objects based on filename
    def side_effect(filepath):
        if "M10" in filepath:
            return mock_tl_m10
        if "OTJ" in filepath:
            return mock_tl_otj
        return None

    mock_from_file.side_effect = side_effect

    # Force cache miss
    import src.tier_list

    src.tier_list._TIER_CACHE["mtime"] = 0.0

    files = TierList.retrieve_files(code="OTJ")

    # Should filter to just OTJ
    assert len(files) == 1
    assert files[0][0] == "OTJ"
    assert files[0][1] == "OTJ Review"

import pytest
import os
import json
from unittest.mock import patch, MagicMock, mock_open
from src.scryfall_tagger import ScryfallTagger


@pytest.fixture
def tagger():
    return ScryfallTagger()


def test_harvest_set_tags_cube(tagger):
    tags, errors = tagger.harvest_set_tags("CUBE")
    assert tags == {}
    assert errors == []


@patch("src.scryfall_tagger.is_cache_stale", return_value=False)
@patch("os.path.exists", return_value=True)
def test_harvest_set_tags_cache_hit(mock_exists, mock_stale, tagger):
    mock_cache_data = json.dumps({"Lightning Bolt": ["removal"]})
    with patch("builtins.open", mock_open(read_data=mock_cache_data)):
        tags, errors = tagger.harvest_set_tags("M10")
        assert tags == {"Lightning Bolt": ["removal"]}
        assert errors == []


@patch("src.scryfall_tagger.is_cache_stale", return_value=True)
@patch("src.scryfall_tagger.requests.get")
@patch("src.scryfall_tagger.time.sleep")
def test_harvest_set_tags_api_fetch(mock_sleep, mock_get, mock_stale, tagger):
    # Mock the Scryfall API responses
    def mock_get_side_effect(*args, **kwargs):
        response = MagicMock()
        url = kwargs.get("url") or args[0]
        if "removal" in url:
            response.status_code = 200
            response.json.return_value = {
                "data": [{"name": "Lightning Bolt"}],
                "next_page": None,
            }
        else:
            response.status_code = 404  # No cards for other tags
        return response

    with patch("builtins.open", mock_open()) as mock_file:
        tags, errors = tagger.harvest_set_tags("M10")
        assert "Lightning Bolt" in tags
        assert "removal" in tags["Lightning Bolt"]

    # Verify cache was written
    mock_file.assert_called()


@patch("src.scryfall_tagger.is_cache_stale", return_value=True)
@patch("src.scryfall_tagger.requests.get")
@patch("src.scryfall_tagger.time.sleep")
def test_harvest_set_tags_api_error(mock_sleep, mock_get, mock_stale, tagger):
    mock_get.side_effect = Exception("API Error")
    tags, errors = tagger.harvest_set_tags("M10")
    assert tags == {}
    assert len(errors) > 0
    assert "API Error" in errors[0]

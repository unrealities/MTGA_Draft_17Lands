import pytest
import json
from unittest.mock import patch, MagicMock
from src.ocr import OCR


@patch("src.ocr.requests.post")
def test_ocr_get_pack(mock_post):
    """Verify that the OCR client constructs the correct payload and parses the API response."""
    # Setup mock response
    mock_response = MagicMock()
    mock_response.text = '["Lightning Bolt", "Counterspell"]'
    mock_post.return_value = mock_response

    ocr = OCR("https://fake.url/ocr")
    card_names = ["Lightning Bolt", "Counterspell", "Trash Card"]
    screenshot_data = "base64_encoded_string_data"

    # Act
    detected_names = ocr.get_pack(card_names, screenshot_data)

    # Assert network call
    mock_post.assert_called_once()

    # Extract the payload that was sent
    call_kwargs = mock_post.call_args.kwargs
    payload = json.loads(call_kwargs["data"])

    # Verify payload schema
    assert payload["image"] == "base64_encoded_string_data"
    assert "Lightning Bolt" in payload["card_names"]

    # Ensure basic lands are inherently appended to the search matrix to prevent OCR misses
    assert "plains" in payload["card_names"]
    assert "island" in payload["card_names"]

    # Verify return value
    assert len(detected_names) == 2
    assert "Lightning Bolt" in detected_names

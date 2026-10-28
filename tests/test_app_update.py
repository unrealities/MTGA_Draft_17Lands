import os
import sys
import json
import pytest
from unittest.mock import patch, MagicMock
from src.app_update import AppUpdate
from src.constants import OLD_APPLICATION_VERSION
from src.constants import BASE_DIR


@pytest.fixture
def app_update():
    return AppUpdate()


@pytest.fixture
def invalid_search_location():
    return "http://invalid_location"


@pytest.fixture
def valid_search_location_old():
    return (
        "https://api.github.com/repos/unrealities/MTGA_Draft_17Lands/releases/163580064"
    )


@pytest.fixture
def valid_search_location_latest():
    return "https://api.github.com/repos/unrealities/MTGA_Draft_17Lands/releases/latest"


@patch("src.app_update.urllib.request.urlopen")
def test_retrieve_file_version_latest_success(
    mock_urlopen, app_update, valid_search_location_latest
):
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps(
        {
            "tag_name": "v4.07",
            "assets": [
                {
                    "browser_download_url": "https://mock.url/file.exe",
                    "name": "MTGA_Draft_Tool.exe",
                }
            ],
        }
    ).encode("utf-8")
    mock_response.__enter__.return_value = mock_response
    mock_urlopen.return_value = mock_response

    version, file_location = app_update.retrieve_file_version(
        valid_search_location_latest
    )
    assert isinstance(version, str) and isinstance(float(version), float)
    assert isinstance(file_location, str)
    assert len(file_location) != 0


@patch("src.app_update.urllib.request.urlopen")
def test_retrieve_file_version_old_success(
    mock_urlopen, app_update, valid_search_location_old
):
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps(
        {
            "tag_name": f"v{OLD_APPLICATION_VERSION}",
            "assets": [
                {
                    "browser_download_url": "https://mock.url/old.zip",
                    "name": "MTGA_Draft_Tool_old.zip",
                }
            ],
        }
    ).encode("utf-8")
    mock_response.__enter__.return_value = mock_response
    mock_urlopen.return_value = mock_response

    version, file_location = app_update.retrieve_file_version(valid_search_location_old)
    assert version == OLD_APPLICATION_VERSION


@patch("src.app_update.urllib.request.urlopen")
def test_retrieve_file_version_failure(
    mock_urlopen, app_update, invalid_search_location
):
    mock_urlopen.side_effect = Exception("Network Error")

    version, file_location = app_update.retrieve_file_version(invalid_search_location)
    assert version == ""
    assert file_location == ""


# =====================================================================
# LIVE API VERIFICATION (Runs only on Master/Main)
# =====================================================================


@pytest.mark.skipif(
    os.environ.get("GITHUB_REF") not in ["refs/heads/master", "refs/heads/main"],
    reason="Live API tests only run on master/main to preserve rate limits.",
)
def test_live_github_api_verification(app_update, valid_search_location_latest):
    """
    True verification test. Hits the live GitHub API to ensure the payload
    schema hasn't unexpectedly changed.
    """
    import urllib.request
    from urllib.error import HTTPError

    req = urllib.request.Request(
        valid_search_location_latest, headers={"User-Agent": "MTGA-Draft-Tool-Test"}
    )

    # Use GitHub Actions token if available to heavily boost rate limits
    if "GITHUB_TOKEN" in os.environ:
        req.add_header("Authorization", f"Bearer {os.environ['GITHUB_TOKEN']}")

    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read())
    except HTTPError as e:
        if e.code in (403, 429):
            pytest.skip(
                f"GitHub API Rate Limit exceeded (HTTP {e.code}). Gracefully skipping live test."
            )
        pytest.fail(f"Live API request failed: HTTP {e.code}")
    except Exception as e:
        pytest.fail(f"Live API request failed unexpectedly: {e}")

    # If we successfully grabbed the live data, push it through the processor
    app_update._AppUpdate__process_file_version(data)

    # If these asserts fail, GitHub changed their API schema and broke the app updater
    assert app_update.version != "", "Live API schema changed! Could not parse version."
    assert app_update.file_location != "", (
        "Live API schema changed! Could not parse download URL."
    )
    assert isinstance(float(app_update.version), float)

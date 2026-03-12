import sys
import json
from unittest.mock import patch, MagicMock
from src.app_update import AppUpdate
from src.constants import OLD_APPLICATION_VERSION, PREVIOUS_APPLICATION_VERSION
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


@pytest.fixture
def invalid_input_url():
    return "http://invalid_url"


@pytest.fixture
def valid_input_url_zip():
    return f"https://github.com/unrealities/MTGA_Draft_17Lands/releases/download/MTGA_Draft_Tool_V{PREVIOUS_APPLICATION_VERSION}/MTGA_Draft_Tool_V{PREVIOUS_APPLICATION_VERSION}.zip"


@pytest.fixture
def output_filename():
    return "test_file.exe"


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


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_download_file_zip_success(app_update, valid_input_url_zip, output_filename):
    output_location = app_update.download_file(valid_input_url_zip, output_filename)
    assert isinstance(output_location, str) and os.path.exists(output_location)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_download_file_failure(app_update, invalid_input_url, output_filename):
    output_location = app_update.download_file(invalid_input_url, output_filename)
    assert output_location == ""

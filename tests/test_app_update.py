import pytest
import os
import sys
from src.app_update import AppUpdate

EXPECTED_OLD_VERSION_STRING = "0319"

@pytest.fixture
def app_update():
    return AppUpdate()

@pytest.fixture
def invalid_search_location():
    return "http://invalid_location"

@pytest.fixture
def valid_search_location_old():
    return "https://api.github.com/repos/unrealities/MTGA_Draft_17Lands/releases/163580064"

@pytest.fixture
def valid_search_location_latest():
    return "https://api.github.com/repos/unrealities/MTGA_Draft_17Lands/releases/latest"

@pytest.fixture
def invalid_input_url():
    return "http://invalid_url"

@pytest.fixture
def valid_input_url_zip():
    return "https://github.com/unrealities/MTGA_Draft_17Lands/releases/download/MTGA_Draft_Tool_V0319/MTGA_Draft_Tool_V0320.zip"
    
@pytest.fixture
def output_filename():
    return "test_file.exe"

@pytest.mark.skipif(sys.platform == 'darwin', reason="Skipping on macOS because of Github API rate limiting")
def test_retrieve_file_version_latest_success(app_update, valid_search_location_latest):
    version, file_location = app_update.retrieve_file_version(valid_search_location_latest)
    assert isinstance(version, str) and isinstance(float(version), float)
    assert isinstance(file_location, str)
    assert len(file_location) != 0

@pytest.mark.skipif(sys.platform == 'darwin', reason="Skipping on macOS because of Github API rate limiting")
def test_retrieve_file_version_old_success(app_update, valid_search_location_old):
    version, file_location = app_update.retrieve_file_version(valid_search_location_old)
    assert version == EXPECTED_OLD_VERSION_STRING

@pytest.mark.skipif(sys.platform == 'darwin', reason="Skipping on macOS because of Github API rate limiting")
def test_retrieve_file_version_failure(app_update, invalid_search_location):
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

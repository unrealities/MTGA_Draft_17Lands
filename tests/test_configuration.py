import pytest
import json
import os
import sys
from unittest.mock import patch, MagicMock
from dataclasses import asdict

# Import the functions to be tested
from src.configuration import (
    read_configuration,
    write_configuration,
    reset_configuration,
    Configuration,
    get_config_path,
)


@pytest.fixture
def example_configuration():
    # Create an example Configuration object for testing
    config = Configuration()
    config.features.override_scale_factor = 1.5
    config.features.hotkey_enabled = True
    config.features.images_enabled = False
    return config


def test_read_configuration_existing_file(tmp_path, example_configuration):
    # Create a temporary file for testing
    file_location = tmp_path / "config.json"

    # Write the example configuration to the temporary file
    with open(file_location, "w") as f:
        json.dump(example_configuration.model_dump(), f)

    # Test reading the configuration from an existing file
    config, success = read_configuration(file_location)

    # Assert that the configuration was successfully read
    assert success is True

    # Assert that the returned configuration matches the example configuration
    assert config == example_configuration


def test_read_configuration_nonexistent_file(tmp_path):
    # Create a temporary file location for testing (nonexistent file)
    file_location = tmp_path / "nonexistent.json"

    # Test reading the configuration from a nonexistent file
    config, success = read_configuration(file_location)

    # Assert that the configuration was not successfully read
    assert success is False

    # Assert that the returned configuration is a new Configuration object
    assert isinstance(config, Configuration)
    assert config == Configuration()


def test_write_configuration(tmp_path, example_configuration):
    # Create a temporary file for testing
    file_location = tmp_path / "config.json"

    # Test writing the configuration
    success = write_configuration(example_configuration, file_location)

    # Assert that the configuration was successfully written
    assert success is True

    # Read the written configuration file
    with open(file_location, "r") as f:
        written_config = json.load(f)

    # Assert that the written configuration matches the example configuration
    assert written_config == example_configuration.model_dump()


def test_reset_configuration(tmp_path, example_configuration):
    # Create a temporary file for testing
    file_location = tmp_path / "config.json"

    # Write the example configuration to the temporary file
    with open(file_location, "w") as f:
        json.dump(example_configuration.model_dump(), f)

    # Test resetting the configuration
    success = reset_configuration(file_location)

    # Assert that the configuration was successfully reset
    assert success is True

    # Read the reset configuration file
    with open(file_location, "r") as f:
        reset_config = json.load(f)

    # Create a new empty Configuration object
    empty_config = Configuration()

    # Assert that the reset configuration matches the empty Configuration object
    assert reset_config == empty_config.model_dump()


def test_get_config_path():
    """Verify get_config_path returns correct OS-specific paths."""

    # Mock expanduser to simulate home directory expansion safely
    def mock_expanduser(path):
        return path.replace("~", "/User/Home")

    # Windows Case
    # We use a simple path string for APPDATA to avoid confusion with drive letters vs root on different OS runners
    mock_appdata = "AppData"
    with patch("sys.platform", "win32"), patch.dict(
        os.environ, {"APPDATA": mock_appdata}
    ), patch("os.path.exists", return_value=True):

        # Expected: AppData/MTGA_Draft_Tool/config.json (separators match runner OS)
        expected = os.path.join(mock_appdata, "MTGA_Draft_Tool", "config.json")
        assert get_config_path() == expected

    # Mac Case
    with patch("sys.platform", "darwin"), patch(
        "os.path.expanduser", side_effect=mock_expanduser
    ), patch("os.path.exists", return_value=True):

        # On Mac logic: expanduser("~/Library/Application Support") -> "/User/Home/Library/Application Support"
        # We assume the runner's os.path.join handles the separators for the runner's OS
        expected = os.path.join(
            "/User/Home/Library/Application Support", "MTGA_Draft_Tool", "config.json"
        )
        assert get_config_path() == expected

    # Linux Case
    with patch("sys.platform", "linux"), patch(
        "os.path.expanduser", side_effect=mock_expanduser
    ), patch("os.path.exists", return_value=True):

        # On Linux logic: expanduser("~/.config") -> "/User/Home/.config"
        expected = os.path.join("/User/Home/.config", "MTGA_Draft_Tool", "config.json")
        assert get_config_path() == expected

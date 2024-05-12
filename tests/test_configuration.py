import pytest
import json
from typing import Tuple
from dataclasses import asdict

# Import the functions to be tested
from src.configuration import (
    read_configuration,
    write_configuration,
    reset_configuration,
    Configuration
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

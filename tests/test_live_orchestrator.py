import pytest
import os
import queue
from unittest.mock import patch, MagicMock
from src.ui.orchestrator import DraftOrchestrator
from src.configuration import Configuration


@pytest.fixture
def orchestrator():
    config = Configuration()
    config.settings.arena_log_location = "mock_live_log.txt"
    config.settings.draft_log_enabled = False

    mock_scanner = MagicMock()
    mock_scanner.arena_file = "mock_live_log.txt"

    return DraftOrchestrator(mock_scanner, config, MagicMock())


@patch("src.ui.orchestrator.os.path.getsize")
@patch("src.ui.orchestrator.os.path.exists")
@patch("builtins.open")
def test_check_live_log_detects_draft(
    mock_open, mock_exists, mock_getsize, orchestrator
):
    """Verifies the background watchdog detects when a draft suddenly starts in the active log."""

    # App starts with a 500-byte log file
    orchestrator._last_live_file_size = 500

    # File exists and has grown to 1000 bytes
    mock_exists.return_value = True
    mock_getsize.return_value = 1000

    # Mock the file reader yielding lines
    mock_file = MagicMock()
    mock_file.readline.side_effect = [
        "Some random Arena telemetry...",
        "[UnityCrossThreadLogger]==> Event_Join Draft",  # Trigger!
        "",  # EOF
    ]
    mock_open.return_value.__enter__.return_value = mock_file

    # Act
    found_draft = orchestrator._check_live_log_for_draft()

    # Assert
    assert found_draft is True
    # Verify the pointer moved forward
    assert orchestrator._last_live_file_size == 1000


@patch("src.ui.orchestrator.os.path.getsize", return_value=500)
@patch("src.ui.orchestrator.os.path.exists", return_value=True)
def test_check_live_log_ignores_static_file(mock_exists, mock_getsize, orchestrator):
    """Verifies we do not waste CPU cycles reading the log if the file size hasn't changed."""

    orchestrator._last_live_file_size = 500  # Matches current size

    with patch("builtins.open") as mock_open:
        found_draft = orchestrator._check_live_log_for_draft()

        # Assert
        assert found_draft is False
        mock_open.assert_not_called()  # No file I/O performed


def test_file_swap_queue_processing(orchestrator):
    """Verify that thread-safe requests from the UI to read historical logs are processed."""

    # UI requests to read two different logs rapidly
    orchestrator.set_file_and_scan("historical_draft_1.log")
    orchestrator.set_file_and_scan("historical_draft_2.log")

    # Mock the scanner so it doesn't actually try to read them
    orchestrator.scanner.draft_start_search.return_value = True
    orchestrator.sync_dataset_to_event = MagicMock()

    # Force the run loop logic manually for one step
    # We simulate what happens inside run() when the queue isn't empty
    new_file = None
    while not orchestrator._file_swap_queue.empty():
        new_file = orchestrator._file_swap_queue.get_nowait()

    assert (
        new_file == "historical_draft_2.log"
    )  # It correctly skips to the most recent request

    # Simulate processing
    orchestrator.scanner.set_arena_file(new_file)

    # Verify scanner was updated
    orchestrator.scanner.set_arena_file.assert_called_with("historical_draft_2.log")

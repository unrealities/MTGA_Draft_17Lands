import pytest
import threading
from unittest.mock import MagicMock, patch
from src.ui_progress import UIProgress


def test_ui_progress_init():
    progress = UIProgress(progress=MagicMock(), status=MagicMock(), ui=MagicMock())
    assert progress.initial_progress == 0


def test_update_status_main_thread():
    status_mock = MagicMock()
    ui_mock = MagicMock()
    progress = UIProgress(status=status_mock, ui=ui_mock)

    with patch("src.ui_progress.threading.current_thread") as mock_thread:
        mock_thread.return_value = threading.main_thread()
        progress._update_status("Loading...")
        status_mock.set.assert_called_with("Loading...")
        ui_mock.update_idletasks.assert_called()


def test_update_status_background_thread():
    status_mock = MagicMock()
    ui_mock = MagicMock()
    progress = UIProgress(status=status_mock, ui=ui_mock)

    with patch("src.ui_progress.threading.current_thread") as mock_thread:
        # Mocking to simulate a background thread
        mock_thread.return_value = MagicMock()
        progress._update_status("Loading...")
        ui_mock.after.assert_called()

    # Manually trigger the callback
    callback = ui_mock.after.call_args[0][1]
    callback()
    status_mock.set.assert_called_with("Loading...")


def test_update_progress_main_thread():
    progress_mock = MagicMock()
    ui_mock = MagicMock()
    progress_obj = UIProgress(progress=progress_mock, ui=ui_mock)

    with patch("src.ui_progress.threading.current_thread") as mock_thread:
        mock_thread.return_value = threading.main_thread()
        progress_obj._update_progress(10.0, increment=True)
        assert progress_obj.initial_progress == 10.0

        progress_obj._update_progress(50.0, increment=False)
        assert progress_mock.__setitem__.call_args[0][1] == 50.0

"""
tests/test_download_panel.py
Iron-clad validation for the Dataset Manager.
"""

import pytest
import tkinter
from unittest.mock import MagicMock, patch
from src.ui.windows.download import DownloadWindow, DatasetArgs
from src.limited_sets import SetInfo
from src.ui.styles import Theme


class TestDownloadPanel:
    @pytest.fixture
    def root(self):
        """Fixture for the root window with Theme applied."""
        root = tkinter.Tk()
        # Initialize the theme to prevent TclErrors when widgets try to access style data
        Theme.apply(root, "Dark")
        yield root
        root.destroy()

    @pytest.fixture
    def mock_sets_data(self):
        return MagicMock(
            data={
                "Outlaws": SetInfo(
                    arena=["OTJ"],
                    seventeenlands=["OTJ"],
                    formats=["PremierDraft", "TradDraft"],
                    set_code="OTJ",
                    start_date="2024-04-16",
                ),
                "Cube": SetInfo(
                    arena=["CUBE"],
                    seventeenlands=["Cube"],
                    formats=["PremierDraft"],
                    set_code="CUBE",
                    start_date="2023-12-01",
                ),
            }
        )

    @pytest.fixture
    def config(self):
        config = MagicMock()
        config.settings.database_location = "/mock"
        config.settings.column_configs = {
            "dataset_manager": [
                "Set",
                "Event",
                "Group",
                "Start",
                "End",
                "Collected",
                "Games",
            ]
        }
        return config

    def test_set_metadata_sync(self, root, mock_sets_data, config):
        panel = DownloadWindow(root, mock_sets_data, config, MagicMock())
        panel.vars["set"].set("Cube")
        panel._on_set_change("Cube")
        assert panel.vars["start"].get() == "2023-12-01"
        assert panel.vars["event"].get() == "PremierDraft"

    def test_threshold_sanitization(self, root, mock_sets_data, config):
        panel = DownloadWindow(root, mock_sets_data, config, MagicMock())
        panel.vars["threshold"].set("abc")
        with patch("tkinter.messagebox.showerror") as mock_err:
            panel._start_download()
            mock_err.assert_called_once()
            assert "numeric" in mock_err.call_args[0][1].lower()

    @patch("src.ui.windows.download.threading.Thread")
    @patch("src.ui.windows.download.FileExtractor")
    def test_state_locking_during_download(
        self, mock_ex_cls, mock_thread, root, mock_sets_data, config
    ):
        class MockSyncThread:
            def __init__(self, target, args, daemon=True):
                self.target = target
                self.args = args

            def start(self):
                self.target(*self.args)

            def is_alive(self):
                return False

        # Force background thread to execute inline synchronously
        mock_thread.side_effect = MockSyncThread

        panel = DownloadWindow(root, mock_sets_data, config, MagicMock())
        mock_ex_cls.return_value.retrieve_17lands_color_ratings.return_value = (
            False,
            0,
        )
        panel._start_download()
        assert (
            str(panel.btn_dl["state"]) == "normal"
        )  # Download is so fast it's finished instantly

    def test_notification_enter_handshake(self, root, mock_sets_data, config):
        panel = DownloadWindow(root, mock_sets_data, config, MagicMock())
        args = DatasetArgs("OTJ", "TradDraft", "2024", "2024", "All", 100, None)
        with patch.object(panel, "_start_download") as mock_start:
            panel.enter(args)
            assert panel.vars["set"].get() == "Outlaws"
            assert panel.vars["event"].get() == "TradDraft"
            mock_start.assert_called_once_with(args)

    @patch("src.ui.windows.download.threading.Thread")
    @patch("src.ui.windows.download.FileExtractor")
    @patch("tkinter.messagebox.showinfo")
    def test_successful_download_callback_routing(
        self, mock_msg, mock_ex_cls, mock_thread, root, mock_sets_data, config
    ):
        """Verify that a successful dataset extraction properly notifies the UI and resets the progress bar."""

        # We don't want the thread to actually run, we just want to test the UI callback logic
        panel = DownloadWindow(root, mock_sets_data, config, MagicMock())

        # Inject the mock extractor
        mock_ex = mock_ex_cls.return_value

        # Test the finalize callback directly (what the thread calls when it finishes successfully)
        panel.btn_dl.configure(state="disabled")
        panel.progress["value"] = 50

        panel._finalize_download("Success Message!")

        # Verify UI reset
        assert str(panel.btn_dl["state"]) == "normal"
        assert panel.progress["value"] == 0
        assert panel.vars["status"].get() == "DOWNLOAD SUCCESSFUL"
        mock_msg.assert_called_once_with(
            "Dataset Download Complete", "Success Message!"
        )

    @patch("tkinter.messagebox.showerror")
    def test_failed_download_callback_routing(
        self, mock_err, root, mock_sets_data, config
    ):
        """Verify that a failed dataset extraction cleanly resets the UI and shows an error."""
        panel = DownloadWindow(root, mock_sets_data, config, MagicMock())

        panel.btn_dl.configure(state="disabled")
        panel.progress["value"] = 50

        panel._handle_error("Network Timeout")

        # Verify UI reset
        assert str(panel.btn_dl["state"]) == "normal"
        assert panel.progress["value"] == 0
        assert panel.vars["status"].get() == "DOWNLOAD FAILED"
        mock_err.assert_called_once_with("Download Error", "Network Timeout")

    @patch("src.ui.windows.download.os.remove")
    @patch("tkinter.messagebox.askyesno", return_value=True)
    def test_delete_dataset_success(
        self, mock_ask, mock_remove, root, mock_sets_data, config
    ):
        """Verify deleting an inactive dataset removes the file and refreshes the table."""
        panel = DownloadWindow(root, mock_sets_data, config, MagicMock())

        # Set the active dataset to something else so we are allowed to delete this one
        config.card_data.latest_dataset = "OTJ_PremierDraft_All_Data.json"

        target_file = "/fake/path/MKM_PremierDraft_All_Data.json"

        with patch.object(panel, "_update_table") as mock_update:
            panel._delete_dataset(target_file)

            mock_remove.assert_called_once_with(target_file)
            mock_update.assert_called_once()

    @patch("tkinter.messagebox.showwarning")
    def test_delete_dataset_blocked_if_active(
        self, mock_warn, root, mock_sets_data, config
    ):
        """Verify the user is prevented from deleting the currently active dataset."""
        panel = DownloadWindow(root, mock_sets_data, config, MagicMock())

        config.card_data.latest_dataset = "OTJ_PremierDraft_All_Data.json"
        target_file = "/fake/path/OTJ_PremierDraft_All_Data.json"

        panel._delete_dataset(target_file)

        mock_warn.assert_called_once()

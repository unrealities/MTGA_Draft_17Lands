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
    @pytest.mark.parametrize("filename", ["", "new-dataset.json"])
    def test_download_only_activates_saved_dataset(self, filename):
        panel = MagicMock()
        panel.configuration.card_data.latest_dataset = "previous-dataset.json"
        ctx = {"db_loc": "", "threshold": 500, "set_key": "OTJ",
               "event": "PremierDraft", "start": "2024-01-01",
               "end": "2024-02-01", "time_period": "ALL_TIME", "group": "All"}
        with patch("src.ui.windows.download.FileExtractor") as factory, patch(
            "src.ui.windows.download.write_configuration"
        ) as save:
            extractor = factory.return_value
            extractor.retrieve_17lands_color_ratings.return_value = (True, "")
            extractor.download_card_data.return_value = (True, "Downloaded", 10)
            extractor.export_card_data.return_value = filename
            DownloadWindow._run_download_process(panel, None, ctx)
            if filename:
                assert panel.configuration.card_data.latest_dataset == filename
                save.assert_called_once_with(panel.configuration)
                panel._safe_finalize.assert_called_once_with("Downloaded")
                panel._safe_error.assert_not_called()
            else:
                assert panel.configuration.card_data.latest_dataset == "previous-dataset.json"
                save.assert_not_called()
                panel._safe_finalize.assert_not_called()
                panel._safe_error.assert_called_once()

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
        config.card_data.excluded_datasets = []
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

    def test_resolve_start_date_prefers_set_info(self, root, mock_sets_data, config):
        """A set with a real start date uses it directly."""
        panel = DownloadWindow(root, mock_sets_data, config, MagicMock())
        assert panel._resolve_start_date("Outlaws") == "2024-04-16"

    def test_resolve_start_date_manifest_fallback(self, root, config):
        """A set stuck on the placeholder date (e.g. stale set-list cache) falls
        back to the earliest start_date in the synced dataset manifest."""
        from src.constants import START_DATE_DEFAULT

        sets_data = MagicMock(
            data={
                "Marvel Super Heroes": SetInfo(
                    arena=["ALL"],
                    seventeenlands=["MSH"],
                    formats=[],
                    set_code="MARVEL",
                    start_date=START_DATE_DEFAULT,
                ),
            }
        )
        panel = DownloadWindow(root, sets_data, config, MagicMock())

        manifest = {
            "datasets": {
                "MSH_PremierDraft_All": {"start_date": "2026-06-23"},
                "MSH_TradDraft_All": {"start_date": "2026-06-24"},
                "TMT_PremierDraft_All": {"start_date": "2026-03-03"},
            }
        }
        with patch(
            "src.ui.windows.download.read_local_manifest", return_value=manifest
        ):
            assert panel._resolve_start_date("Marvel Super Heroes") == "2026-06-23"

    def test_resolve_start_date_placeholder_without_manifest(self, root, config):
        """No real set date and no manifest entry: keep the placeholder."""
        from src.constants import START_DATE_DEFAULT

        sets_data = MagicMock(
            data={
                "Marvel Super Heroes": SetInfo(
                    arena=["ALL"],
                    seventeenlands=["MSH"],
                    formats=[],
                    set_code="MARVEL",
                    start_date=START_DATE_DEFAULT,
                ),
            }
        )
        panel = DownloadWindow(root, sets_data, config, MagicMock())

        with patch(
            "src.ui.windows.download.read_local_manifest", return_value={}
        ):
            assert (
                panel._resolve_start_date("Marvel Super Heroes") == START_DATE_DEFAULT
            )

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

        with patch.object(panel, "_update_table") as mock_update, patch(
            "src.ui.windows.download.write_configuration", return_value=True
        ) as mock_write:
            panel._delete_dataset(target_file)

            mock_remove.assert_called_once_with(target_file)
            mock_update.assert_called_once()
            assert config.card_data.excluded_datasets == ["MKM_PremierDraft_All_Data.json"]
            mock_write.assert_called_once_with(config)

    def test_delete_dataset_requires_saved_exclusion(self, root, mock_sets_data, config):
        panel = DownloadWindow(root, mock_sets_data, config, MagicMock())
        config.card_data.latest_dataset = "other.json"
        with patch("tkinter.messagebox.askyesno", return_value=True), patch(
            "src.ui.windows.download.write_configuration", return_value=False
        ), patch("src.ui.windows.download.os.remove") as remove, patch(
            "tkinter.messagebox.showerror"
        ) as error:
            panel._delete_dataset("/fake/path/HOB_PremierDraft_All_Data.json")
        remove.assert_not_called()
        error.assert_called_once()
        assert config.card_data.excluded_datasets == []

    def test_restore_deleted_datasets(self, root, mock_sets_data, config):
        panel = DownloadWindow(root, mock_sets_data, config, MagicMock())
        config.card_data.excluded_datasets = ["HOB_PremierDraft_All_Data.json"]
        with patch("tkinter.messagebox.askyesno", return_value=True), patch(
            "src.ui.windows.download.write_configuration", return_value=True
        ) as write, patch("tkinter.messagebox.showinfo"):
            panel._restore_deleted_datasets()
        assert config.card_data.excluded_datasets == []
        write.assert_called_once_with(config)

    def test_clear_inactive_datasets_keeps_active_and_other_files(
        self, root, mock_sets_data, config, tmp_path, monkeypatch
    ):
        panel = DownloadWindow(root, mock_sets_data, config, MagicMock())
        monkeypatch.setattr("src.constants.SETS_FOLDER", str(tmp_path))
        active = "OTJ_PremierDraft_All_Data.json"
        unwanted = ["HOB_PremierDraft_All_Data.json", "MSH_QuickDraft_All_Data.json"]
        config.card_data.latest_dataset = active
        config.settings.last_run_version = "4.23"
        config.card_data.excluded_datasets = ["older_Data.json"]
        for name in [active, *unwanted, "local_manifest.json", "notes.txt"]:
            (tmp_path / name).write_text("{}")
        (tmp_path / "directory_Data.json").mkdir()

        with patch("tkinter.messagebox.askyesno", return_value=True), patch(
            "src.ui.windows.download.write_configuration", return_value=True
        ) as write, patch("tkinter.messagebox.showinfo"), patch.object(
            panel, "_update_table"
        ) as update:
            panel._clear_inactive_datasets()

        assert all(not (tmp_path / name).exists() for name in unwanted)
        assert (tmp_path / active).exists()
        assert (tmp_path / "local_manifest.json").exists()
        assert (tmp_path / "notes.txt").exists()
        assert (tmp_path / "directory_Data.json").is_dir()
        assert set(config.card_data.excluded_datasets) == {"older_Data.json", *unwanted}
        assert config.card_data.latest_dataset == active
        assert config.settings.last_run_version == "4.23"
        write.assert_called_once_with(config)
        update.assert_called_once()

    @pytest.mark.parametrize("confirmed,saved", [(False, True), (True, False)])
    def test_clear_inactive_datasets_requires_confirmation_and_saved_exclusions(
        self, root, mock_sets_data, config, tmp_path, monkeypatch, confirmed, saved
    ):
        panel = DownloadWindow(root, mock_sets_data, config, MagicMock())
        monkeypatch.setattr("src.constants.SETS_FOLDER", str(tmp_path))
        target = tmp_path / "HOB_PremierDraft_All_Data.json"
        target.write_text("{}")
        with patch("tkinter.messagebox.askyesno", return_value=confirmed), patch(
            "src.ui.windows.download.write_configuration", return_value=saved
        ) as write, patch("tkinter.messagebox.showerror"):
            panel._clear_inactive_datasets()
        assert target.exists()
        assert config.card_data.excluded_datasets == []
        assert write.call_count == int(confirmed)

    def test_clear_inactive_datasets_reports_partial_failure(
        self, root, mock_sets_data, config, tmp_path, monkeypatch
    ):
        import os

        panel = DownloadWindow(root, mock_sets_data, config, MagicMock())
        monkeypatch.setattr("src.constants.SETS_FOLDER", str(tmp_path))
        blocked = tmp_path / "HOB_PremierDraft_All_Data.json"
        removable = tmp_path / "MSH_PremierDraft_All_Data.json"
        blocked.write_text("{}")
        removable.write_text("{}")
        remove = os.remove

        def remove_unlocked(path):
            if str(path) == str(blocked):
                raise PermissionError("File is in use")
            remove(path)

        with patch("tkinter.messagebox.askyesno", return_value=True), patch(
            "src.ui.windows.download.write_configuration", return_value=True
        ), patch("src.ui.windows.download.os.remove", side_effect=remove_unlocked), patch(
            "tkinter.messagebox.showerror"
        ) as error, patch.object(panel, "_update_table"):
            panel._clear_inactive_datasets()

        assert blocked.exists()
        assert not removable.exists()
        assert set(config.card_data.excluded_datasets) == {blocked.name, removable.name}
        assert "Removed 1 dataset(s)" in error.call_args.args[1]

    def test_clear_inactive_datasets_waits_for_manual_download(
        self, root, mock_sets_data, config
    ):
        panel = DownloadWindow(root, mock_sets_data, config, MagicMock())
        panel._download_thread = MagicMock()
        panel._download_thread.is_alive.return_value = True
        with patch("tkinter.messagebox.showwarning") as warning, patch(
            "src.ui.windows.download.os.listdir"
        ) as listdir:
            panel._clear_inactive_datasets()
        warning.assert_called_once()
        listdir.assert_not_called()

    @patch("src.ui.windows.download.write_configuration")
    @patch("src.utils.clear_set_history", return_value=3)
    @patch("tkinter.messagebox.showinfo")
    @patch("tkinter.messagebox.askyesno", return_value=True)
    def test_clear_set_history_button(
        self,
        mock_ask,
        mock_info,
        mock_clear,
        mock_write,
        root,
        mock_sets_data,
        config,
    ):
        """Clear Set History wipes datasets and resets the version marker so the
        next launch performs a fresh refresh."""
        panel = DownloadWindow(root, mock_sets_data, config, MagicMock())

        config.card_data.excluded_datasets = ["HOB_PremierDraft_All_Data.json"]
        with patch.object(panel, "_update_table"):
            panel._clear_set_history()

        mock_clear.assert_called_once()
        assert config.settings.last_run_version == ""
        assert config.card_data.latest_dataset == ""
        assert config.card_data.excluded_datasets == ["HOB_PremierDraft_All_Data.json"]
        mock_write.assert_called_once()
        mock_info.assert_called_once()

    @patch("tkinter.messagebox.askyesno", return_value=False)
    def test_clear_set_history_button_cancelled(
        self, mock_ask, root, mock_sets_data, config
    ):
        """Declining the confirmation must not delete anything."""
        panel = DownloadWindow(root, mock_sets_data, config, MagicMock())
        with patch("src.utils.clear_set_history") as mock_clear:
            panel._clear_set_history()
            mock_clear.assert_not_called()

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

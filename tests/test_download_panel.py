"""
tests/test_download_panel.py
Iron-clad validation for the Dataset Manager.
"""

import pytest
import tkinter
from unittest.mock import MagicMock, patch
from src.ui.windows.download import DownloadWindow, DatasetArgs
from src.limited_sets import SetInfo


class TestDownloadPanel:
    @pytest.fixture
    def root(self):
        root = tkinter.Tk()
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

    @patch("src.ui.windows.download.FileExtractor")
    def test_state_locking_during_download(
        self, mock_ex_cls, root, mock_sets_data, config
    ):
        panel = DownloadWindow(root, mock_sets_data, config, MagicMock())
        mock_ex_cls.return_value.retrieve_17lands_color_ratings.return_value = (
            False,
            0,
        )
        panel._start_download()
        assert str(panel.btn_dl["state"]) == "normal"

    def test_notification_enter_handshake(self, root, mock_sets_data, config):
        panel = DownloadWindow(root, mock_sets_data, config, MagicMock())
        args = DatasetArgs("OTJ", "TradDraft", "2024", "2024", "All", 100, None)
        with patch.object(panel, "_start_download") as mock_start:
            panel.enter(args)
            assert panel.vars["set"].get() == "Outlaws"
            assert panel.vars["event"].get() == "TradDraft"
            mock_start.assert_called_once_with(args)

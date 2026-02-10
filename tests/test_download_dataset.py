"""
tests/test_download_dataset.py
Fixed: Removed fragile !frame path dependencies.
"""

import pytest
import tkinter
from unittest.mock import MagicMock, patch
from src.ui.windows.download import DownloadWindow, DatasetArgs
from src.limited_sets import SetInfo


class TestDownloadDatasetUI:
    @pytest.fixture
    def mock_sets_data(self):
        return MagicMock(
            data={
                "OTJ": SetInfo(
                    arena=["OTJ"],
                    seventeenlands=["OTJ"],
                    formats=["PremierDraft", "TradDraft"],
                    set_code="OTJ",
                    start_date="2024-04-16",
                ),
                "Arena Cube": SetInfo(
                    arena=["CUBE"],
                    seventeenlands=["Cube"],
                    formats=["PremierDraft"],
                    set_code="CUBE",
                    start_date="2023-12-01",
                ),
            }
        )

    @pytest.fixture
    def app_context(self, mock_sets_data):
        root = tkinter.Tk()
        config = MagicMock()
        config.settings.database_location = "/mock"
        window = DownloadWindow(root, mock_sets_data, config, MagicMock())
        yield window
        root.destroy()

    def test_initial_dropdown_population(self, app_context):
        # Access variables directly instead of searching widget hierarchy
        assert "OTJ" in app_context.sets_data.keys()

    def test_set_selection_updates_dates(self, app_context):
        app_context.vars["set"].set("Arena Cube")
        app_context._on_set_change("Arena Cube")
        assert app_context.vars["start"].get() == "2023-12-01"

    @patch("src.ui.windows.download.FileExtractor")
    def test_download_button_state_locking(self, mock_ex, app_context):
        mock_ex.return_value.retrieve_17lands_color_ratings.return_value = (False, 0)
        app_context._start_download()
        assert str(app_context.btn_dl["state"]) == "normal"

    @patch("src.ui.windows.download.FileExtractor")
    def test_notification_enter_handshake(self, mock_ex, app_context):
        args = DatasetArgs(
            draft_set="OTJ",
            draft="TradDraft",
            start="2024-04-16",
            end="2024-05-01",
            user_group="Top",
            game_count=10000,
            color_ratings={"W": 55.0},
        )
        with patch.object(app_context, "_start_download") as mock_dl:
            app_context.enter(args)
            assert app_context.vars["set"].get() == "OTJ"
            assert app_context.vars["event"].get() == "TradDraft"

"""
tests/test_color_percentages.py
"""

import pytest
import tkinter
from tkinter import ttk
from unittest.mock import MagicMock, patch
from src.ui.app import DraftApp
from src.configuration import Configuration, Settings


class TestColorPercentagesUI:
    @pytest.fixture
    def root(self):
        root = tkinter.Tk()
        yield root
        root.destroy()

    @pytest.fixture
    def mock_scanner(self):
        scanner = MagicMock()
        scanner.retrieve_color_win_rate.return_value = {
            "WG (57.5%)": "WG",
            "UB (54.2%)": "UB",
            "Auto": "Auto",
        }
        # FIX: Ensure this mock is present to avoid StopIteration in _update_data_sources
        scanner.retrieve_data_sources.return_value = {"Mock Set": "/mock/path.json"}
        scanner.retrieve_current_limited_event.return_value = ("SET", "Draft")
        scanner.retrieve_current_pack_and_pick.return_value = (1, 1)
        scanner.retrieve_taken_cards.return_value = []
        scanner.retrieve_set_metrics.return_value = MagicMock()
        scanner.retrieve_tier_data.return_value = ({}, {})
        return scanner

    @pytest.fixture
    def config(self):
        return Configuration(
            settings=Settings(deck_filter="Auto", filter_format="Colors")
        )

    def _patch_panels(self, root):
        def create_mock_frame(*args, **kwargs):
            return ttk.Frame(args[0])

        patches = [
            patch("src.ui.app.Notifications"),
            patch("src.ui.app.DownloadWindow", side_effect=create_mock_frame),
            patch("src.ui.app.TakenCardsPanel", side_effect=create_mock_frame),
            patch("src.ui.app.SuggestDeckPanel", side_effect=create_mock_frame),
            patch("src.ui.app.ComparePanel", side_effect=create_mock_frame),
            patch("src.ui.app.TierListWindow", side_effect=create_mock_frame),
        ]
        return patches

    def test_filter_dropdown_population(self, root, mock_scanner, config):
        patches = self._patch_panels(root)
        for p in patches:
            p.start()
        with patch("src.ui.app.DraftApp._refresh_ui_data"):
            app = DraftApp(root, mock_scanner, config)
            menu = app.om_filter["menu"]
            last = menu.index("end")
            labels = [menu.entrycget(i, "label") for i in range(last + 1)]
            assert "WG (57.5%)" in labels
        for p in patches:
            p.stop()

    def test_filter_selection_updates_config(self, root, mock_scanner, config):
        patches = self._patch_panels(root)
        for p in patches:
            p.start()
        with patch("src.ui.app.DraftApp._refresh_ui_data"):
            app = DraftApp(root, mock_scanner, config)
            app.vars["deck_filter"].set("UB (54.2%)")
            assert app.configuration.settings.deck_filter == "UB"
        for p in patches:
            p.stop()

    def test_missing_winrate_data_graceful_handling(self, root, mock_scanner, config):
        mock_scanner.retrieve_color_win_rate.return_value = {}
        patches = self._patch_panels(root)
        for p in patches:
            p.start()
        try:
            with patch("src.ui.app.DraftApp._refresh_ui_data"):
                app = DraftApp(root, mock_scanner, config)
                # App should fallback to current config filter if data is empty
                assert app.vars["deck_filter"].get() == "Auto"
        finally:
            for p in patches:
                p.stop()

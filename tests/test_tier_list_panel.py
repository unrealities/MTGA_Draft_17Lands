"""
tests/test_tier_list_panel.py
Validation for Tier List UI.
"""

import pytest
import tkinter
from unittest.mock import MagicMock, patch
from src.ui.windows.tier_list import TierListWindow
from src.tier_list import TierList, Meta
from src.configuration import Configuration


class MockSyncThread:
    """Helper to safely execute threaded functions synchronously in tests."""

    def __init__(self, target, args, daemon=True):
        self.target = target
        self.args = args

    def start(self):
        self.target(*self.args)

    def is_alive(self):
        return False


class TestTierListWindow:
    @pytest.fixture
    def root(self):
        root = tkinter.Tk()
        yield root
        root.destroy()

    @pytest.fixture
    def mock_tier_files(self):
        return [
            ("OTJ", "LSV Review", "2024-04-16 12:00:00", "Tier_OTJ_1.txt"),
            ("MKM", "Draftsim", "2024-02-06 08:00:00", "Tier_MKM_2.txt"),
        ]

    def test_history_table_population(self, root, mock_tier_files):
        """Verify existing local tier lists are displayed correctly."""
        with patch(
            "src.tier_list.TierList.retrieve_files", return_value=mock_tier_files
        ):
            panel = TierListWindow(root, Configuration(), MagicMock())
            items = panel.table.get_children()
            assert len(items) == 2
            first_row = panel.table.item(items[0])["values"]
            assert first_row[0] == "OTJ"

    def test_invalid_url_blocking(self, root):
        """Verify non-17Lands URLs are rejected."""
        panel = TierListWindow(root, Configuration(), MagicMock())
        panel.vars["url"].set("https://not-17lands.com/tier_list/abc")

        with patch("tkinter.messagebox.showwarning") as mock_warn:
            panel._start_import()
            mock_warn.assert_called_once()

    @patch("src.ui.windows.tier_list.threading.Thread", new=MockSyncThread)
    @patch("src.tier_list.TierList.from_api")
    def test_successful_import_lifecycle(self, mock_from_api, root):
        """Verify full import updates the UI and notifies the dashboard."""
        callback = MagicMock()
        panel = TierListWindow(root, Configuration(), callback)

        mock_tl = MagicMock(spec=TierList)
        mock_tl.meta = Meta(set="ECL", label="Test")
        mock_from_api.return_value = mock_tl

        panel.vars["url"].set("https://www.17lands.com/tier_list/123")
        panel.vars["label"].set("Pro Review")

        with patch.object(panel, "_update_history_table") as mock_refresh:
            panel._start_import()

            mock_from_api.assert_called_once_with(
                "https://www.17lands.com/tier_list/123"
            )
            mock_tl.to_file.assert_called_once()
            mock_refresh.assert_called_once()
            callback.assert_called_once()
            assert panel.vars["status"].get() == "IMPORT SUCCESSFUL"

    @patch("src.ui.windows.tier_list.threading.Thread", new=MockSyncThread)
    def test_import_error_handling(self, root):
        """Verify UI stability during network/API failures."""
        panel = TierListWindow(root, Configuration(), MagicMock())
        panel.vars["url"].set("https://www.17lands.com/tier_list/fail")
        panel.vars["label"].set("Faulty")

        with patch(
            "src.tier_list.TierList.from_api", side_effect=Exception("API Error")
        ):
            with patch("tkinter.messagebox.showerror") as mock_err:
                panel._start_import()
                mock_err.assert_called_once()
                assert panel.vars["status"].get() == "IMPORT FAILED"
                assert str(panel.btn_import["state"]) == "normal"

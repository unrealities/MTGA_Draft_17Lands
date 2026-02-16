import pytest
import tkinter
from tkinter import ttk
from unittest.mock import MagicMock, patch
from src.ui.app import DraftApp
from src.configuration import Configuration, Settings
from src.ui.styles import Theme


class MockWidget(ttk.Frame):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent)
        self.refresh = MagicMock()
        self.update_pack_data = MagicMock()
        self.update_signals = MagicMock()
        self.update_stats = MagicMock()
        self.enter = MagicMock()
        self.get_treeview = MagicMock()
        self.update_deck_balance = MagicMock()


class TestAppOrchestrator:
    @pytest.fixture
    def root(self):
        root = tkinter.Tk()
        # Initialize theme to prevent style lookups on dead roots from previous tests
        Theme.apply(root, "Dark")
        yield root
        try:
            root.destroy()
        except tkinter.TclError:
            pass

    @pytest.fixture
    def mock_scanner(self):
        scanner = MagicMock()
        scanner.retrieve_data_sources.return_value = {
            "[ECL] PremierDraft (All)": "/mock/path.json"
        }
        scanner.retrieve_color_win_rate.return_value = {"Auto": "Auto", "WG": "WG"}
        scanner.retrieve_current_limited_event.return_value = ("ECL", "PremierDraft")
        scanner.retrieve_current_pack_and_pick.return_value = (1, 1)
        scanner.retrieve_taken_cards.return_value = []
        scanner.retrieve_draft_history.return_value = [
            {"Pack": 1, "Pick": 1, "Cards": ["1"]}
        ]
        scanner.retrieve_set_metrics.return_value.get_metrics.return_value = (55.0, 5.0)
        scanner.retrieve_tier_data.return_value = {}
        scanner.arena_file = "mock.log"
        return scanner

    @pytest.fixture
    def config(self):
        return Configuration(settings=Settings(theme="Dark", deck_filter="Auto"))

    @pytest.fixture
    def ui_patches(self):
        """Standard set of patches for DraftApp UI sub-components."""
        return [
            patch("src.ui.app.DashboardFrame", side_effect=MockWidget),
            patch("src.ui.app.TakenCardsPanel", side_effect=MockWidget),
            patch("src.ui.app.SuggestDeckPanel", side_effect=MockWidget),
            patch("src.ui.app.ComparePanel", side_effect=MockWidget),
            patch("src.ui.app.DownloadWindow", side_effect=MockWidget),
            patch("src.ui.app.TierListWindow", side_effect=MockWidget),
            patch("src.ui.app.Notifications"),
            # CRITICAL: Prevent the infinite update loop from scheduling itself
            patch("src.ui.app.DraftApp._schedule_update"),
        ]

    def test_startup_data_bootstrap(self, root, mock_scanner, config, ui_patches):
        for p in ui_patches:
            p.start()
        try:
            config.card_data.latest_dataset = "path.json"
            app = DraftApp(root, mock_scanner, config)
            assert mock_scanner.retrieve_set_data.called
        finally:
            for p in ui_patches:
                p.stop()

    def test_filter_change_persistence(self, root, mock_scanner, config, ui_patches):
        for p in ui_patches:
            p.start()
        try:
            with patch("src.ui.app.write_configuration") as mock_write:
                app = DraftApp(root, mock_scanner, config)
                app.vars["deck_filter"].set("WG")
                assert app.configuration.settings.deck_filter == "WG"
                assert mock_write.called
        finally:
            for p in ui_patches:
                p.stop()

    def test_export_csv_pipeline(self, root, mock_scanner, config, ui_patches):
        for p in ui_patches:
            p.start()
        try:
            with patch("src.ui.app.messagebox"), patch(
                "src.ui.app.filedialog.asksaveasfile"
            ) as mock_dialog, patch(
                "src.card_logic.export_draft_to_csv"
            ) as mock_export:

                app = DraftApp(root, mock_scanner, config)
                mock_file = MagicMock()
                mock_dialog.return_value = mock_file
                mock_export.return_value = "csv_data"

                app._export_csv()
                assert mock_export.called
                mock_file.write.assert_called_with("csv_data")
                assert mock_file.__enter__.called
        finally:
            for p in ui_patches:
                p.stop()

    def test_notification_tab_switch(self, root, mock_scanner, config, ui_patches):
        """Verify UI tab switching via virtual events."""
        for p in ui_patches:
            p.start()
        try:
            app = DraftApp(root, mock_scanner, config)

            # Generation of event
            app.root.event_generate("<<ShowDataTab>>")
            app.root.update()

            # Current index should be 3 (Dataset Manager)
            assert app.notebook.index("current") == 3
        finally:
            for p in ui_patches:
                p.stop()

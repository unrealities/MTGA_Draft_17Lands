import pytest
import json
import tkinter
from unittest.mock import MagicMock, patch
from src.configuration import Configuration, Settings, Features
from src.overlay import Overlay
from src import constants

def test_dropdown_percentage_mapping_order_invariance(tmp_path):
    # 1. Setup mock data
    dummy_cards = {
        str(i): {"name": f"c{i}", "deck_colors": {"All Decks": {"gihwr": 0.0}}}
        for i in range(101)
    }
    mock_data = {
        "meta": {"version": 2, "start_date": "2024-01-01", "end_date": "2024-01-02"},
        "color_ratings": {"GW": 57.7, "RW": 55.0},
        "card_ratings": dummy_cards,
    }
    data_file = tmp_path / "test_set_Data.json"
    with open(data_file, "w") as f:
        json.dump(mock_data, f)

    # 2. Setup UI environment
    root = tkinter.Tk()
    
    try:
        conf = Configuration(
            settings=Settings(filter_format="Colors", ui_size="100%"),
            features=Features(hotkey_enabled=False),
        )

        # Mock side effect to set OS config without loading Tcl themes
        def mock_set_os_config(self):
            self.scale_factor = 1.0
            self.fonts_dict = {
                "All.TMenubutton": (constants.FONT_SANS_SERIF, 10),
                "All.TableRow": 10,
                "Sets.TableRow": 10
            }

        with patch("src.overlay.read_configuration", return_value=(conf, True)), \
             patch("src.overlay.LimitedSets.retrieve_limited_sets"), \
             patch("os.path.getsize", return_value=1000), \
             patch("src.overlay.stat") as mock_stat, \
             patch("src.overlay.search_arena_log_locations", return_value="fake.log"), \
             patch("src.overlay.ArenaScanner") as mock_scanner_cls, \
             patch("builtins.input", side_effect=Exception("Blocking Input Detected!")), \
             patch("tkinter.messagebox.askyesno", return_value=False), \
             patch("tkinter.messagebox.showinfo"), \
             patch("src.overlay.Notifications") as mock_notifications, \
             patch("src.overlay.tkinter.Tk", return_value=root), \
             patch("src.overlay.Listener"), \
             patch.object(Overlay, '_Overlay__set_os_configuration', side_effect=mock_set_os_config, autospec=True):

            # Scope stat patch
            mock_stat.return_value.st_mtime = 1000
            
            # Prevent network calls
            mock_notifications.return_value.check_for_updates.return_value = False

            # Configure ArenaScanner
            mock_scanner_instance = mock_scanner_cls.return_value
            mock_scanner_instance.step_through = False
            mock_scanner_instance.retrieve_current_pack_and_pick.return_value = (1, 1)
            mock_scanner_instance.retrieve_current_limited_event.return_value = ("TEST_SET", "PremierDraft")
            mock_scanner_instance.retrieve_data_sources.return_value = {"Source": str(data_file)}
            mock_scanner_instance.retrieve_taken_cards.return_value = []
            mock_scanner_instance.retrieve_current_pack_cards.return_value = []
            mock_scanner_instance.retrieve_current_picked_cards.return_value = []
            mock_scanner_instance.retrieve_current_missing_cards.return_value = []
            mock_scanner_instance.retrieve_set_metrics.return_value = MagicMock()
            
            # Mock win rates with correct structure {Label: ID}
            expected_deck_colors = {
                "GW (57.7%)": "GW",
                "RW (55.0%)": "RW",
                "All Decks": "All Decks",
                "Auto": "Auto"
            }
            mock_scanner_instance.retrieve_color_win_rate.return_value = expected_deck_colors

            # Initialize app
            app = Overlay(MagicMock(file="fake.log", data=None, step=False))

            # Trigger manual data update
            app.data_source_selection.set("Source")
            app._Overlay__update_draft_data()
            app._Overlay__update_column_options()
            
            # Force UI update
            root.update()

            # 3. Verify labels
            menu = app.deck_colors_options["menu"]
            labels = []
            
            last_index = menu.index('end')
            if last_index is not None:
                for i in range(last_index + 1):
                    labels.append(menu.entrycget(i, "label"))

            assert "GW (57.7%)" in labels
            assert "RW (55.0%)" in labels

    finally:
        try:
            if 'app' in locals() and hasattr(app, 'close_overlay'):
                app.close_overlay()
        except tkinter.TclError:
            pass
        
        try:
            root.destroy()
        except tkinter.TclError:
            pass

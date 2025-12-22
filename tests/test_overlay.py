import pytest
import logging
from unittest.mock import MagicMock, patch
from src.overlay import Overlay, start_overlay
from src.configuration import Configuration
from src import constants   


@pytest.fixture(autouse=True)
def catch_log_errors(caplog):
    """
    Verify that the app is not generating any logging errors.

    This function catches any logging errors in the app by checking log records.
    """
    yield
    errors = [
        record
        for record in caplog.get_records("call")
        if record.levelno >= logging.ERROR
    ]
    assert (
        not errors
    ), f"Log error detected - resolve any errors that appear in the captured log call"


@pytest.fixture(name="mock_scanner")
def fixture_mock_scanner():
    """
    Mock the ArenaScanner class and all of its methods within overlay.py.
    """
    mock_instance = MagicMock()
    mock_instance.retrieve_color_win_rate.return_value = {"Auto": 0.0}
    mock_instance.retrieve_data_sources.return_value = {"None": ""}
    mock_instance.retrieve_tier_source.return_value = []
    mock_instance.retrieve_set_metrics.return_value = None
    mock_instance.retrieve_tier_data.return_value = ({}, {})
    mock_instance.draft_start_search.return_value = False
    mock_instance.retrieve_current_pack_and_pick.return_value = (0, 0)
    mock_instance.retrieve_current_limited_event.return_value = ("", "")
    yield mock_instance


def test_start_overlay_pass(mock_scanner):
    """
    Verify that the app starts up without generating exceptions or logging errors.

    - Mock the mainloop function to exit the overlay after startup.
    - Mock AppUpdate and messagebox to prevent prompt windows from opening and blocking the test.
    - Mock functions interacting with external files as those files aren't available to Github runners.
    """
    with (
        patch("tkinter.Tk.mainloop", return_value=None),
        patch("tkinter.messagebox.showinfo", return_value=None),
        patch("src.overlay.stat", return_value=MagicMock(st_mtime=0)),
        patch("src.overlay.write_configuration", return_value=True),
        patch("src.overlay.read_configuration", return_value=(Configuration(), True)),
        patch("src.overlay.LimitedSets.retrieve_limited_sets", return_value=None),
        patch("src.overlay.Notifications.check_for_updates", return_value=("", "")),
        patch("src.overlay.ArenaScanner", return_value=mock_scanner),
        patch("src.overlay.filter_options", return_value=["All Decks"]),
        patch("src.overlay.retrieve_arena_directory", return_value="fake_location"),
        patch("src.overlay.search_arena_log_locations", return_value="fake_location"),
    ):
        try:
            start_overlay()
        except Exception as e:
            pytest.fail(f"Exception occurred: {e}")


def test_update_pack_table_filters_lands_and_ids(mock_scanner):
    """
    Verify that __update_pack_table hides basic lands and numeric IDs from the UI treeview.
    """
    with (
        patch("tkinter.Tk.mainloop", return_value=None),
        patch("src.overlay.stat", return_value=MagicMock(st_mtime=0)),
        patch("src.overlay.write_configuration", return_value=True),
        patch("src.overlay.read_configuration", return_value=(Configuration(), True)),
        patch("src.overlay.LimitedSets.retrieve_limited_sets", return_value=None),
        patch("src.overlay.Notifications.check_for_updates", return_value=("", "")),
        patch("src.overlay.ArenaScanner", return_value=mock_scanner),
        patch("src.overlay.filter_options", return_value=["All Decks"]),
        patch("src.overlay.retrieve_arena_directory", return_value="fake_location"),
        patch("src.overlay.search_arena_log_locations", return_value="fake_location"),
    ):
        app = Overlay(MagicMock(file="fake.log", data=None, step=False))

        # Setup Mock Data
        # 1. Valid Card
        card_valid = {
            constants.DATA_FIELD_NAME: "Valid Card",
            constants.DATA_FIELD_COLORS: ["W"],
            constants.DATA_FIELD_TYPES: ["Creature"],
            constants.DATA_FIELD_CMC: 2,
            constants.DATA_FIELD_MANA_COST: "{1}{W}",
            constants.DATA_FIELD_DECK_COLORS: {
                "All Decks": {
                    constants.DATA_FIELD_GIHWR: 55.0,
                    constants.DATA_FIELD_ALSA: 2.0,
                }
            },
        }

        # 2. Basic Land
        card_land = {
            constants.DATA_FIELD_NAME: "Plains",  # In BASIC_LANDS
            constants.DATA_FIELD_COLORS: ["W"],
            constants.DATA_FIELD_TYPES: ["Land"],
            constants.DATA_FIELD_CMC: 0,
            constants.DATA_FIELD_MANA_COST: "",
            constants.DATA_FIELD_DECK_COLORS: {},
        }

        # 3. Numeric ID (Unknown Card)
        card_unknown = {
            constants.DATA_FIELD_NAME: "12345",  # digit string
            constants.DATA_FIELD_COLORS: [],
            constants.DATA_FIELD_TYPES: [],
            constants.DATA_FIELD_CMC: 0,
            constants.DATA_FIELD_MANA_COST: "",
            constants.DATA_FIELD_DECK_COLORS: {},
        }

        input_list = [card_valid, card_land, card_unknown]

        # Mock Fields
        fields = {
            "Column1": constants.DATA_FIELD_NAME,
            "Column2": constants.DATA_FIELD_GIHWR,
        }

        # Call method
        app._Overlay__update_pack_table(input_list, ["All Decks"], fields)

        # Assertions
        # Check Treeview children count
        children = app.pack_table.get_children()
        assert len(children) == 1

        # Verify content of the single row
        row_values = app.pack_table.item(children[0])["values"]
        assert row_values[0] == "Valid Card"

def test_signal_table_visibility_toggle(mock_scanner):
    """
    Verify that the 'Enable Signals' setting correctly toggles the visibility of the signal frame.
    """
    with (
        patch("tkinter.Tk.mainloop", return_value=None),
        patch("tkinter.messagebox.showinfo", return_value=None),
        patch("src.overlay.stat", return_value=MagicMock(st_mtime=0)),
        patch("src.overlay.write_configuration", return_value=True),
        patch("src.overlay.read_configuration", return_value=(Configuration(), True)),
        patch("src.overlay.LimitedSets.retrieve_limited_sets", return_value=None),
        patch("src.overlay.Notifications.check_for_updates", return_value=("", "")),
        patch("src.overlay.ArenaScanner", return_value=mock_scanner),
        patch("src.overlay.filter_options", return_value=["All Decks"]),
        patch("src.overlay.retrieve_arena_directory", return_value="fake_location"),
        patch("src.overlay.search_arena_log_locations", return_value="fake_location"),
    ):
        app = Overlay(MagicMock(file="fake.log", data=None, step=False))
        
        # Mock the toggle_widget function to track calls instead of checking grid info directly
        # because grid_info requires the mainloop to process geometry managers sometimes
        with patch("src.overlay.toggle_widget") as mock_toggle:
            
            # 1. Enable Signals
            app.signals_checkbox_value.set(1) # True
            
            # Manually trigger display update (normally triggered by trace)
            # Since trace is hard to test with mocks, we call the method directly
            app._Overlay__display_widgets()
            
            # Verify toggle_widget was called for signal_frame with True
            # toggle_widget(widget, enable)
            # Check calls
            found_enable = False
            for call in mock_toggle.call_args_list:
                if call[0][0] == app.signal_frame and call[0][1] == True:
                    found_enable = True
                    break
            assert found_enable, "Signal frame should be enabled"

            # 2. Disable Signals
            mock_toggle.reset_mock()
            app.signals_checkbox_value.set(0) # False
            app._Overlay__display_widgets()
            
            found_disable = False
            for call in mock_toggle.call_args_list:
                if call[0][0] == app.signal_frame and call[0][1] == False:
                    found_disable = True
                    break
            assert found_disable, "Signal frame should be disabled"

# TODO: create a test for CreateCardToolTip

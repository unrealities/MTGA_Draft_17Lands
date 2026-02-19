"""
tests/test_settings.py
Validation for the Preferences (Settings) UI.
Updated to match the Pro UI schema (dynamic columns, no fixed column_X dropdowns).
"""

import pytest
import tkinter
from unittest.mock import MagicMock, patch
from src.ui.windows.settings import SettingsWindow
from src.configuration import Configuration, Settings
from src import constants
from src.ui.styles import Theme  # Ensure Theme is initialized


class TestSettingsWindow:
    @pytest.fixture
    def root(self):
        root = tkinter.Tk()
        Theme.apply(root, "Dark")  # Apply theme to prevent style errors
        yield root
        root.destroy()

    @pytest.fixture
    def config(self):
        return Configuration(
            settings=Settings(
                stats_enabled=True,
                result_format=constants.RESULT_FORMAT_WIN_RATE,
            )
        )

    def test_initial_ui_loading(self, root, config):
        """Verify the UI elements reflect the provided configuration."""
        window = SettingsWindow(root, config, MagicMock())

        # Check that string values match config
        assert window.vars["result_format"].get() == constants.RESULT_FORMAT_WIN_RATE
        assert window.vars["filter_format"].get() == constants.DECK_FILTER_FORMAT_COLORS
        assert window.vars["ui_size"].get() == constants.UI_SIZE_DEFAULT

        # Check integer conversion for booleans (True -> 1)
        assert window.vars["signals_enabled"].get() == 1
        assert window.vars["draft_log_enabled"].get() == 1  # Default is True

    @patch("src.ui.windows.settings.write_configuration")
    def test_dropdown_change_persists(self, mock_write, root, config):
        """Verify changing a dropdown updates the config object and writes to disk."""
        callback = MagicMock()
        window = SettingsWindow(root, config, callback)

        # Simulate changing Result Format
        new_format = constants.RESULT_FORMAT_GRADE
        window.vars["result_format"].set(new_format)

        assert config.settings.result_format == new_format
        assert mock_write.called
        # result_format doesn't necessarily trigger callback immediately unless bound,
        # but in SettingsWindow._on_setting_changed it does call callback if present.
        # However, result_format might handle things differently or just trigger write.
        # Let's check if on_update_callback is called.
        # In SettingsWindow._on_setting_changed:
        #   if self.on_update_callback: self.on_update_callback()
        assert callback.called

    @patch("src.ui.windows.settings.write_configuration")
    def test_checkbox_toggle_persists(self, mock_write, root, config):
        """Verify toggling a feature updates the config boolean."""
        window = SettingsWindow(root, config, MagicMock())

        # Simulate unchecking 'Enable Tactical Advisor'
        window.vars["stats_enabled"].set(0)

        assert config.settings.stats_enabled is False
        assert mock_write.called

    @patch("src.ui.windows.settings.reset_configuration")
    def test_reset_defaults_flow(self, mock_reset, root, config):
        """Verify the reset button triggers logic and reloads the UI correctly."""
        window = SettingsWindow(root, config, MagicMock())

        # Config to simulate "Factory Defaults"
        default_config = Configuration()
        # Ensure default has a known state for a field we can check, e.g. stats_enabled=False default?
        # Actually default Configuration() has stats_enabled=False in the provided Pydantic model?
        # Let's check Configuration model in src/configuration.py:
        # stats_enabled: bool = False

        with patch("tkinter.messagebox.askyesno", return_value=True):
            with patch("src.configuration.read_configuration") as mock_read:
                mock_read.return_value = (default_config, True)

                # Set current state to something non-default first
                window.vars["signals_enabled"].set(0)  # False (default is True)

                window._reset_defaults()

                assert mock_reset.called
                # Should be back to 1 (True) per default config
                assert window.vars["signals_enabled"].get() == 1

    def test_safe_closure_cleanup(self, root, config):
        """Verify traces are removed on close."""
        window = SettingsWindow(root, config, MagicMock())
        window._on_close()
        assert len(window.trace_ids) == 0

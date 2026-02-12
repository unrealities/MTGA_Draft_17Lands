"""
tests/test_settings.py
Validation for the Preferences (Settings) UI.
"""

import pytest
import tkinter
from unittest.mock import MagicMock, patch
from src.ui.windows.settings import SettingsWindow
from src.configuration import Configuration, Settings
from src import constants


class TestSettingsWindow:
    @pytest.fixture
    def root(self):
        root = tkinter.Tk()
        yield root
        root.destroy()

    @pytest.fixture
    def config(self):
        return Configuration(
            settings=Settings(
                column_2=constants.DATA_FIELD_GIHWR,
                stats_enabled=True,
                result_format="Percentage",
            )
        )

    def test_initial_ui_loading(self, root, config):
        """Verify the UI elements reflect the provided configuration."""
        window = SettingsWindow(root, config, MagicMock())

        # Check Column 2 dropdown matches the full label constant
        assert window.vars["column_2"].get() == constants.FIELD_LABEL_GIHWR
        assert window.vars["stats_enabled"].get() == 1
        assert window.vars["result_format"].get() == "Percentage"

    @patch("src.ui.windows.settings.write_configuration")
    def test_dropdown_change_persists(self, mock_write, root, config):
        """Verify changing a dropdown updates the config object and writes to disk."""
        callback = MagicMock()
        window = SettingsWindow(root, config, callback)

        # Simulate selecting "ALSA"
        alsa_label = constants.FIELD_LABEL_ALSA
        window.vars["column_2"].set(alsa_label)

        assert config.settings.column_2 == constants.DATA_FIELD_ALSA
        assert mock_write.called
        assert callback.called

    @patch("src.ui.windows.settings.write_configuration")
    def test_checkbox_toggle_persists(self, mock_write, root, config):
        """Verify toggling a feature updates the config boolean."""
        window = SettingsWindow(root, config, MagicMock())
        window.vars["stats_enabled"].set(0)

        assert config.settings.stats_enabled is False
        assert mock_write.called

    @patch("src.ui.windows.settings.reset_configuration")
    def test_reset_defaults_flow(self, mock_reset, root, config):
        """Verify the reset button triggers logic and reloads the UI correctly."""
        window = SettingsWindow(root, config, MagicMock())

        with patch("tkinter.messagebox.askyesno", return_value=True):
            with patch("src.configuration.read_configuration") as mock_read:
                # Mock a "Default" configuration response with a disabled column
                default_config = Configuration(
                    settings=Settings(column_2=constants.DATA_FIELD_DISABLED)
                )
                mock_read.return_value = (default_config, True)

                window._reset_defaults()

                assert mock_reset.called
                assert window.vars["column_2"].get() == constants.FIELD_LABEL_DISABLED

    def test_safe_closure_cleanup(self, root, config):
        """Verify traces are removed on close."""
        window = SettingsWindow(root, config, MagicMock())
        window._on_close()
        assert len(window.trace_ids) == 0

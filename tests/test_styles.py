"""
tests/test_styles.py
Testing for the Dynamic Styling Engine.
"""

import pytest
from unittest.mock import MagicMock, patch
import sys
from importlib import reload
from src.ui.styles import Theme


class TestThemeEngine:
    @pytest.fixture
    def mock_root(self):
        """A mocked root window that mimics the Tkinter interface."""
        root = MagicMock()
        root.tk = MagicMock()
        root.winfo_class.return_value = "Tk"
        root.winfo_children.return_value = []
        return root

    @pytest.fixture
    def mock_style(self):
        """Patches ttk.Style so it doesn't attempt to contact a real Tcl interpreter."""
        with patch("src.ui.styles.ttk.Style") as mock:
            yield mock.return_value

    def test_palette_registry_completeness(self):
        """Verify all standard MTG land themes are present and have required files."""
        expected_themes = [
            "Dark",
            "Light",
            "Forest",
            "Island",
            "Plains",
            "Swamp",
            "Mountain",
            "Wastes",
        ]
        for theme in expected_themes:
            assert theme in Theme.PALETTES
            assert "bg" in Theme.PALETTES[theme]

    def test_theme_application_updates_class_variables(self, mock_root, mock_style):
        """
        Verify that calling apply() updates the class-level constants
        used by other UI components.
        """
        Theme.apply(mock_root, "Forest")
        assert Theme.BG_PRIMARY == "#cbd9c7"
        assert Theme.ACCENT == "#2e7d32"
        assert Theme.TEXT_MAIN == "#1a2f1c"

        Theme.apply(mock_root, "Island")
        assert Theme.BG_PRIMARY == "#c1d7e9"
        assert Theme.ACCENT == "#0077b6"

    def test_invalid_theme_fallback(self, mock_root, mock_style):
        """Edge Case: Verify that an invalid theme name defaults to 'Dark' gracefully."""
        Theme.apply(mock_root, "NonExistentTheme")
        assert Theme.BG_PRIMARY == "#1e1e1e"
        assert Theme.ACCENT == "#4dabff"

    def test_widget_density_configuration(self, mock_root, mock_style):
        """
        Verify that critical layout settings (like rowheight) are
        properly configured in the ttk.Style engine.
        """
        Theme.apply(mock_root, "Dark")
        treeview_config_calls = [
            call
            for call in mock_style.configure.call_args_list
            if call[0][0] == "Treeview"
        ]
        assert len(treeview_config_calls) > 0
        assert treeview_config_calls[0][1]["rowheight"] == 22

    def test_live_update_trigger(self, mock_root, mock_style):
        """Verify that applying a theme triggers the virtual event for live updates."""
        Theme.apply(mock_root, "Forest")
        mock_root.event_generate.assert_any_call("<<ThemeChanged>>")

    @patch("sys.platform", "darwin")
    def test_macos_font_stability(self):
        import src.ui.styles

        reload(src.ui.styles)
        assert src.ui.styles.Theme.FONT_FAMILY == "Verdana"

    @patch("sys.platform", "win32")
    def test_windows_font_stability(self):
        import src.ui.styles

        reload(src.ui.styles)
        assert src.ui.styles.Theme.FONT_FAMILY == "Segoe UI"

    def test_tcl_source_call_logic(self, mock_root, mock_style):
        with patch("os.path.exists", return_value=True):
            Theme.apply(mock_root, "Custom", custom_path="custom.tcl")
        source_calls = [
            call for call in mock_root.tk.call.call_args_list if call[0][0] == "source"
        ]
        assert len(source_calls) > 0
        assert "custom.tcl" in source_calls[0][0][1]

    def test_root_background_is_updated(self, mock_root, mock_style):
        """Ensures the root window background is updated to match the theme."""
        Theme.apply(mock_root, "Dark")

        mock_root.configure.assert_any_call(bg=Theme.BG_PRIMARY)

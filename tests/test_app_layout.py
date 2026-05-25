import pytest
import tkinter
from unittest.mock import MagicMock, patch
from src.ui.app_layout import AppLayoutManager
from src.configuration import Configuration
from src.ui.styles import Theme


class TestAppLayoutManager:
    @pytest.fixture
    def root(self):
        root = tkinter.Tk()
        Theme.apply(root, "Dark")
        yield root
        root.destroy()

    @pytest.fixture
    def mock_app(self, root):
        app = MagicMock()
        app.root = root
        app.configuration = Configuration()

        # Mock sub-components
        app.interactions = MagicMock()
        app.orchestrator = MagicMock()
        return app

    def test_build_layout_initialization(self, mock_app):
        """Verify the layout manager constructs the core UI shell without crashing."""
        layout = AppLayoutManager(mock_app)
        layout.build()

        # Verify containers exist
        assert layout.main_container is not None
        assert layout.splitter is not None
        assert layout.notebook is not None
        assert layout.dashboard is not None

        # Verify panels are injected into the notebook
        assert len(layout.notebook.tabs()) == 6

    def test_toggle_tabs_visibility(self, mock_app):
        """Verify that clicking 'Hide Tabs' collapses the lower pane correctly."""
        layout = AppLayoutManager(mock_app)
        layout.build()

        assert layout.tabs_visible is True

        # Hide tabs
        layout.toggle_tabs()
        assert layout.tabs_visible is False
        assert "Show Tabs" in layout.btn_toggle_tabs.cget("text")

        # Show tabs again
        layout.toggle_tabs()
        assert layout.tabs_visible is True
        assert "Hide Tabs" in layout.btn_toggle_tabs.cget("text")

    def test_ensure_tabs_visible(self, mock_app):
        """Verify the defensive method guarantees tabs are shown."""
        layout = AppLayoutManager(mock_app)
        layout.build()

        layout.toggle_tabs()  # Hide them
        assert layout.tabs_visible is False

        layout.ensure_tabs_visible()  # Force them back
        assert layout.tabs_visible is True

    @patch("src.ui.app_layout.Theme.scaled_val", side_effect=lambda x: x)
    def test_save_and_restore_window_state(self, mock_scale, mock_app):
        """Verify custom geometries and sash positions are saved and restored."""
        layout = AppLayoutManager(mock_app)
        layout.build()

        # Mock the Tkinter state to pretend the window is fully visible and resized
        mock_app.root.state = MagicMock(return_value="normal")
        mock_app.root.geometry = MagicMock(return_value="1400x900+10+10")
        layout.splitter.sashpos = MagicMock(return_value=600)

        # Simulate saving
        layout.save_window_state()
        assert "1400x900" in mock_app.configuration.settings.main_window_geometry
        assert mock_app.configuration.settings.paned_window_sash == 600

        # Simulate restoring state on a fresh boot
        with patch.object(mock_app.root, "after") as mock_after:
            layout.restore_window_state()

            # The geometry should be applied immediately
            assert "1400x900" in mock_app.root.geometry()

            # The sash restoration is deferred via `after` to allow Tkinter to render.
            # We assert that `after` was called with the apply_sashes function.
            assert mock_after.call_count >= 2

            # Extract and execute the delayed function manually to test it
            apply_func = mock_after.call_args_list[0][0][1]
            layout.splitter.sashpos = MagicMock()
            apply_func()
            layout.splitter.sashpos.assert_called_with(0, 600)

    def test_session_info_updates_cleanly(self, mock_app):
        """Verify the bottom metadata text updates correctly and handles None."""
        layout = AppLayoutManager(mock_app)
        layout.build()

        layout.update_session_info("PremierDraft_OTJ", "uuid-1234", "10:00:00")
        text = layout.lbl_session_info.cget("text")

        assert "PremierDraft_OTJ" in text
        assert "uuid-1234" in text
        assert "10:00:00" in text

        # Test handling of missing data
        layout.update_session_info(None, None, None)
        assert layout.lbl_session_info.cget("text") == ""

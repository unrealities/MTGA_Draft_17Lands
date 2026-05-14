# tests/test_sealed_studio.py
import pytest
import tkinter
from unittest.mock import MagicMock, patch
from src.ui.windows.sealed_studio import SealedStudioWindow
from src.configuration import Configuration
from src.ui.styles import Theme
from src.constants import DATA_FIELD_NAME


class TestSealedStudio:
    @pytest.fixture
    def root(self):
        root = tkinter.Tk()
        Theme.apply(root, "Dark")
        yield root
        root.destroy()

    @pytest.fixture
    def mock_app_context(self):
        context = MagicMock()
        context.orchestrator.scanner.current_draft_id = "test_sealed_123"

        # Configure the orchestrator to return valid math metrics so the AI engine doesn't crash
        mock_metrics = MagicMock()
        mock_metrics.get_metrics.return_value = (55.0, 3.0)
        context.orchestrator.scanner.retrieve_set_metrics.return_value = mock_metrics
        context.orchestrator.scanner.retrieve_tier_data.return_value = {}

        return context

    @pytest.fixture
    def mock_pool(self):
        return [
            {DATA_FIELD_NAME: "Plains", "types": ["Land", "Basic"], "count": 5},
            {
                DATA_FIELD_NAME: "Grizzly Bears",
                "types": ["Creature"],
                "cmc": 2,
                "colors": ["G"],
                "count": 2,
            },
            {
                DATA_FIELD_NAME: "Shock",
                "types": ["Instant"],
                "cmc": 1,
                "colors": ["R"],
                "count": 1,
            },
        ]

    def test_initialization_and_auto_shell(self, root, mock_app_context, mock_pool):
        """Verify the Sealed Studio boots up, parses the pool, and auto-generates shells."""
        mock_metrics = MagicMock()
        mock_metrics.get_metrics.return_value = (55.0, 3.0)

        # The engine requires at least 40 cards to mathematically generate shells safely
        for i in range(40):
            mock_pool.append(
                {
                    "name": f"Test Card {i}",
                    "colors": ["R"],
                    "cmc": 2,
                    "types": ["Creature"],
                    "deck_colors": {"All Decks": {"gihwr": 55.0}},
                }
            )

        # Disable the thread pool executor to make image loading synchronous and avoid lingering threads
        with patch("src.ui.windows.sealed_studio.ThreadPoolExecutor") as mock_exec:
            studio = SealedStudioWindow(
                root, mock_app_context, Configuration(), mock_pool, mock_metrics
            )

            # Explicitly trigger the auto-generate action
            studio._on_auto_generate()

            # Auto-generate should have created variants
            assert len(studio.session.variants) > 1

            # The active deck should be populated
            main_deck, sb = studio.session.get_active_deck_lists()
            assert len(main_deck) > 0 or len(sb) > 0

            # Verify UI toggle
            assert studio.view_mode == "visual"
            studio._toggle_view()
            assert studio.view_mode == "list"

    def test_filter_interactions(self, root, mock_app_context, mock_pool):
        """Verify that unchecking filter boxes removes cards from the pool views."""
        with patch("src.ui.windows.sealed_studio.ThreadPoolExecutor"):
            studio = SealedStudioWindow(
                root, mock_app_context, Configuration(), mock_pool, MagicMock()
            )

            # Move all cards to sideboard to test pool filtering
            studio._clear_deck()
            _, sb = studio.session.get_active_deck_lists()
            assert any(c["name"] == "Shock" for c in sb)

            # Uncheck spells
            studio.filter_vars["spells"].set(0)
            studio._refresh_data()

            # Shock should be gone from the Treeview (List Mode)
            # Switch to list mode to check the treeview
            studio.view_mode = "list"
            studio._apply_view_mode()
            studio._refresh_data()

            tree = studio.pool_manager.tree
            rows = tree.get_children()
            names = [tree.item(r)["values"][0] for r in rows]
            assert "Shock" not in names
            assert "Grizzly Bears" in names  # Creatures still checked

    def test_add_basic_lands_ui(self, root, mock_app_context, mock_pool):
        """Verify the basic land buttons inject lands into the active variant."""
        with patch("src.ui.windows.sealed_studio.ThreadPoolExecutor"):
            studio = SealedStudioWindow(
                root, mock_app_context, Configuration(), mock_pool, MagicMock()
            )

            # Clear everything
            studio._clear_deck()

            # Click the 'Mountain' button
            studio._add_basic("Mountain")

            main_deck, _ = studio.session.get_active_deck_lists()
            mountains = [c for c in main_deck if c["name"] == "Mountain"]

            assert len(mountains) == 1
            assert mountains[0]["count"] == 1

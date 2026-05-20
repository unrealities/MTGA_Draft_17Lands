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

    def test_list_mode_drag_and_drop(self, root, mock_app_context, mock_pool):
        with patch("src.ui.windows.sealed_studio.ThreadPoolExecutor"):
            studio = SealedStudioWindow(
                root, mock_app_context, Configuration(), mock_pool, MagicMock()
            )

            # Start drag
            studio._drag_data = {"name": "Shock", "x": 10, "y": 10, "is_pool": True}

            class MockEvent:
                x_root = 100
                y_root = 100

            # Mock coordinate check
            with (
                patch.object(studio.deck_manager, "winfo_rootx", return_value=50),
                patch.object(studio.deck_manager, "winfo_rooty", return_value=50),
                patch.object(studio.deck_manager, "winfo_width", return_value=200),
                patch.object(studio.deck_manager, "winfo_height", return_value=200),
            ):
                studio._on_list_drag_release(
                    MockEvent(), studio.pool_manager.tree, is_pool=True
                )

            # Shock should be moved from pool to main
            main, sb = studio.session.get_active_deck_lists()
            assert any(c["name"] == "Shock" for c in main)
            assert not any(c["name"] == "Shock" for c in sb)

    def test_canvas_mode_double_click(self, root, mock_app_context, mock_pool):
        with patch("src.ui.windows.sealed_studio.ThreadPoolExecutor"):
            studio = SealedStudioWindow(
                root, mock_app_context, Configuration(), mock_pool, MagicMock()
            )

            # Mock canvas identifying the card
            studio.pool_canvas.find_withtag = MagicMock(return_value=[1])
            studio.pool_canvas.gettags = MagicMock(return_value=("cardname_Shock",))

            class MockEvent:
                pass

            studio._on_canvas_double_click(
                MockEvent(), studio.pool_canvas, is_pool=True
            )

            main, sb = studio.session.get_active_deck_lists()
            assert any(c["name"] == "Shock" for c in main)

    def test_create_rename_delete_tabs(self, root, mock_app_context, mock_pool):
        """Verify the Sealed Studio variants can be managed via Notebook headers."""
        with patch("src.ui.windows.sealed_studio.ThreadPoolExecutor"):
            studio = SealedStudioWindow(
                root, mock_app_context, Configuration(), mock_pool, MagicMock()
            )

            # Create
            with patch(
                "src.ui.windows.sealed_studio.simpledialog.askstring",
                return_value="New Deck",
            ):
                studio._create_new_tab()
            assert "New Deck" in studio.session.variants

            # Rename
            with patch(
                "src.ui.windows.sealed_studio.simpledialog.askstring",
                return_value="Renamed Deck",
            ):
                studio._rename_tab()
            assert "Renamed Deck" in studio.session.variants
            assert "New Deck" not in studio.session.variants

            # Delete
            with patch("tkinter.messagebox.askyesno", return_value=True):
                studio._delete_tab()
            assert "Renamed Deck" not in studio.session.variants

    def test_export_to_clipboard(self, root, mock_app_context, mock_pool):
        """Verify export pulls from the active session variant."""
        with patch("src.ui.windows.sealed_studio.ThreadPoolExecutor"):
            studio = SealedStudioWindow(
                root, mock_app_context, Configuration(), mock_pool, MagicMock()
            )
            # Main deck gets built with 5 Plains and 2 Bears in setup
            studio._export_active_deck()
            assert "Grizzly Bears" in root.clipboard_get()

    @patch("src.ui.windows.sealed_studio.requests.post")
    @patch("src.ui.windows.sealed_studio.open_file")
    def test_export_to_sealeddeck(
        self, mock_open_file, mock_post, root, mock_app_context, mock_pool
    ):
        """Verify pushing a deck to sealeddeck.tech and opening the browser."""
        with patch("src.ui.windows.sealed_studio.ThreadPoolExecutor"):
            studio = SealedStudioWindow(
                root, mock_app_context, Configuration(), mock_pool, MagicMock()
            )

            # Mock successful API response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"url": "https://sealeddeck.tech/123"}
            mock_post.return_value = mock_response

            # Create a fake Thread class that executes the target synchronously
            def sync_thread(target=None, *args, **kwargs):
                mock_instance = MagicMock()
                if target:
                    # When .start() is called, execute the function synchronously
                    mock_instance.start = lambda: target()
                return mock_instance

            # Patch the global threading module directly since the import happens inside the function
            with patch("threading.Thread", side_effect=sync_thread):
                studio._export_to_sealeddeck_tech()
                root.update()

            mock_open_file.assert_called_once_with("https://sealeddeck.tech/123")

    def test_clear_and_add_all(self, root, mock_app_context, mock_pool):
        """Verify Clear and Add All buttons bulk move cards between arrays."""
        with patch("src.ui.windows.sealed_studio.ThreadPoolExecutor"):
            studio = SealedStudioWindow(
                root, mock_app_context, Configuration(), mock_pool, MagicMock()
            )

            # Clear Deck
            studio._clear_deck()
            main, sb = studio.session.get_active_deck_lists()
            assert len(main) == 0
            assert len(sb) > 0

            # Add All
            studio._add_all_to_deck()
            main, sb = studio.session.get_active_deck_lists()
            assert len(sb) == 0
            assert len(main) > 0

    def test_import_deck_from_clipboard_success(
        self, root, mock_app_context, mock_pool
    ):
        """Verify reading a deck from the clipboard successfully integrates into the Sealed Session."""
        with patch("src.ui.windows.sealed_studio.ThreadPoolExecutor"):
            studio = SealedStudioWindow(
                root, mock_app_context, Configuration(), mock_pool, MagicMock()
            )

            # Mock clipboard with a valid deck (Plains and Grizzly Bears are in the mock_pool)
            root.clipboard_clear()
            root.clipboard_append(
                "Deck\n1 Plains\n2 Grizzly Bears\n\nSideboard\n1 Shock"
            )

            with patch("tkinter.messagebox.showinfo") as mock_info:
                studio._import_deck_from_clipboard()
                mock_info.assert_called_once()

            main, sb = studio.session.get_active_deck_lists()
            names = [c["name"] for c in main]
            assert "Plains" in names
            assert "Grizzly Bears" in names

    def test_import_deck_from_clipboard_invalid(
        self, root, mock_app_context, mock_pool
    ):
        """Verify invalid text on clipboard shows warning without crashing."""
        with patch("src.ui.windows.sealed_studio.ThreadPoolExecutor"):
            studio = SealedStudioWindow(
                root, mock_app_context, Configuration(), mock_pool, MagicMock()
            )

            root.clipboard_clear()
            root.clipboard_append("This is just garbage text.")

            with patch("tkinter.messagebox.showwarning") as mock_warn:
                studio._import_deck_from_clipboard()
                mock_warn.assert_called_once()

    def test_on_close_saves_session(self, root, mock_app_context, mock_pool):
        """Verify closing the window persists the draft variants to disk."""
        with patch("src.ui.windows.sealed_studio.ThreadPoolExecutor"):
            studio = SealedStudioWindow(
                root, mock_app_context, Configuration(), mock_pool, MagicMock()
            )

            with patch.object(studio.session, "save_session") as mock_save:
                studio._on_close()
                mock_save.assert_called_once()

    def test_create_rename_delete_tabs(self, root, mock_app_context, mock_pool):
        """Verify the Sealed Studio variants can be managed via Notebook headers."""
        with patch("src.ui.windows.sealed_studio.ThreadPoolExecutor"):
            studio = SealedStudioWindow(
                root, mock_app_context, Configuration(), mock_pool, MagicMock()
            )

            # Create
            with patch(
                "src.ui.windows.sealed_studio.simpledialog.askstring",
                return_value="New Deck",
            ):
                studio._create_new_tab()
            assert "New Deck" in studio.session.variants

            # Rename
            with patch(
                "src.ui.windows.sealed_studio.simpledialog.askstring",
                return_value="Renamed Deck",
            ):
                studio._rename_tab()
            assert "Renamed Deck" in studio.session.variants
            assert "New Deck" not in studio.session.variants

            # Delete
            with patch("tkinter.messagebox.askyesno", return_value=True):
                studio._delete_tab()
            assert "Renamed Deck" not in studio.session.variants

    def test_on_tab_changed_syncs_notebooks(self, root, mock_app_context, mock_pool):
        """Verify switching variants in the Visual notebook automatically syncs the List notebook."""
        with patch("src.ui.windows.sealed_studio.ThreadPoolExecutor"):
            studio = SealedStudioWindow(
                root, mock_app_context, Configuration(), mock_pool, MagicMock()
            )

            # Setup two variants
            studio.session.create_variant("Build 2")
            studio._refresh_tabs()

            # Mock the visual notebook selection
            studio.notebook_vis.index = MagicMock(return_value=1)
            studio.notebook_vis.tab = MagicMock(return_value=" Build 2 ")

            # Hook into the sync logic
            with patch.object(studio, "_refresh_data") as mock_refresh:
                studio._on_tab_changed_vis(None)

                # Verify state updated
                assert studio.session.active_variant_name == "Build 2"
                mock_refresh.assert_called_once()

    def test_canvas_drag_and_drop_state(self, root, mock_app_context, mock_pool):
        """Verify starting a drag on a card in the visual canvas captures its tags correctly."""
        with patch("src.ui.windows.sealed_studio.ThreadPoolExecutor"):
            studio = SealedStudioWindow(
                root, mock_app_context, Configuration(), mock_pool, MagicMock()
            )

            class MockEvent:
                x_root = 100
                y_root = 100

            # Mock canvas item selection
            studio.pool_canvas.find_withtag = MagicMock(return_value=[1])
            studio.pool_canvas.gettags = MagicMock(
                return_value=("card", "cardname_Grizzly Bears", "inst_123_456")
            )

            # 1. Start Drag
            studio._on_canvas_press(MockEvent(), studio.pool_canvas, is_pool=True)

            assert studio._drag_data is not None
            assert studio._drag_data["name"] == "Grizzly Bears"
            assert studio._drag_data["inst"] == "inst_123_456"

            # 2. Motion
            class MotionEvent:
                x_root = 150
                y_root = 150

            studio.pool_canvas.move = MagicMock()
            studio._on_canvas_motion(MotionEvent())

            # Canvas item should be moved
            studio.pool_canvas.move.assert_called_with("inst_123_456", 50, 50)
            assert studio._drag_data["x"] == 150

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

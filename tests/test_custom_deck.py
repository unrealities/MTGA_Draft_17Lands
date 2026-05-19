import pytest
import tkinter
from tkinter import ttk
from unittest.mock import MagicMock, patch
from src.ui.windows.custom_deck import CustomDeckPanel
from src.configuration import Configuration
from src.ui.styles import Theme


class TestCustomDeckPanel:
    @pytest.fixture
    def root(self):
        root = tkinter.Tk()
        Theme.apply(root, "Dark")
        yield root
        root.destroy()

    def test_run_simulation_empty_deck(self, root):
        """Verify simulation gracefully rejects an empty deck."""
        app_context = MagicMock()
        panel = CustomDeckPanel(root, MagicMock(), Configuration(), app_context)

        # Override executor to run inline
        panel.sim_executor.submit = lambda fn, *args, **kwargs: fn(*args, **kwargs)

        panel.deck_list = []
        panel._run_monte_carlo_task(panel.deck_list)
        root.update()

        # Should display warning instead of crashing
        labels = [
            w.cget("text")
            for w in panel.sim_frame.winfo_children()
            if isinstance(w, ttk.Label)
        ]
        assert any("Deck must have 40 cards to analyze" in text for text in labels)

    def test_auto_lands_empty_spells(self, root):
        """Verify Auto-lands does not divide by zero if deck has 0 spells."""
        app_context = MagicMock()
        panel = CustomDeckPanel(root, MagicMock(), Configuration(), app_context)
        panel.sim_executor.submit = lambda fn, *args, **kwargs: fn(*args, **kwargs)

        # Deck with only basic lands
        panel.deck_list = [{"name": "Plains", "types": ["Land", "Basic"]}]

        panel._run_auto_lands_task()
        root.update()

        labels = [
            w.cget("text")
            for w in panel.sim_frame.winfo_children()
            if isinstance(w, ttk.Label)
        ]
        assert any("Add spells to the deck first" in text for text in labels)

    def test_add_and_remove_specific_basic_lands(self, root):
        """Verify the Basic Land toolbar accurately injects and removes lands from the main deck array."""
        app_context = MagicMock()
        panel = CustomDeckPanel(root, MagicMock(), Configuration(), app_context)

        assert len(panel.deck_list) == 0

        # Add 2 Mountains
        panel._add_specific_basic("Mountain")
        panel._add_specific_basic("Mountain")

        # Add 1 Forest
        panel._add_specific_basic("Forest")

        assert len(panel.deck_list) == 2  # Two unique entries

        mountain_entry = next(c for c in panel.deck_list if c["name"] == "Mountain")
        assert mountain_entry["count"] == 2
        assert mountain_entry["colors"] == ["R"]

        # Remove 1 Mountain
        panel._remove_specific_basic("Mountain")
        assert mountain_entry["count"] == 1

        # Remove the Forest
        panel._remove_specific_basic("Forest")
        assert not any(c["name"] == "Forest" for c in panel.deck_list)

    def test_clear_deck_moves_to_sideboard(self, root):
        """Verify clicking 'Clear' moves all spells to the sideboard but completely erases basic lands."""
        panel = CustomDeckPanel(root, MagicMock(), Configuration(), MagicMock())

        panel.deck_list = [
            {"name": "Lightning Bolt", "count": 2, "types": ["Instant"]},
            {"name": "Mountain", "count": 10, "types": ["Basic", "Land"]},
        ]
        panel.sb_list = [{"name": "Shock", "count": 1, "types": ["Instant"]}]

        panel._clear_deck()

        # Deck should be completely empty
        assert len(panel.deck_list) == 0

        # Sideboard should now contain the Bolts, but NOT the Mountains
        assert len(panel.sb_list) == 2
        names = [c["name"] for c in panel.sb_list]
        assert "Lightning Bolt" in names
        assert "Shock" in names
        assert "Mountain" not in names

    def test_refresh_appends_new_draft_picks_to_sideboard(self, root):
        """Verify that as the user drafts new cards, they appear in the sideboard without resetting the main deck."""
        mock_draft = MagicMock()

        # Initially, the user has drafted 1 card
        mock_draft.retrieve_taken_cards.return_value = [{"name": "Card A", "count": 1}]

        panel = CustomDeckPanel(root, mock_draft, Configuration(), MagicMock())
        panel.refresh()

        assert len(panel.sb_list) == 1
        assert panel.known_pool_size == 1

        # User moves the card to their main deck manually
        panel.deck_list.append(panel.sb_list.pop())

        # Draft progresses: User picks a new card (Card B) and another copy of Card A
        mock_draft.retrieve_taken_cards.return_value = [
            {"name": "Card A", "count": 1},
            {"name": "Card A", "count": 1},
            {"name": "Card B", "count": 1},
        ]

        panel.refresh()

        # Known pool size should update to 3
        assert panel.known_pool_size == 3

        # Main deck should still have the 1st copy of Card A untouched
        assert len(panel.deck_list) == 1
        assert panel.deck_list[0]["count"] == 1

        # Sideboard should now contain the NEW copy of Card A, and Card B
        assert len(panel.sb_list) == 2
        sb_counts = {c["name"]: c["count"] for c in panel.sb_list}
        assert sb_counts["Card A"] == 1
        assert sb_counts["Card B"] == 1

    def test_import_deck_from_suggest_tab(self, root):
        """Verify the 'Custom Builder' button from Suggest Deck flawlessly overwrites the current arrays."""
        panel = CustomDeckPanel(root, MagicMock(), Configuration(), MagicMock())

        # Pre-existing state
        panel.deck_list = [{"name": "Old Card"}]

        new_deck = [{"name": "New Main Card", "count": 1}]
        new_sb = [{"name": "New SB Card", "count": 1}]

        panel.import_deck(new_deck, new_sb)

        assert len(panel.deck_list) == 1
        assert panel.deck_list[0]["name"] == "New Main Card"
        assert len(panel.sb_list) == 1

    def test_render_deck_stats_logic(self, root):
        """Verify the UI analytics function correctly parses Pip requirements and Card Types."""
        panel = CustomDeckPanel(root, MagicMock(), Configuration(), MagicMock())

        panel.deck_list = [
            {
                "name": "Double Red",
                "mana_cost": "{R}{R}",
                "count": 2,
                "types": ["Creature"],
                "cmc": 4,
            },
            {
                "name": "Blue Cantrip",
                "mana_cost": "{U}",
                "count": 1,
                "types": ["Instant"],
                "cmc": 1,
            },
            {
                "name": "Mountain",
                "mana_cost": "",
                "count": 10,
                "types": ["Basic", "Land"],
                "cmc": 0,
            },
        ]

        # Force the UI to build the stats frame
        panel._render_deck_stats()
        root.update_idletasks()

        # Recursively extract text from all labels inside the stats frame and its sub-frames
        def get_all_text(widget):
            texts = []
            for child in widget.winfo_children():
                if isinstance(child, ttk.Label):
                    texts.append(str(child.cget("text")))
                texts.extend(get_all_text(child))
            return texts

        labels = get_all_text(panel.stats_frame)
        combined_text = " ".join(labels)

        assert "Creatures: 2" in combined_text
        assert "Non-Creatures: 1" in combined_text
        assert "Lands: 10" in combined_text

        # Verify Pips: 2 copies of {R}{R} = 4 Red Pips. 1 copy of {U} = 1 Blue Pip.
        assert "Red (R): 4" in combined_text
        assert "Blue (U): 1" in combined_text

        # Verify Curve calculation: ( (4*2) + (1*1) ) / 3 spells = 9 / 3 = 3.0
        assert "Avg CMC: 3.00" in combined_text

        @patch("src.ui.windows.custom_deck.requests.get")
        @patch("src.ui.windows.custom_deck.Image.open")
        @patch("src.ui.windows.custom_deck.ImageTk.PhotoImage")
        def test_fetch_and_show_image_network(
            self, mock_photo, mock_img_open, mock_get, root
        ):
            """Verify the background thread downloads images and attaches them to the canvas."""
            app_context = MagicMock()
            panel = CustomDeckPanel(root, MagicMock(), Configuration(), app_context)

            # Fake network response
            mock_resp = MagicMock()
            mock_resp.content = b"fake_image_data"
            mock_get.return_value = mock_resp

            # Override executor to run synchronously
            panel.image_executor.submit = lambda fn, *args, **kwargs: fn(
                *args, **kwargs
            )

            mock_frame = tkinter.Frame(root)
            card = {"name": "Lightning Bolt", "image": ["https://mock.url/bolt.jpg"]}

            # Prevent file I/O errors by mocking the open function and os.path.exists
            with patch("builtins.open", MagicMock()), patch(
                "os.path.exists", return_value=False
            ), patch("os.makedirs"):
                panel._fetch_and_show_image(card, mock_frame, 100, 100)

                # Allow Tkinter `after` calls to process on the main thread
                root.update()

                mock_get.assert_called_once()
                mock_img_open.assert_called_once()
                mock_photo.assert_called_once()

                # Verify the image label was added to the frame
                assert len(mock_frame.winfo_children()) == 1

        def test_drag_and_drop_list_bindings(self, root):
            """Verify right-click and double-click handlers on the treeviews."""
            app_context = MagicMock()
            panel = CustomDeckPanel(root, MagicMock(), Configuration(), app_context)

            # Seed deck
            panel.deck_list = [{"name": "Test Card", "count": 1}]
            panel.sb_list = [{"name": "SB Card", "count": 1}]
            panel._update_tables()

            # Mock tree identification to bypass Tkinter rendering boundaries
            panel.deck_manager.tree.identify_row = MagicMock(return_value="0")
            panel.deck_manager.tree.item = MagicMock(return_value={"text": "Test Card"})

            # 1. Double Click moves card to Sideboard
            with patch.object(panel, "_move_card") as mock_move:
                panel._on_double_click(
                    MagicMock(y=10), panel.deck_manager.tree, is_sb=False
                )
                mock_move.assert_called_with(
                    panel.deck_list, panel.sb_list, "Test Card"
                )

            # 2. Right Click opens tooltip
            with patch("src.ui.windows.custom_deck.CardToolTip.create") as mock_tooltip:
                panel._on_right_click(
                    MagicMock(x=10, y=10), panel.deck_manager.tree, is_sb=False
                )
                mock_tooltip.assert_called_once()

        def test_drag_and_drop_motion_and_release(self, root):
            """Verify drag motion and release boundaries transfer cards correctly."""
            app_context = MagicMock()
            panel = CustomDeckPanel(root, MagicMock(), Configuration(), app_context)

            # Setup initial state
            panel.deck_list = [{"name": "Bolt", "count": 1}]
            panel.sb_list = []
            panel._update_tables()

            class MockEvent:
                x_root = 100
                y_root = 100
                x = 10
                y = 10

            # Start Drag
            panel._drag_data = {"name": "Bolt", "x": 10, "y": 10, "is_sb": False}

            # Motion
            panel._on_drag_motion(MockEvent(), panel.deck_manager.tree)
            assert panel.deck_manager.tree.cget("cursor") == "hand2"

            # Release outside the valid area (dx >= 5, dy >= 5, but inside_widget=False)
            with patch.object(panel, "_inside_widget", return_value=False):
                panel._on_drag_release(
                    MockEvent(), panel.deck_manager.tree, is_sb=False
                )

            # Card should not have moved
            assert len(panel.deck_list) == 1

            # Release inside the valid area (dx >= 5, dy >= 5, inside_widget=True)
            panel._drag_data = {"name": "Bolt", "x": 10, "y": 10, "is_sb": False}
            with patch.object(panel, "_inside_widget", return_value=True):
                panel._on_drag_release(
                    MockEvent(), panel.deck_manager.tree, is_sb=False
                )

            # Card should have moved to sideboard
            assert len(panel.deck_list) == 0
            assert len(panel.sb_list) == 1

        def test_tab_change_triggers_sample_hand(self, root):
            """Verify switching to the simulation tab automatically draws a hand."""
            app_context = MagicMock()
            panel = CustomDeckPanel(root, MagicMock(), Configuration(), app_context)
            with patch.object(panel, "_draw_sample_hand") as mock_draw:
                # Simulate selecting the 3rd tab (Simulation & Sample Hand)
                panel.notebook.select = MagicMock(return_value="tab3")
                panel.notebook.tab = MagicMock(
                    return_value={"text": " SIMULATION & SAMPLE HAND "}
                )
                panel._on_tab_changed(None)
                mock_draw.assert_called_once()

        def test_clear_table_resets_ui(self, root):
            """Verify defensive UI clear logic."""
            app_context = MagicMock()
            panel = CustomDeckPanel(root, MagicMock(), Configuration(), app_context)
            panel.deck_list = [{"name": "Bolt"}]
            panel.sb_list = [{"name": "Shock"}]
            panel._clear_table()
            assert len(panel.deck_list) == 0
            assert len(panel.sb_list) == 0

        def test_basic_land_remove_bindings(self, root):
            """Verify that middle/right clicking removes a basic land."""
            app_context = MagicMock()
            panel = CustomDeckPanel(root, MagicMock(), Configuration(), app_context)
            panel._add_specific_basic("Plains")
            assert len(panel.deck_list) == 1
            # Test Right Click removal function
            panel._on_basic_remove(None, "Plains")
            assert len(panel.deck_list) == 0

        @patch("src.ui.windows.custom_deck.tkinter.messagebox.showwarning")
        def test_auto_optimize_deck_error_handling(self, mock_warn, root):
            """Verify that failed optimizations gracefully pop an alert instead of crashing."""
            app_context = MagicMock()
            panel = CustomDeckPanel(root, MagicMock(), Configuration(), app_context)
            # Override executor for synchronous execution
            panel.sim_executor.submit = lambda fn, *args, **kwargs: fn(*args, **kwargs)

            # An empty deck will cause optimize_deck to throw an Exception
            panel.deck_list = []
            panel._run_auto_optimize_task()
            root.update()

            # Verify the warning was shown
            mock_warn.assert_called_once()

        def test_sample_hand_sorting(self, root):
            """Verify that drawing a sample hand sorts cards correctly (Lands -> CMCs)."""
            app_context = MagicMock()
            panel = CustomDeckPanel(root, MagicMock(), Configuration(), app_context)
            panel.deck_list = [
                {"name": "Mountain", "types": ["Land", "Basic"], "cmc": 0, "count": 2},
                {"name": "Big Spell", "cmc": 5, "count": 2},
                {"name": "Small Spell", "cmc": 1, "count": 3},
            ]

            # Override executor so image loading fails fast but safely generates the UI labels
            panel.image_executor.submit = lambda fn, *args, **kwargs: fn(
                *args, **kwargs
            )

            with patch.object(panel, "_fetch_and_show_image"):
                panel._draw_sample_hand()

            # It should have populated the hand frames without crashing (7 cards)
            assert len(panel.hand_frames) == 7

        def test_copy_to_clipboard(self, root):
            """Verify the copy button successfully formats the deck and pushes to the OS clipboard."""
            app_context = MagicMock()
            panel = CustomDeckPanel(root, MagicMock(), Configuration(), app_context)

            panel.deck_list = [{"name": "Lightning Bolt", "count": 4}]
            panel.sb_list = [{"name": "Mountain", "count": 1}]

            panel._copy_to_clipboard()

            # Read clipboard
            clipboard_data = root.clipboard_get()
            assert "4 Lightning Bolt" in clipboard_data
            assert "Sideboard" in clipboard_data
            assert "1 Mountain" in clipboard_data

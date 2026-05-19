"""
tests/test_ui_components.py
Thorough UI component testing.
Verified: Sorting Toggle, Coordinate Safety, Alphabetical Wrap-around, and Zebra Integrity.
"""

import pytest
import tkinter
from unittest.mock import patch, MagicMock
from src.ui.components import (
    AutocompleteEntry,
    ModernTreeview,
    identify_safe_coordinates,
)
from src.ui.styles import Theme
from src import constants


class TestUIComponents:
    @pytest.fixture
    def root(self):
        root = tkinter.Tk()
        Theme.apply(root, "Dark")
        yield root
        root.destroy()

    def test_safe_coordinate_calculation(self, root):
        """Verify identify_safe_coordinates prevents monitor bleed-off and supports negative multi-monitor setups."""
        sw, sh = 1920, 1080
        ww, wh = 300, 400
        with pytest.MonkeyPatch.context() as m:
            m.setattr(root, "winfo_screenwidth", lambda: sw)
            m.setattr(root, "winfo_screenheight", lambda: sh)
            m.setattr(root, "winfo_pointerx", lambda: 1800)
            m.setattr(root, "winfo_pointery", lambda: 1000)
            x, y = identify_safe_coordinates(root, ww, wh, 10, 10)
            assert x + ww <= sw
            assert y + wh <= sh

            # Test Negative Monitor
            m.setattr(root, "winfo_pointerx", lambda: -1000)
            m.setattr(root, "winfo_pointery", lambda: -500)
            nx, ny = identify_safe_coordinates(root, ww, wh, 10, 10)
            assert nx < 0
            assert ny < 0

    def test_autocomplete_prefix_filtering(self, root):
        """Verify typing 'A' only hits relevant cards."""
        data = ["Aven", "Apprentice", "Birds of Paradise"]
        entry = AutocompleteEntry(root, completion_list=data)
        entry.insert(0, "A")

        class KeyEvent:
            keysym = "a"

        entry._on_key_release(KeyEvent())
        assert len(entry.hits) == 2
        assert "Birds of Paradise" not in entry.hits

    def test_autocomplete_cycling_and_wrap(self, root):
        """Verify full wrap-around keyboard cycling."""
        # Sorted: Apprentice, Archer, Aven
        data = ["Aven", "Apprentice", "Archer"]
        entry = AutocompleteEntry(root, completion_list=data)
        entry.insert(0, "A")

        class KeyEvent:
            keysym = "a"

        entry._on_key_release(KeyEvent())

        assert entry.get() == "Apprentice"

        class DownEvent:
            keysym = "Down"

        entry._on_key_release(DownEvent())
        assert entry.get() == "Archer"

        entry._on_key_release(DownEvent())
        assert entry.get() == "Aven"

        entry._on_key_release(DownEvent())
        assert entry.get() == "Apprentice"  # Cycle wrapped correctly

    def test_treeview_sorting_mtg_ranks_descending(self, root):
        """Verify the 1st click on 'Grade' shows best cards (A+) first."""
        cols = ["Card", "Grade"]
        tree = ModernTreeview(root, columns=cols)

        tree.insert("", "end", values=("Mediocre", "C+"))
        tree.insert("", "end", values=("Bomb", "A+"))
        tree.insert("", "end", values=("Trash", "F"))

        # 1. First click: reverse becomes True (Descending)
        # 2. Priority Collation: Numbers (Ranks) win over Strings
        # 3. field_process_sort: A+(14), C+(8), F(2)
        tree._handle_sort("Grade")

        results = [tree.item(k)["values"][1] for k in tree.get_children()]
        assert results == ["A+", "C+", "F"]

    def test_treeview_sorting_na_handling(self, root):
        """Verify that 'NA' or empty strings always sink to the bottom in descending sort."""
        cols = ["Val"]
        tree = ModernTreeview(root, columns=cols)
        tree.insert("", "end", values=("50.0",))
        tree.insert("", "end", values=("NA",))
        tree.insert("", "end", values=("99.0",))

        # Click 1: Descending
        tree._handle_sort("Val")
        results = [tree.item(k)["values"][0] for k in tree.get_children()]
        # 99 and 50 are Priority 1, NA is Priority 0.
        assert results == ["99.0", "50.0", "NA"]

    def test_treeview_sorting_toggle_logic(self, root):
        """Verify clicking twice reverses the sort order."""
        cols = ["Val"]
        tree = ModernTreeview(root, columns=cols)
        tree.insert("", "end", values=("10.0",))
        tree.insert("", "end", values=("50.0",))

        # Click 1: Descending
        tree._handle_sort("Val")
        assert tree.item(tree.get_children()[0])["values"][0] == "50.0"

        # Click 2: Ascending
        tree._handle_sort("Val")
        assert tree.item(tree.get_children()[0])["values"][0] == "10.0"

    def test_treeview_zebra_striping_persistence(self, root):
        """Verify stripes follow visible index after sort."""
        cols = ["Val"]
        tree = ModernTreeview(root, columns=cols)
        tree.insert("", "end", values=("Z",))  # Row 0
        tree.insert("", "end", values=("A",))  # Row 1

        # Sort so 'A' is at top (Ascending)
        tree._handle_sort("Val")  # Toggle to Desc
        tree._handle_sort("Val")  # Toggle to Asc

        children = tree.get_children()
        assert "bw_odd" in tree.item(children[0], "tags")  # A is now row 0
        assert "bw_even" in tree.item(children[1], "tags")  # Z is now row 1

    def test_autocomplete_empty_list_safety(self, root):
        """Ensure no DivisionByZero or index errors if hits is empty."""
        entry = AutocompleteEntry(root, completion_list=[])
        entry.insert(0, "Z")

        class KeyEvent:
            keysym = "z"

        entry._on_key_release(KeyEvent())
        assert not entry.hits

    @patch("src.configuration.write_configuration")
    def test_dynamic_treeview_column_management(self, mock_write, root):
        """Verify the DynamicTreeviewManager can add, remove, and reset columns."""
        from src.ui.components import DynamicTreeviewManager
        from src.configuration import Configuration

        config = Configuration()
        config.settings.column_configs["test_view"] = ["name", "gihwr"]

        manager = DynamicTreeviewManager(root, "test_view", config, lambda: None)

        # 1. Test Add Column
        manager._add_column("alsa")
        assert "alsa" in manager.active_fields
        assert "alsa" in config.settings.column_configs["test_view"]
        mock_write.assert_called()

        # 2. Test Remove Column
        manager._remove_column_by_name("gihwr")
        assert "gihwr" not in manager.active_fields
        assert "gihwr" not in config.settings.column_configs["test_view"]

        # 3. Test Reset Defaults
        manager._reset_defaults()
        assert manager.active_fields == ["name", "value", "gihwr"]

    def test_collapsible_frame_toggle(self, root):
        """Verify the CollapsibleFrame correctly expands and collapses its content."""
        from src.ui.components import CollapsibleFrame
        from src.configuration import Configuration

        config = Configuration()
        frame = CollapsibleFrame(
            root,
            title="TEST",
            expanded=True,
            configuration=config,
            setting_key="test_panel",
        )

        # Starts expanded
        assert frame.expanded is True
        assert frame.content_frame.winfo_manager() != ""

        # Toggle to hide
        frame.toggle()
        assert frame.expanded is False
        assert (
            frame.content_frame.winfo_manager() == ""
        )  # pack_forget() removes the geometry manager
        assert config.settings.collapsible_states["test_panel"] is False

    def test_card_pile_rendering(self, root):
        """Verify the visual CardPile successfully parses card objects into UI rectangles."""
        from src.ui.components import CardPile
        from unittest.mock import MagicMock

        mock_app = MagicMock()
        pile = CardPile(root, "CMC 2", mock_app)

        card_data = {
            "name": "Grizzly Bears",
            "count": 2,
            "mana_cost": "{1}{G}",
            "deck_colors": {"All Decks": {"gihwr": 55.0}},
        }

        # Call the render function
        pile.add_card(card_data)

        # Verify the container was populated with the Tkinter Frame for the card
        children = pile.container.winfo_children()
        assert len(children) == 1

        # Drill into the card frame to verify the text was rendered
        card_frame = children[0]
        labels = [
            w for w in card_frame.winfo_children() if isinstance(w, tkinter.Label)
        ]
        assert len(labels) == 1
        assert "2x Grizzly Bears" in labels[0].cget("text")

    @patch("src.ui.components.CardToolTip._reposition")
    def test_card_tooltip_instantiation(self, mock_repo, root):
        """Verify the complex CardToolTip overlay spawns without throwing layout errors."""
        from src.ui.components import CardToolTip

        # Ensure we don't accidentally block it by passing a Basic Land
        card_data = {
            "name": "Lightning Bolt",
            "rarity": "uncommon",
            "types": ["Instant"],
            "deck_colors": {"All Decks": {"gihwr": 62.0, "iwd": 5.0, "alsa": 2.1}},
        }

        try:
            # We must use scale=1.0 to ensure layout math holds
            CardToolTip.create(root, card_data, images_enabled=False, scale=1.0)

            tooltip = CardToolTip._active_tooltip
            assert tooltip is not None
            assert tooltip.winfo_exists()

            # Verify the data was mapped
            assert "Lightning Bolt" in tooltip.winfo_children()[0].winfo_children()[
                0
            ].cget("text")

            # Cleanup
            tooltip._close()
            assert not tooltip.winfo_exists()
        except Exception as e:
            pytest.fail(f"CardToolTip crashed on initialization: {e}")

    def test_dynamic_treeview_column_drag_and_drop(self, root):
        """Verify columns can be dragged and reordered by users."""
        from src.ui.components import DynamicTreeviewManager
        from src.configuration import Configuration

        config = Configuration()
        config.settings.column_configs["test_view"] = ["name", "gihwr", "value"]

        manager = DynamicTreeviewManager(root, "test_view", config, lambda: None)
        tree = manager.tree

        # Headless Tkinter doesn't fully populate internal display properties until drawn,
        # so we mock the display order retrieval function for this isolated test.
        with patch.object(
            tree, "_get_display_order", return_value=["name", "gihwr", "value"]
        ):

            class MockEvent:
                def __init__(self, x):
                    self.x = x
                    self.y = 10

            # Mock identifying columns
            # Column 1 = Name, Column 2 = GIHWR, Column 3 = Value
            tree.identify_region = MagicMock(return_value="heading")
            tree.identify_column = MagicMock(return_value="#2")

            # 1. Start drag on GIHWR
            tree._on_header_press(MockEvent(100))
            assert tree._drag_col == "gihwr"

            # 2. Drag it far enough to register motion
            tree._on_header_motion(MockEvent(150))
            assert tree._dragging is True

            # 3. Release it over Column 3 (Value)
            tree.identify_column = MagicMock(return_value="#3")
            tree._on_header_release(MockEvent(150))

            # The config object should have been updated by the move
            saved_order = config.settings.column_display_orders["test_view"]
            # Expect order to be: name, value, gihwr (because gihwr was dropped over value's index)
            assert saved_order == ["name", "value", "gihwr"]

    def test_scrolled_frame_initialization(self, root):
        """Verify ScrolledFrame layout and coordinate binding."""
        from src.ui.components import ScrolledFrame

        frame = ScrolledFrame(root)

        # Test resize bindings
        class MockEvent:
            height = 500

        frame.canvas.event_generate("<Configure>", height=500)

        assert frame.canvas.winfo_exists()
        assert frame.scrollbar.winfo_exists()
        assert frame.scrollable_frame.winfo_exists()

    def test_dynamic_treeview_context_menu(self, root):
        """Verify right-clicking headers spawns the column configuration menu."""
        from src.ui.components import DynamicTreeviewManager
        from src.configuration import Configuration

        config = Configuration()
        config.settings.column_configs["test_view"] = ["name", "gihwr"]

        manager = DynamicTreeviewManager(root, "test_view", config, lambda: None)

        class MockEvent:
            x = 10
            y = 10
            x_root = 100
            y_root = 100

        manager.tree.identify_region = MagicMock(return_value="heading")
        # Click on GIHWR column (#2)
        manager.tree.identify_column = MagicMock(return_value="#2")

        with patch("tkinter.Menu.post") as mock_post:
            manager._show_context_menu(MockEvent())
            mock_post.assert_called_once_with(100, 100)
        """Verify the complex CardToolTip overlay spawns without throwing layout errors."""
        from src.ui.components import CardToolTip

        # Ensure we don't accidentally block it by passing a Basic Land
        card_data = {
            "name": "Lightning Bolt",
            "rarity": "uncommon",
            "types": ["Instant"],
            "deck_colors": {"All Decks": {"gihwr": 62.0, "iwd": 5.0, "alsa": 2.1}},
        }

        try:
            # We must use scale=1.0 to ensure layout math holds
            CardToolTip.create(root, card_data, images_enabled=False, scale=1.0)

            tooltip = CardToolTip._active_tooltip
            assert tooltip is not None
            assert tooltip.winfo_exists()

            # Verify the data was mapped
            assert "Lightning Bolt" in tooltip.winfo_children()[0].winfo_children()[
                0
            ].cget("text")

            # Cleanup
            tooltip._close()
            assert not tooltip.winfo_exists()
        except Exception as e:
            pytest.fail(f"CardToolTip crashed on initialization: {e}")

"""
tests/test_ui_components.py
Thorough UI component testing.
Verified: Sorting Toggle, Coordinate Safety, Alphabetical Wrap-around, and Zebra Integrity.
"""

import pytest
import tkinter
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
        """Verify identify_safe_coordinates prevents monitor bleed-off."""
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
        hd = {"Card": {"width": 100}, "Grade": {"width": 50}}
        tree = ModernTreeview(root, columns=cols, headers_config=hd)

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
        hd = {"Val": {"width": 50}}
        tree = ModernTreeview(root, columns=cols, headers_config=hd)
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
        hd = {"Val": {"width": 50}}
        tree = ModernTreeview(root, columns=cols, headers_config=hd)
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
        hd = {"Val": {"width": 50}}
        tree = ModernTreeview(root, columns=cols, headers_config=hd)
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

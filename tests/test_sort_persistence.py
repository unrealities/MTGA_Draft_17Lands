"""
tests/test_sort_persistence.py
Tests for the persistent column sort feature in ModernTreeview.

Covers:
  - active_sort_column tracking
  - config persistence (table_sort_states)
  - sort group mapping (pack_table / overlay_table share state)
  - reapply_sort() after data reload
  - cross-table sort inheritance via shared config
  - force_reverse parameter
  - sort arrow heading indicators
  - graceful no-op when saved column no longer exists
"""

import pytest
import tkinter
from types import SimpleNamespace
from unittest.mock import patch
from src.ui.components import ModernTreeview
from src.ui.styles import Theme


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_config(sort_states=None):
    """Returns a minimal config object with optional pre-populated sort states."""
    settings = SimpleNamespace()
    if sort_states is not None:
        settings.table_sort_states = dict(sort_states)
    # No table_sort_states attribute → tests hasattr() branch in __init__/_handle_sort
    config = SimpleNamespace(settings=settings)
    return config


WRITE_CFG = "src.configuration.write_configuration"


def make_tree(root, columns=("name", "gihwr", "value"), view_id=None, config=None):
    """Convenience factory. __init__ never calls write_configuration, so no patch needed."""
    tree = ModernTreeview(root, columns=columns, view_id=view_id, config=config)
    tree.active_fields = list(columns)
    return tree


def get_col_values(tree, col_index=0):
    return [tree.item(k)["values"][col_index] for k in tree.get_children()]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def root():
    r = tkinter.Tk()
    Theme.apply(r, "Dark")
    yield r
    r.destroy()


# ---------------------------------------------------------------------------
# active_sort_column tracking
# ---------------------------------------------------------------------------

class TestActiveSortColumn:
    def test_initially_none(self, root):
        tree = make_tree(root)
        assert tree.active_sort_column is None

    def test_set_after_sort(self, root):
        tree = make_tree(root)
        tree.insert("", "end", values=("Lightning Bolt", "60.0", "80"))
        with patch(WRITE_CFG):
            tree._handle_sort("gihwr")
        assert tree.active_sort_column == "gihwr"

    def test_updates_to_most_recently_sorted_column(self, root):
        tree = make_tree(root)
        tree.insert("", "end", values=("Card A", "55.0", "70"))
        with patch(WRITE_CFG):
            tree._handle_sort("gihwr")
            tree._handle_sort("value")
        assert tree.active_sort_column == "value"

    def test_loaded_from_config_on_init(self, root):
        # pack_table → sort_group="pack"; init loads if both config and view_id are set
        config = make_config(sort_states={"pack": {"column": "gihwr", "reverse": True}})
        tree = make_tree(root, view_id="pack_table", config=config)
        assert tree.active_sort_column == "gihwr"
        assert tree.column_sort_state["gihwr"] is True


# ---------------------------------------------------------------------------
# Config persistence
# ---------------------------------------------------------------------------

class TestConfigPersistence:
    def test_sort_state_written_to_config(self, root):
        config = make_config()
        tree = make_tree(root, view_id="pack_table", config=config)
        tree.insert("", "end", values=("Card A", "60.0", "80"))

        with patch(WRITE_CFG) as mock_write:
            tree._handle_sort("gihwr")
            mock_write.assert_called_once()

        assert hasattr(config.settings, "table_sort_states")
        state = config.settings.table_sort_states["pack"]
        assert state["column"] == "gihwr"
        assert state["reverse"] is True  # first click → descending

    def test_sort_direction_toggled_and_persisted(self, root):
        config = make_config()
        tree = make_tree(root, view_id="pack_table", config=config)
        tree.insert("", "end", values=("Card A", "60.0", "80"))

        with patch(WRITE_CFG):
            tree._handle_sort("gihwr")   # descending
            assert config.settings.table_sort_states["pack"]["reverse"] is True

            tree._handle_sort("gihwr")   # ascending
            assert config.settings.table_sort_states["pack"]["reverse"] is False

    def test_no_config_does_not_crash(self, root):
        """Tree without config sorts fine; just nothing persisted."""
        tree = make_tree(root, view_id=None, config=None)
        tree.insert("", "end", values=("Card A", "60.0", "80"))
        tree.insert("", "end", values=("Card B", "40.0", "50"))
        tree._handle_sort("gihwr")
        assert tree.active_sort_column == "gihwr"

    def test_write_configuration_called_with_config_object(self, root):
        config = make_config()
        tree = make_tree(root, view_id="pack_table", config=config)
        tree.insert("", "end", values=("Card A", "60.0", "80"))

        with patch(WRITE_CFG) as mock_write:
            tree._handle_sort("gihwr")
            args, _ = mock_write.call_args
            assert args[0] is config


# ---------------------------------------------------------------------------
# Sort group mapping
# ---------------------------------------------------------------------------

class TestSortGroupMapping:
    @pytest.mark.parametrize("view_id,expected_group", [
        ("pack_table",         "pack"),
        ("overlay_table",      "pack"),
        ("taken_table",        "pool"),
        ("overlay_pool_table", "pool"),
        ("missing_table",      "missing_table"),
        (None,                 "default"),
    ])
    def test_sort_group_values(self, root, view_id, expected_group):
        tree = make_tree(root, view_id=view_id)
        assert tree.sort_group == expected_group

    def test_pack_and_overlay_share_sort_state(self, root):
        """Sorting pack_table should be visible to overlay_table via shared config."""
        config = make_config()

        pack_tree = make_tree(root, view_id="pack_table", config=config)
        pack_tree.insert("", "end", values=("Card A", "60.0", "80"))
        with patch(WRITE_CFG):
            pack_tree._handle_sort("gihwr")

        # overlay_table reads the same "pack" group
        assert config.settings.table_sort_states["pack"]["column"] == "gihwr"

        overlay_tree = make_tree(root, view_id="overlay_table", config=config)
        overlay_tree.insert("", "end", values=("Card A", "60.0", "80"))
        assert overlay_tree.active_sort_column == "gihwr"


# ---------------------------------------------------------------------------
# reapply_sort()
# ---------------------------------------------------------------------------

class TestReapplySort:
    def test_reapply_restores_order_after_reload(self, root):
        """Simulate a new pick: delete rows, re-insert shuffled, call reapply_sort."""
        tree = make_tree(root, view_id="pack_table", config=make_config())

        def populate(rows):
            for item in tree.get_children():
                tree.delete(item)
            for row in rows:
                tree.insert("", "end", values=row)

        # Sort descending by gihwr
        populate([("Card A", "40.0", "50"), ("Card B", "70.0", "90")])
        with patch(WRITE_CFG):
            tree._handle_sort("gihwr")

        assert get_col_values(tree, 1)[0] == "70.0"

        # New pick: reload rows in different order
        populate([("Card C", "30.0", "40"), ("Card D", "80.0", "95")])
        with patch(WRITE_CFG):
            tree.reapply_sort()

        assert get_col_values(tree, 1)[0] == "80.0"

    def test_reapply_returns_true_when_sort_applied(self, root):
        config = make_config()
        tree = make_tree(root, view_id="pack_table", config=config)
        tree.insert("", "end", values=("Card A", "60.0", "80"))
        with patch(WRITE_CFG):
            tree._handle_sort("gihwr")
            result = tree.reapply_sort()
        assert result is True

    def test_reapply_returns_false_with_no_active_sort(self, root):
        tree = make_tree(root, view_id="pack_table", config=make_config())
        tree.insert("", "end", values=("Card A", "60.0", "80"))
        assert tree.reapply_sort() is False

    def test_reapply_returns_false_when_saved_column_missing(self, root):
        """Config references a column not present in this table → graceful no-op."""
        config = make_config(sort_states={"pack": {"column": "nonexistent_col", "reverse": True}})
        tree = make_tree(root, view_id="pack_table", config=config)
        tree.insert("", "end", values=("Card A", "60.0", "80"))
        result = tree.reapply_sort()
        assert result is False

    def test_reapply_inherits_sort_from_sibling_table(self, root):
        """overlay_table reapply_sort() picks up sort set by pack_table."""
        config = make_config()

        pack_tree = make_tree(root, view_id="pack_table", config=config)
        pack_tree.insert("", "end", values=("Card A", "40.0", "50"))
        pack_tree.insert("", "end", values=("Card B", "70.0", "90"))
        with patch(WRITE_CFG):
            pack_tree._handle_sort("gihwr")

        overlay_tree = make_tree(root, view_id="overlay_table", config=config)
        overlay_tree.insert("", "end", values=("Card C", "30.0", "40"))
        overlay_tree.insert("", "end", values=("Card D", "80.0", "95"))
        with patch(WRITE_CFG):
            overlay_tree.reapply_sort()

        assert get_col_values(overlay_tree, 1)[0] == "80.0"


# ---------------------------------------------------------------------------
# force_reverse parameter
# ---------------------------------------------------------------------------

class TestForceReverse:
    def test_force_reverse_true_does_not_toggle(self, root):
        tree = make_tree(root)
        tree.insert("", "end", values=("Card A", "40.0", "50"))
        tree.insert("", "end", values=("Card B", "70.0", "90"))

        # Force descending without toggling
        tree._handle_sort("gihwr", force_reverse=True)
        assert tree.column_sort_state["gihwr"] is True
        assert get_col_values(tree, 1)[0] == "70.0"

    def test_force_reverse_false_gives_ascending(self, root):
        tree = make_tree(root)
        tree.insert("", "end", values=("Card A", "40.0", "50"))
        tree.insert("", "end", values=("Card B", "70.0", "90"))

        tree._handle_sort("gihwr", force_reverse=False)
        assert tree.column_sort_state["gihwr"] is False
        assert get_col_values(tree, 1)[0] == "40.0"

    def test_force_reverse_does_not_change_existing_state_of_other_columns(self, root):
        tree = make_tree(root)
        tree.insert("", "end", values=("Card A", "40.0", "50"))

        tree._handle_sort("gihwr", force_reverse=True)
        # value column was never touched
        assert tree.column_sort_state["value"] is False


# ---------------------------------------------------------------------------
# Sort arrow heading indicators
# ---------------------------------------------------------------------------

class TestSortArrowIndicators:
    def test_arrow_shown_on_active_column_descending(self, root):
        tree = make_tree(root)
        tree.insert("", "end", values=("Card A", "60.0", "80"))
        tree._handle_sort("gihwr")
        heading_text = tree.heading("gihwr")["text"]
        assert "▼" in heading_text

    def test_arrow_shown_on_active_column_ascending(self, root):
        tree = make_tree(root)
        tree.insert("", "end", values=("Card A", "60.0", "80"))
        tree._handle_sort("gihwr")  # descending
        tree._handle_sort("gihwr")  # ascending
        heading_text = tree.heading("gihwr")["text"]
        assert "▲" in heading_text

    def test_arrow_cleared_from_previously_sorted_column(self, root):
        tree = make_tree(root)
        tree.insert("", "end", values=("Card A", "60.0", "80"))
        tree._handle_sort("gihwr")
        tree._handle_sort("value")
        assert "▼" not in tree.heading("gihwr")["text"]
        assert "▲" not in tree.heading("gihwr")["text"]

    def test_arrow_shown_on_init_when_sort_state_loaded(self, root):
        """If config already has a sort state, the arrow should be present from the start."""
        config = make_config(sort_states={"pack": {"column": "gihwr", "reverse": True}})
        tree = make_tree(root, view_id="pack_table", config=config)
        assert "▼" in tree.heading("gihwr")["text"]

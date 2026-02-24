"""
tests/test_dashboard.py
Senior-level unit testing for the Live Dashboard component.
Fixed: Populated mock results with sufficient column counts to match
configured active_fields, preventing IndexError in sorting logic.
"""

import pytest
import tkinter
from unittest.mock import MagicMock, patch
from src.ui.dashboard import DashboardFrame
from src.configuration import Configuration, Settings
from src import constants


class TestDashboardFrame:
    @pytest.fixture
    def root(self):
        """Headless Tkinter context."""
        root = tkinter.Tk()
        yield root
        root.destroy()

    @pytest.fixture
    def mock_config(self):
        """Standard configuration with specific column settings for testing."""
        config = Configuration()
        # Updated to use new column_configs dictionary
        config.settings.column_configs["pack_table"] = [
            constants.DATA_FIELD_NAME,
            constants.DATA_FIELD_GIHWR,
            constants.DATA_FIELD_ALSA,
            constants.DATA_FIELD_DISABLED,
        ]
        return config

    def test_initialization_columns(self, root, mock_config):
        """
        Verify that the dashboard builds its tables with the specific
        columns requested in the Configuration.
        """
        dashboard = DashboardFrame(root, mock_config, MagicMock(), MagicMock())

        # Access the underlying Treeview of the Pack table via its manager
        # DashboardFrame -> DynamicTreeviewManager -> ModernTreeview
        # We access the manager instance stored in the dashboard
        pack_tree = dashboard.pack_manager.tree

        columns = list(pack_tree["columns"])
        assert "name" in columns
        assert "gihwr" in columns
        assert "alsa" in columns
        assert "ata" not in columns

    def test_update_pack_data_rendering(self, root, mock_config):
        """Verify data injection into the Treeview."""
        dashboard = DashboardFrame(root, mock_config, MagicMock(), MagicMock())
        pack_tree = dashboard.pack_manager.tree

        # Results match the 3 active columns (Name, GIHWR, ALSA)
        mock_processed_cards = [
            {"results": ["Bolt", "55.5", "1.2"], "tag": "bw_odd", "sort_key": 55.5},
            {
                "results": ["Counterspell", "52.0", "2.5"],
                "tag": "bw_even",
                "sort_key": 52.0,
            },
        ]

        # We patch update_pack_data's internal logic, or test the logic that prepares data
        # Actually, update_pack_data calls CardResult internally? No, the refactored code
        # inside update_pack_data does the processing directly using tree.active_fields.

        # Let's test update_pack_data with raw card objects
        cards = [
            {
                constants.DATA_FIELD_NAME: "Bolt",
                "deck_colors": {"All Decks": {"gihwr": 55.5, "alsa": 1.2}},
            },
            {
                constants.DATA_FIELD_NAME: "Counterspell",
                "deck_colors": {"All Decks": {"gihwr": 52.0, "alsa": 2.5}},
            },
        ]

        dashboard.update_pack_data(
            cards=cards,
            colors=[],
            metrics=MagicMock(),
            tier_data={},
            current_pick=1,
        )

        rows = pack_tree.get_children()
        assert len(rows) == 2
        # Index 0 is Name
        assert pack_tree.item(rows[0])["values"][0] == "Bolt"

    def test_zebra_striping_logic(self, root, mock_config):
        """Verify alternating bw_odd/bw_even tags."""
        mock_config.settings.card_colors_enabled = False
        dashboard = DashboardFrame(root, mock_config, MagicMock(), MagicMock())
        pack_tree = dashboard.pack_manager.tree

        cards = [
            {constants.DATA_FIELD_NAME: "C1"},
            {constants.DATA_FIELD_NAME: "C2"},
            {constants.DATA_FIELD_NAME: "C3"},
        ]

        dashboard.update_pack_data(cards, [], None, {}, 1)

        rows = pack_tree.get_children()
        # Row 1 (Index 0) is Odd
        assert "bw_odd" in pack_tree.item(rows[0], "tags")
        assert "bw_even" in pack_tree.item(rows[1], "tags")
        assert "bw_odd" in pack_tree.item(rows[2], "tags")

    def test_card_color_highlighting(self, root, mock_config):
        """Verify color tags (red_card, etc.) work correctly."""
        mock_config.settings.card_colors_enabled = True
        dashboard = DashboardFrame(root, mock_config, MagicMock(), MagicMock())
        pack_tree = dashboard.pack_manager.tree

        cards = [
            {
                constants.DATA_FIELD_NAME: "Fireball",
                constants.DATA_FIELD_MANA_COST: "{R}",
            }
        ]

        dashboard.update_pack_data(cards, [], None, {}, 1)

        rows = pack_tree.get_children()
        tags = pack_tree.item(rows[0], "tags")
        assert "red_card" in tags

    def test_signals_table_population(self, root, mock_config):
        dashboard = DashboardFrame(root, mock_config, MagicMock(), MagicMock())
        mock_scores = {"W": 10.5, "U": 25.0, "B": 5.0}
        dashboard.update_signals(mock_scores)

        # SignalMeter stores scores in .scores attribute
        assert dashboard.signal_meter.scores["U"] == 25.0
        assert dashboard.signal_meter.scores["W"] == 10.5

    def test_stats_curve_population(self, root, mock_config):
        dashboard = DashboardFrame(root, mock_config, MagicMock(), MagicMock())
        mock_distribution = [2, 5, 10, 3, 1, 0, 0]
        dashboard.update_stats(mock_distribution)

        # ManaCurvePlot stores current distribution in .current
        assert dashboard.curve_plot.current == mock_distribution

    def test_card_selection_callback(self, root, mock_config):
        """Verify that selecting a row in the pack table triggers the callback."""
        mock_callback = MagicMock()
        dashboard = DashboardFrame(root, mock_config, mock_callback, MagicMock())
        pack_tree = dashboard.pack_manager.tree

        pack_tree.insert("", "end", iid="row_1", values=("Test Card",))
        pack_tree.selection_set("row_1")

        pack_tree.event_generate("<<TreeviewSelect>>")
        assert mock_callback.called

    def test_empty_data_resilience(self, root, mock_config):
        """Verify dashboard doesn't crash when passed empty card lists."""
        dashboard = DashboardFrame(root, mock_config, MagicMock(), MagicMock())
        try:
            dashboard.update_pack_data([], [], None, {}, 1)
            dashboard.update_signals({})
            dashboard.update_stats([])
        except Exception as e:
            pytest.fail(f"DashboardFrame crashed on empty data: {e}")

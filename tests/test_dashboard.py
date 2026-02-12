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
        config.settings.column_2 = constants.DATA_FIELD_GIHWR
        config.settings.column_3 = constants.DATA_FIELD_ALSA
        config.settings.column_4 = constants.DATA_FIELD_DISABLED
        return config

    def test_initialization_columns(self, root, mock_config):
        """
        Verify that the dashboard builds its tables with the specific
        columns requested in the Configuration.
        """
        dashboard = DashboardFrame(root, mock_config, MagicMock())

        # Access the underlying Treeview of the Pack table
        pack_tree = list(dashboard.table_pack.children.values())[1]

        columns = list(pack_tree["columns"])
        assert "Card" in columns
        assert "GIHWR" in columns
        assert "ALSA" in columns
        assert "ATA" not in columns

    def test_update_pack_data_rendering(self, root, mock_config):
        """Verify data injection into the Treeview."""
        dashboard = DashboardFrame(root, mock_config, MagicMock())
        pack_tree = list(dashboard.table_pack.children.values())[1]

        # Results match the 3 active columns (Name, GIHWR, ALSA)
        mock_processed_cards = [
            {"results": ["Bolt", "55.5", "1.2"], constants.DATA_FIELD_MANA_COST: "{R}"},
            {
                "results": ["Counterspell", "52.0", "2.5"],
                constants.DATA_FIELD_MANA_COST: "{U}{U}",
            },
        ]

        with patch("src.ui.dashboard.CardResult") as mock_result_cls:
            mock_processor = mock_result_cls.return_value
            mock_processor.return_results.return_value = mock_processed_cards

            dashboard.update_pack_data(
                cards=[{}, {}],
                colors=["R", "U"],
                metrics=MagicMock(),
                tier_data={},
                current_pick=1,
            )

        rows = pack_tree.get_children()
        assert len(rows) == 2
        assert pack_tree.item(rows[0])["values"][0] == "Bolt"

    def test_zebra_striping_logic(self, root, mock_config):
        """Verify alternating bw_odd/bw_even tags."""
        mock_config.settings.card_colors_enabled = False
        dashboard = DashboardFrame(root, mock_config, MagicMock())
        pack_tree = list(dashboard.table_pack.children.values())[1]

        # FIX: Provide 3 values per row to match active_fields [Name, GIHWR, ALSA]
        mock_processed = [
            {"results": ["C1", "50.0", "1.0"]},
            {"results": ["C2", "40.0", "2.0"]},
            {"results": ["C3", "30.0", "3.0"]},
        ]

        with patch("src.ui.dashboard.CardResult") as mock_result_cls:
            mock_result_cls.return_value.return_results.return_value = mock_processed
            dashboard.update_pack_data([{}, {}, {}], [], None, {}, 1)

        rows = pack_tree.get_children()
        # Row 1 (Index 0) is Odd
        assert "bw_odd" in pack_tree.item(rows[0], "tags")
        assert "bw_even" in pack_tree.item(rows[1], "tags")
        assert "bw_odd" in pack_tree.item(rows[2], "tags")

    def test_card_color_highlighting(self, root, mock_config):
        """Verify color tags (red_card, etc.) work correctly."""
        mock_config.settings.card_colors_enabled = True
        dashboard = DashboardFrame(root, mock_config, MagicMock())
        pack_tree = list(dashboard.table_pack.children.values())[1]

        # FIX: Provide 3 values per row to match active_fields
        mock_processed = [
            {
                "results": ["Fireball", "60.0", "1.5"],
                constants.DATA_FIELD_MANA_COST: "{R}",
            }
        ]

        with patch("src.ui.dashboard.CardResult") as mock_result_cls:
            mock_result_cls.return_value.return_results.return_value = mock_processed
            dashboard.update_pack_data([{}], [], None, {}, 1)

        rows = pack_tree.get_children()
        tags = pack_tree.item(rows[0], "tags")
        assert "red_card" in tags

    def test_signals_table_population(self, root, mock_config):
        dashboard = DashboardFrame(root, mock_config, MagicMock())
        mock_scores = {"W": 10.5, "U": 25.0, "B": 5.0}
        dashboard.update_signals(mock_scores)

        rows = dashboard.table_signals.get_children()
        # Blue (25.0) should be first due to descending sort
        first_row = dashboard.table_signals.item(rows[0])["values"]
        assert first_row[0] == "Blue"
        assert str(first_row[1]) == "25.0"

    def test_stats_curve_population(self, root, mock_config):
        dashboard = DashboardFrame(root, mock_config, MagicMock())
        mock_distribution = [2, 5, 10, 3, 1, 0, 0]
        dashboard.update_stats(mock_distribution)

        rows = dashboard.table_stats.get_children()
        assert len(rows) == 7
        assert dashboard.table_stats.item(rows[2])["values"][1] == 10

    def test_card_selection_callback(self, root, mock_config):
        """Verify that selecting a row in the pack table triggers the callback."""
        mock_callback = MagicMock()
        dashboard = DashboardFrame(root, mock_config, mock_callback)
        pack_tree = list(dashboard.table_pack.children.values())[1]

        pack_tree.insert("", "end", iid="row_1", values=("Test Card",))
        pack_tree.selection_set("row_1")

        pack_tree.event_generate("<<TreeviewSelect>>")
        assert mock_callback.called

    def test_empty_data_resilience(self, root, mock_config):
        """Verify dashboard doesn't crash when passed empty card lists."""
        dashboard = DashboardFrame(root, mock_config, MagicMock())
        try:
            dashboard.update_pack_data([], [], None, {}, 1)
            dashboard.update_signals({})
            dashboard.update_stats([])
        except Exception as e:
            pytest.fail(f"DashboardFrame crashed on empty data: {e}")

"""
tests/test_compare.py
Validation for the Card Compare UI.
Covers: Case-insensitive search, duplicate entry prevention,
and dashboard setting synchronization.
"""

import pytest
import tkinter
from unittest.mock import MagicMock, patch
from src.ui.windows.compare import ComparePanel
from src.configuration import Configuration, Settings
from src import constants


class TestComparePanel:
    @pytest.fixture
    def root(self):
        root = tkinter.Tk()
        yield root
        root.destroy()

    @pytest.fixture
    def mock_draft(self):
        """Mock draft providing a small dataset of 2 cards."""
        draft = MagicMock()
        draft.set_data.get_card_ratings.return_value = {
            "1": {
                constants.DATA_FIELD_NAME: "Lightning Bolt",
                constants.DATA_FIELD_CMC: 1,
                constants.DATA_FIELD_MANA_COST: "{R}",
            },
            "2": {
                constants.DATA_FIELD_NAME: "Counterspell",
                constants.DATA_FIELD_CMC: 2,
                constants.DATA_FIELD_MANA_COST: "{U}{U}",
            },
        }
        draft.retrieve_taken_cards.return_value = []
        draft.retrieve_set_metrics.return_value = MagicMock()
        draft.retrieve_tier_data.return_value = {}
        return draft

    def test_autocomplete_population_on_load(self, root, mock_draft):
        """Verify that the search index is populated when the panel opens."""
        panel = ComparePanel(root, mock_draft, Configuration())

        # Check autocomplete hits source
        assert "Lightning Bolt" in panel.entry_card.completion_list
        assert "Counterspell" in panel.entry_card.completion_list

    def test_add_card_logic(self, root, mock_draft):
        """Verify adding a card via name string updates the list and table."""
        panel = ComparePanel(root, mock_draft, Configuration())

        panel.entry_card.insert(0, "Lightning Bolt")
        panel._add_card()  # Simulate Enter/Add click

        assert len(panel.compare_list) == 1
        assert panel.compare_list[0][constants.DATA_FIELD_NAME] == "Lightning Bolt"
        assert len(panel.table.get_children()) == 1

    def test_duplicate_prevention(self, root, mock_draft):
        """Verify that adding the same card twice is ignored."""
        panel = ComparePanel(root, mock_draft, Configuration())

        panel.entry_card.insert(0, "Counterspell")
        panel._add_card()
        panel.entry_card.insert(0, "Counterspell")
        panel._add_card()

        # Internal list and UI must still only have 1 entry
        assert len(panel.compare_list) == 1
        assert len(panel.table.get_children()) == 1

    def test_search_case_insensitivity(self, root, mock_draft):
        """Verify 'bolt' finds 'Lightning Bolt' logic handles lower/upper correctly."""
        panel = ComparePanel(root, mock_draft, Configuration())

        # Type in lowercase
        panel.entry_card.insert(0, "lightning bolt")
        panel._add_card()

        assert len(panel.compare_list) == 1
        assert panel.compare_list[0][constants.DATA_FIELD_NAME] == "Lightning Bolt"

    def test_column_sync_with_dashboard(self, root, mock_draft):
        """Verify that changing global column settings (e.g. show ATA) updates Compare."""
        # Updated to use new column_configs dictionary
        config = Configuration()
        config.settings.column_configs["compare_table"] = ["name", "ata", "gihwr"]

        panel = ComparePanel(root, mock_draft, config)

        cols = list(panel.table["columns"])
        # Expected: CARD, ATA, GIH WR
        # Column IDs are lowercase
        assert "ata" in cols

    def test_clear_table_logic(self, root, mock_draft):
        """Verify the 'Clear' button wipes all states."""
        panel = ComparePanel(root, mock_draft, Configuration())
        panel.entry_card.insert(0, "Counterspell")
        panel._add_card()

        panel._clear_list()

        assert len(panel.compare_list) == 0
        assert len(panel.table.get_children()) == 0

    def test_not_found_handling(self, root, mock_draft):
        """Edge Case: Verify searching for a non-existent card doesn't crash."""
        panel = ComparePanel(root, mock_draft, Configuration())
        panel.entry_card.insert(0, "Black Lotus")  # Not in ECL set

        try:
            panel._add_card()
            assert len(panel.compare_list) == 0
        except Exception as e:
            pytest.fail(f"ComparePanel crashed on invalid card search: {e}")

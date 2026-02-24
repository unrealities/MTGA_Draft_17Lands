"""
tests/test_taken_cards.py
Comprehensive validation for the Card Pool UI.
Covers: Lifecycle, Type Filtering (all categories), and Stacking.
"""

import pytest
import tkinter
from unittest.mock import MagicMock, patch
from src.ui.windows.taken_cards import TakenCardsPanel
from src.configuration import Configuration, Settings
from src import constants


class TestTakenCardsPanel:
    @pytest.fixture
    def root(self):
        root = tkinter.Tk()
        yield root
        root.destroy()

    @pytest.fixture
    def mock_draft(self):
        """Mock scanner returning a diverse set of card types."""
        draft = MagicMock()
        draft.retrieve_taken_cards.return_value = [
            {
                constants.DATA_FIELD_NAME: "Plains",
                constants.DATA_FIELD_TYPES: [constants.CARD_TYPE_LAND],
                constants.DATA_FIELD_CMC: 0,
            },
            {
                constants.DATA_FIELD_NAME: "Plains",
                constants.DATA_FIELD_TYPES: [constants.CARD_TYPE_LAND],
                constants.DATA_FIELD_CMC: 0,
            },
            {
                constants.DATA_FIELD_NAME: "Aven",
                constants.DATA_FIELD_TYPES: [constants.CARD_TYPE_CREATURE],
                constants.DATA_FIELD_CMC: 2,
            },
            {
                constants.DATA_FIELD_NAME: "Shock",
                constants.DATA_FIELD_TYPES: [constants.CARD_TYPE_INSTANT],
                constants.DATA_FIELD_CMC: 1,
            },
            {
                constants.DATA_FIELD_NAME: "Sol Ring",
                constants.DATA_FIELD_TYPES: [constants.CARD_TYPE_ARTIFACT],
                constants.DATA_FIELD_CMC: 1,
            },
        ]
        draft.retrieve_set_metrics.return_value = MagicMock()
        draft.retrieve_tier_data.return_value = {}
        return draft

    def test_card_stacking(self, root, mock_draft):
        """Verify duplicate cards are stacked with the correct count."""
        panel = TakenCardsPanel(root, mock_draft, Configuration())
        # The stack_cards function adds a "count" key to the dictionary
        plains = next(
            c
            for c in panel.current_display_list
            if c[constants.DATA_FIELD_NAME] == "Plains"
        )
        assert plains["count"] == 2

    def test_filter_lands_removal(self, root, mock_draft):
        """Verify that disabling Lands removes them from the visible list."""
        panel = TakenCardsPanel(root, mock_draft, Configuration())

        # Simulate unchecking 'Lands'
        panel.vars["land"].set(0)
        # Call the update method directly (mimicking the Checkbutton command)
        panel.refresh()

        names = [c[constants.DATA_FIELD_NAME] for c in panel.current_display_list]
        assert "Plains" not in names
        assert "Aven" in names  # Creature should stay

    def test_filter_spells_category(self, root, mock_draft):
        """Verify the 'Spells' filter correctly targets Instants and Sorceries."""
        panel = TakenCardsPanel(root, mock_draft, Configuration())

        panel.vars["spell"].set(0)
        panel.refresh()

        names = [c[constants.DATA_FIELD_NAME] for c in panel.current_display_list]
        assert "Shock" not in names  # Instant removed
        assert "Aven" in names  # Creature stays

    def test_filter_other_category(self, root, mock_draft):
        """Verify 'Other' targets Artifacts, Enchantments, Planeswalkers."""
        panel = TakenCardsPanel(root, mock_draft, Configuration())

        panel.vars["other"].set(0)
        panel.refresh()

        names = [c[constants.DATA_FIELD_NAME] for c in panel.current_display_list]
        assert "Sol Ring" not in names  # Artifact removed
        assert "Aven" in names  # Creature stays

    def test_column_synchronization(self, root, mock_draft):
        """Verify the panel respects global dashboard column settings."""
        config = Configuration()
        config.settings.column_configs["taken_table"] = ["name", "alsa"]
        panel = TakenCardsPanel(root, mock_draft, config)

        # Treeview columns are returned as a tuple of internal IDs
        cols = panel.table["columns"]
        # In the modern app structure, column IDs match the field names (lowercase)
        assert "alsa" in cols

    def test_empty_pool_handling(self, root, mock_draft):
        """Edge Case: Verify panel handles zero cards without crashing."""
        mock_draft.retrieve_taken_cards.return_value = []
        panel = TakenCardsPanel(root, mock_draft, Configuration())
        assert len(panel.current_display_list) == 0

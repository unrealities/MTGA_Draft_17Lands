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
        panel.refresh()

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

    def test_toggle_view_modes(self, root, mock_draft):
        """Verify the toggle button seamlessly switches between List and Visual modes."""
        panel = TakenCardsPanel(root, mock_draft, Configuration())
        panel.refresh()

        # Starts in list mode
        assert panel.view_mode == "list"
        assert panel.table_manager.winfo_manager() != ""
        assert panel.visual_scroller.winfo_manager() == ""

        # Switch to Visual
        panel._toggle_view()
        assert panel.view_mode == "visual"
        assert panel.table_manager.winfo_manager() == ""  # Hidden
        assert panel.visual_scroller.winfo_manager() != ""  # Shown

        # Switch back to List
        panel._toggle_view()
        assert panel.view_mode == "list"
        assert panel.table_manager.winfo_manager() != ""
        assert panel.visual_scroller.winfo_manager() == ""

    @patch("src.ui.windows.taken_cards.copy_deck", return_value="Deck\n1 Plains")
    def test_copy_to_clipboard(self, mock_copy, root, mock_draft):
        panel = TakenCardsPanel(root, mock_draft, Configuration())
        panel.current_display_list = [{"name": "Plains"}]

        panel._copy_to_clipboard()

        assert mock_copy.called
        assert "Plains" in root.clipboard_get()

    def test_render_visual_view(self, root, mock_draft):
        panel = TakenCardsPanel(root, mock_draft, Configuration())
        # Inject diverse CMCs into the mock draft so refresh() picks them up
        mock_draft.retrieve_taken_cards.return_value = [
            {"name": "Land", "types": ["Land"], "cmc": 0},
            {"name": "One", "types": ["Creature"], "cmc": 1},
            {"name": "Two", "types": ["Creature"], "cmc": 2},
            {"name": "Three", "types": ["Creature"], "cmc": 3},
            {"name": "Four", "types": ["Creature"], "cmc": 4},
            {"name": "Five", "types": ["Creature"], "cmc": 5},
            {"name": "Six", "types": ["Creature"], "cmc": 6},
            {"name": "Unknown", "cmc": "error"},
        ]

        panel.view_mode = "visual"
        panel.refresh()

        # Since we pack CardPiles into the scrollable_frame, we verify they were created
        children = panel.visual_scroller.scrollable_frame.winfo_children()
        assert (
            len(children) == 8
        )  # 8 distinct piles (Lands, 1, 2, 3, 4, 5, 6+, Unknown)

    @patch("src.ui.windows.taken_cards.CardToolTip.create")
    def test_on_selection(self, mock_tooltip, root, mock_draft):
        panel = TakenCardsPanel(root, mock_draft, Configuration())
        panel.refresh()

        class MockEvent:
            x = 10
            y = 10

        panel.table.identify_region = MagicMock(return_value="cell")
        panel.table.selection = MagicMock(return_value=["item1"])
        panel.table.item = MagicMock(return_value={"text": "Aven"})

        panel._on_selection(MockEvent())

        mock_tooltip.assert_called_once()
        assert mock_tooltip.call_args[0][1]["name"] == "Aven"

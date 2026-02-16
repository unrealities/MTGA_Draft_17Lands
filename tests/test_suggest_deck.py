"""
tests/test_suggest_deck.py
Validation for the Dynamic Deck Builder UI.
"""

import pytest
import tkinter
from unittest.mock import MagicMock, patch
from src.ui.windows.suggest_deck import SuggestDeckPanel
from src.configuration import Configuration
from src import constants


class TestSuggestDeckPanel:
    @pytest.fixture
    def root(self):
        root = tkinter.Tk()
        yield root
        root.destroy()

    @pytest.fixture
    def mock_draft(self):
        draft = MagicMock()
        draft.retrieve_taken_cards.return_value = []
        draft.retrieve_set_metrics.return_value = MagicMock()
        return draft

    @pytest.fixture
    def mock_variants(self):
        return {
            "BG Consistent": {
                "type": "Midrange",
                "rating": 1500,
                "deck_cards": [{"name": "Mosswood Dreadknight", "cmc": 2, "count": 1}],
            },
            "BG Splash R": {
                "type": "Bomb Splash",
                "rating": 1650,
                "deck_cards": [{"name": "Etali", "cmc": 7, "count": 1}],
            },
        }

    def test_variants_displayed_in_dropdown(self, root, mock_draft, mock_variants):
        with patch(
            "src.ui.windows.suggest_deck.suggest_deck", return_value=mock_variants
        ):
            panel = SuggestDeckPanel(root, mock_draft, Configuration())

            # Check dropdown values
            menu = panel.om_archetype["menu"]
            last = menu.index("end")
            labels = [menu.entrycget(i, "label") for i in range(last + 1)]

            assert any("BG Consistent" in l for l in labels)
            assert any("BG Splash R" in l for l in labels)

    def test_deck_selection_updates_table(self, root, mock_draft, mock_variants):
        with patch(
            "src.ui.windows.suggest_deck.suggest_deck", return_value=mock_variants
        ):
            panel = SuggestDeckPanel(root, mock_draft, Configuration())

            # Select the Splash deck
            splash_label = [k for k in panel.suggestions.keys() if "Splash" in k][0]
            panel._on_deck_selection_change(splash_label)

            # Verify table has Etali
            assert panel.current_deck_list[0]["name"] == "Etali"

"""
tests/test_suggest_deck.py
Validation for the Deck Builder UI.
Fixed: Updated to verify the synchronized Label/Logic state.
"""

import pytest
import tkinter
from unittest.mock import MagicMock, patch
from src.ui.windows.suggest_deck import SuggestDeckPanel
from src.configuration import Configuration, Settings
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
        draft.retrieve_taken_cards.return_value = [{"name": "Dummy"}]
        draft.retrieve_set_metrics.return_value = MagicMock()
        draft.retrieve_tier_data.return_value = {}
        return draft

    @pytest.fixture
    def mock_multi_results(self):
        return {
            "Golgari": {
                "type": "Midrange",
                "rating": 1800,
                "deck_cards": [
                    {
                        "name": "Assassin's Trophy",
                        "cmc": 2,
                        "count": 1,
                        "types": ["Instant"],
                    }
                ],
            },
            "Azorius": {
                "type": "Control",
                "rating": 1100,
                "deck_cards": [
                    {"name": "Island", "cmc": 0, "count": 17, "types": ["Land"]}
                ],
            },
        }

    def test_archetype_sorting_priority(self, root, mock_draft, mock_multi_results):
        with patch(
            "src.ui.windows.suggest_deck.suggest_deck", return_value=mock_multi_results
        ):
            panel = SuggestDeckPanel(root, mock_draft, Configuration())
            current_sel = panel.var_archetype.get()
            assert "Golgari" in current_sel
            assert "1800" in current_sel

    def test_user_switching_archetypes(self, root, mock_draft, mock_multi_results):
        """Verify that manually selecting a deck updates both the label and the card list."""
        with patch(
            "src.ui.windows.suggest_deck.suggest_deck", return_value=mock_multi_results
        ):
            panel = SuggestDeckPanel(root, mock_draft, Configuration())

            # Identify Azorius label
            azorius_label = [k for k in panel.suggestions.keys() if "Azorius" in k][0]

            # Switching logic: must update label AND internal deck
            panel._on_deck_selection_change(azorius_label)

            assert "Azorius" in panel.var_archetype.get()  # Now passes!
            assert panel.current_deck_list[0]["name"] == "Island"

    def test_no_viable_decks_ui_state(self, root, mock_draft):
        with patch("src.ui.windows.suggest_deck.suggest_deck", return_value={}):
            panel = SuggestDeckPanel(root, mock_draft, Configuration())
            assert panel.var_archetype.get() == "No viable decks yet"
            assert len(panel.table.get_children()) == 0

    def test_builder_error_ui_state(self, root, mock_draft):
        with patch(
            "src.ui.windows.suggest_deck.suggest_deck", side_effect=ValueError("Crash")
        ):
            panel = SuggestDeckPanel(root, mock_draft, Configuration())
            assert panel.var_archetype.get() == "Builder Error"

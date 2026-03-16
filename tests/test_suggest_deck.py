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
        # Must return at least one card to bypass the "Not enough cards drafted yet" check
        draft.retrieve_taken_cards.return_value = [{"name": "Forest"}] * 15
        draft.retrieve_set_metrics.return_value = MagicMock()
        draft.retrieve_current_limited_event.return_value = ("SET", "PremierDraft")
        return draft

    @pytest.fixture
    def mock_variants(self):
        stats_dict = {
            "cast_t2": 50,
            "cast_t3": 50,
            "cast_t4": 50,
            "curve_out": 20,
            "removal_t4": 50,
            "mulligans": 10,
            "avg_hand_size": 6.8,
            "screw_t3": 10,
            "screw_t4": 10,
            "color_screw_t3": 10,
            "flood_t5": 10,
        }
        return {
            "BG Consistent": {
                "type": "Midrange",
                "rating": 1500,
                "colors": ["B", "G"],
                "deck_cards": [
                    {
                        "name": "Mosswood Dreadknight",
                        "cmc": 2,
                        "count": 1,
                        "types": ["Creature"],
                        "mana_cost": "{1}{B}{G}",
                        "colors": ["B", "G"],
                    }
                ],
                "sideboard_cards": [],
                "stats": stats_dict,
                "optimization_note": "",
            },
            "BG Splash R": {
                "type": "Bomb Splash",
                "rating": 1650,
                "colors": ["B", "G", "R"],
                "deck_cards": [
                    {
                        "name": "Etali",
                        "cmc": 7,
                        "count": 1,
                        "types": ["Creature"],
                        "mana_cost": "{5}{R}{R}",
                        "colors": ["R"],
                    }
                ],
                "sideboard_cards": [],
                "stats": stats_dict,
                "optimization_note": "",
            },
        }

    def test_variants_displayed_in_dropdown(self, root, mock_draft, mock_variants):
        with patch("src.card_logic.suggest_deck", return_value=mock_variants):
            panel = SuggestDeckPanel(root, mock_draft, Configuration())

            # Execute background task synchronously so assertions don't fire too early
            panel.sim_executor.submit = lambda fn, *args, **kwargs: fn(*args, **kwargs)

            panel.refresh()
            root.update()

            menu = panel.om_archetype["menu"]
            last = menu.index("end")
            labels = [menu.entrycget(i, "label") for i in range(last + 1)]

            assert any("BG Consistent" in l for l in labels)
            assert any("BG Splash R" in l for l in labels)

    def test_deck_selection_updates_table(self, root, mock_draft, mock_variants):
        with patch("src.card_logic.suggest_deck", return_value=mock_variants):
            panel = SuggestDeckPanel(root, mock_draft, Configuration())

            # Execute background task synchronously so assertions don't fire too early
            panel.sim_executor.submit = lambda fn, *args, **kwargs: fn(*args, **kwargs)

            panel.refresh()
            root.update()

            # Select the Splash deck
            splash_label = [k for k in panel.suggestions.keys() if "Splash" in k][0]
            panel._on_deck_selection_change(splash_label)

            # Verify table has Etali
            assert panel.current_deck_list[0]["name"] == "Etali"

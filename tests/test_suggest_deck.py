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
        # Must return at least 23 playable cards to bypass the "Not enough cards drafted yet" check
        draft.retrieve_taken_cards.return_value = [
            {"name": "Lightning Bolt", "types": ["Instant"]}
        ] * 25
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

    def test_render_deck_and_stats(self, root, mock_draft, mock_variants):
        from tkinter import ttk

        panel = SuggestDeckPanel(root, mock_draft, Configuration())
        panel.suggestions = mock_variants

        # Execute render method directly
        panel._render_deck("BG Consistent")

        # Verify deck loaded
        assert panel.current_archetype_key == "BG"
        assert len(panel.current_deck_list) == 1
        assert panel.current_deck_list[0]["name"] == "Mosswood Dreadknight"

        # Verify stats generated from the deck correctly
        def get_all_text(widget):
            texts = []
            for child in widget.winfo_children():
                if isinstance(child, ttk.Label):
                    texts.append(str(child.cget("text")))
                texts.extend(get_all_text(child))
            return texts

        labels = get_all_text(panel.stats_frame)
        assert any("Black (B): 1" in l for l in labels)
        assert any("Green (G): 1" in l for l in labels)

    @patch("src.ui.windows.suggest_deck.CardToolTip.create")
    def test_on_selection(self, mock_tooltip, root, mock_draft, mock_variants):
        panel = SuggestDeckPanel(root, mock_draft, Configuration())
        panel.suggestions = mock_variants
        panel._render_deck("BG Consistent")

        # Simulate click
        panel.table.identify_region = MagicMock(return_value="cell")
        panel.table.selection = MagicMock(return_value=["item1"])
        panel.table.item = MagicMock(
            return_value={
                "text": "Mosswood Dreadknight",
                "values": ["Mosswood Dreadknight"],
            }
        )

        class MockEvent:
            x = 10
            y = 10

        panel._on_selection(MockEvent(), is_sb=False)

        mock_tooltip.assert_called_once()
        assert mock_tooltip.call_args[0][1]["name"] == "Mosswood Dreadknight"

    @patch(
        "src.ui.windows.suggest_deck.copy_deck",
        return_value="Deck\n1 Mosswood Dreadknight",
    )
    def test_copy_to_clipboard(self, mock_copy, root, mock_draft, mock_variants):
        panel = SuggestDeckPanel(root, mock_draft, Configuration())
        panel.suggestions = mock_variants
        panel.var_archetype.set("BG Consistent")

        panel._copy_to_clipboard()

        assert "Mosswood Dreadknight" in root.clipboard_get()

    @patch("src.ui.windows.suggest_deck.CardToolTip.create")
    def test_on_selection(self, mock_tooltip, root, mock_draft, mock_variants):
        panel = SuggestDeckPanel(root, mock_draft, Configuration())
        panel.suggestions = mock_variants
        panel._render_deck("BG Consistent")

        # Simulate click
        panel.table.identify_region = MagicMock(return_value="cell")
        panel.table.selection = MagicMock(return_value=["item1"])
        panel.table.item = MagicMock(
            return_value={
                "text": "Mosswood Dreadknight",
                "values": ["Mosswood Dreadknight"],
            }
        )

        panel._on_selection(MagicMock(x=10, y=10), is_sb=False)

        mock_tooltip.assert_called_once()
        assert mock_tooltip.call_args[0][1]["name"] == "Mosswood Dreadknight"

    def test_copy_to_clipboard(self, root, mock_draft, mock_variants):
        panel = SuggestDeckPanel(root, mock_draft, Configuration())
        panel.suggestions = mock_variants
        panel.var_archetype.set("BG Consistent")

        panel._copy_to_clipboard()

        # Validate formatting output correctly populated clipboard
        assert "Mosswood Dreadknight" in root.clipboard_get()

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

    def test_calculate_suggestions_not_enough_cards(self, root, mock_draft):
        """Verify that having fewer than 22 spells cleanly exits the builder."""
        panel = SuggestDeckPanel(root, mock_draft, Configuration())

        # Less than 22 playable spells
        mock_draft.retrieve_taken_cards.return_value = [
            {"name": "Bolt", "types": ["Instant"]}
        ] * 5

        panel._calculate_suggestions()

        assert "Not enough spells drafted yet" in panel.var_archetype.get()

    def test_handle_builder_error(self, root, mock_draft):
        """Verify that if the AI engine throws an exception, the UI reports it cleanly."""
        panel = SuggestDeckPanel(root, mock_draft, Configuration())

        panel._handle_builder_error("Test Exception")

        assert panel.var_archetype.get() == "Builder Error"
        assert len(panel.suggestions) == 0

    def test_finalize_build_empty(self, root, mock_draft):
        """Verify that if the AI engine returns an empty dict, the UI handles it cleanly."""
        panel = SuggestDeckPanel(root, mock_draft, Configuration())

        panel._finalize_build({})

        assert "Not enough on-color playables" in panel.var_archetype.get()
        assert panel.is_building is False

    def test_update_tables_all_columns_coverage(self, root, mock_draft, mock_variants):
        """Verify that all specific column fields are parsed without KeyErrors in the AI Builder tab."""
        config = Configuration()

        panel = SuggestDeckPanel(root, mock_draft, config)
        panel.suggestions = mock_variants

        # Override active fields manually since SuggestDeckPanel uses static_columns
        panel.table_manager.active_fields = [
            "name",
            "count",
            "cmc",
            "types",
            "colors",
            "tags",
            "gihwr",
        ]

        # Add tags to the mock variant
        panel.suggestions["BG Consistent"]["deck_cards"][0]["tags"] = [
            "removal",
            "card_advantage",
        ]

        panel._render_deck("BG Consistent")

        rows = panel.table.get_children()
        assert len(rows) == 1
        vals = panel.table.item(rows[0])["values"]

        assert vals[0] == "Mosswood Dreadknight"
        # Tag visual mapping ensures the emoji or name is present
        assert "🎯" in str(vals[5]) or "Removal" in str(vals[5])

    def test_clear_table_logic(self, root, mock_draft, mock_variants):
        """Verify that clearing the view wipes out tables, stats, and canvases."""
        panel = SuggestDeckPanel(root, mock_draft, Configuration())
        panel.suggestions = mock_variants
        panel._render_deck("BG Consistent")

        # Add something to the stats and sim frames
        from tkinter import ttk

        ttk.Label(panel.sim_frame, text="Sim").pack()

        panel._clear_table()

        # Verify wiping
        assert len(panel.current_deck_list) == 0
        assert len(panel.current_sb_list) == 0
        assert len(panel.table.get_children()) == 0
        assert len(panel.sim_frame.winfo_children()) == 0
        assert len(panel.stats_frame.winfo_children()) == 0

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

    def test_tab_change_triggers_sample_hand(self, root, mock_draft):
        """Verify switching to the Simulation tab attempts to draw a sample hand."""
        panel = SuggestDeckPanel(root, mock_draft, Configuration())

        with patch.object(panel, "_draw_sample_hand") as mock_draw:
            panel.notebook.select = MagicMock(return_value="tab3")
            # notebook.tab(id, "text") returns a string directly in Tkinter
            panel.notebook.tab = MagicMock(return_value=" SIMULATION & SAMPLE HAND ")
            panel._on_tab_changed(None)

            # We assert it was called because the user navigated to the tab
            mock_draw.assert_called_once()

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

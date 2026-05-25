import pytest
import tkinter
from tkinter import ttk
from unittest.mock import MagicMock, patch
from src.ui.windows.custom_deck import CustomDeckPanel
from src.configuration import Configuration
from src.ui.styles import Theme


class TestCustomDeckPanel:
    @pytest.fixture
    def root(self):
        root = tkinter.Tk()
        Theme.apply(root, "Dark")
        yield root
        root.destroy()

    def test_run_simulation_empty_deck(self, root):
        """Verify simulation gracefully rejects an empty deck."""
        app_context = MagicMock()
        panel = CustomDeckPanel(root, MagicMock(), Configuration(), app_context)

        # Override executor to run inline
        panel.sim_executor.submit = lambda fn, *args, **kwargs: fn(*args, **kwargs)

        panel.deck_list = []
        panel._run_monte_carlo_task(panel.deck_list)
        root.update()

        # Should display warning instead of crashing
        labels = [
            w.cget("text")
            for w in panel.sim_frame.winfo_children()
            if isinstance(w, ttk.Label)
        ]
        assert any("Deck must have 40 cards to analyze" in text for text in labels)

    def test_auto_lands_empty_spells(self, root):
        """Verify Auto-lands does not divide by zero if deck has 0 spells."""
        app_context = MagicMock()
        panel = CustomDeckPanel(root, MagicMock(), Configuration(), app_context)
        panel.sim_executor.submit = lambda fn, *args, **kwargs: fn(*args, **kwargs)

        # Deck with only basic lands
        panel.deck_list = [{"name": "Plains", "types": ["Land", "Basic"]}]

        panel._run_auto_lands_task()
        root.update()

        labels = [
            w.cget("text")
            for w in panel.sim_frame.winfo_children()
            if isinstance(w, ttk.Label)
        ]
        assert any("Add spells to the deck first" in text for text in labels)

    def test_add_and_remove_specific_basic_lands(self, root):
        """Verify the Basic Land toolbar accurately injects and removes lands from the main deck array."""
        app_context = MagicMock()
        panel = CustomDeckPanel(root, MagicMock(), Configuration(), app_context)

        assert len(panel.deck_list) == 0

        # Add 2 Mountains
        panel._add_specific_basic("Mountain")
        panel._add_specific_basic("Mountain")

        # Add 1 Forest
        panel._add_specific_basic("Forest")

        assert len(panel.deck_list) == 2  # Two unique entries

        mountain_entry = next(c for c in panel.deck_list if c["name"] == "Mountain")
        assert mountain_entry["count"] == 2
        assert mountain_entry["colors"] == ["R"]

        # Remove 1 Mountain
        panel._remove_specific_basic("Mountain")
        assert mountain_entry["count"] == 1

        # Remove the Forest
        panel._remove_specific_basic("Forest")
        assert not any(c["name"] == "Forest" for c in panel.deck_list)

    def test_clear_deck_moves_to_sideboard(self, root):
        """Verify clicking 'Clear' moves all spells to the sideboard but completely erases basic lands."""
        panel = CustomDeckPanel(root, MagicMock(), Configuration(), MagicMock())

        panel.deck_list = [
            {"name": "Lightning Bolt", "count": 2, "types": ["Instant"]},
            {"name": "Mountain", "count": 10, "types": ["Basic", "Land"]},
        ]
        panel.sb_list = [{"name": "Shock", "count": 1, "types": ["Instant"]}]

        panel._clear_deck()

        # Deck should be completely empty
        assert len(panel.deck_list) == 0

        # Sideboard should now contain the Bolts, but NOT the Mountains
        assert len(panel.sb_list) == 2
        names = [c["name"] for c in panel.sb_list]
        assert "Lightning Bolt" in names
        assert "Shock" in names
        assert "Mountain" not in names

    def test_refresh_appends_new_draft_picks_to_sideboard(self, root):
        """Verify that as the user drafts new cards, they appear in the sideboard without resetting the main deck."""
        mock_draft = MagicMock()

        # Initially, the user has drafted 1 card
        mock_draft.retrieve_taken_cards.return_value = [{"name": "Card A", "count": 1}]

        panel = CustomDeckPanel(root, mock_draft, Configuration(), MagicMock())
        panel.refresh()

        assert len(panel.sb_list) == 1
        assert panel.known_pool_size == 1

        # User moves the card to their main deck manually
        panel.deck_list.append(panel.sb_list.pop())

        # Draft progresses: User picks a new card (Card B) and another copy of Card A
        mock_draft.retrieve_taken_cards.return_value = [
            {"name": "Card A", "count": 1},
            {"name": "Card A", "count": 1},
            {"name": "Card B", "count": 1},
        ]

        panel.refresh()

        # Known pool size should update to 3
        assert panel.known_pool_size == 3

        # Main deck should still have the 1st copy of Card A untouched
        assert len(panel.deck_list) == 1
        assert panel.deck_list[0]["count"] == 1

        # Sideboard should now contain the NEW copy of Card A, and Card B
        assert len(panel.sb_list) == 2
        sb_counts = {c["name"]: c["count"] for c in panel.sb_list}
        assert sb_counts["Card A"] == 1
        assert sb_counts["Card B"] == 1

    def test_import_deck_from_suggest_tab(self, root):
        """Verify the 'Custom Builder' button from Suggest Deck flawlessly overwrites the current arrays."""
        panel = CustomDeckPanel(root, MagicMock(), Configuration(), MagicMock())

        # Pre-existing state
        panel.deck_list = [{"name": "Old Card"}]

        new_deck = [{"name": "New Main Card", "count": 1}]
        new_sb = [{"name": "New SB Card", "count": 1}]

        panel.import_deck(new_deck, new_sb)

        assert len(panel.deck_list) == 1
        assert panel.deck_list[0]["name"] == "New Main Card"
        assert len(panel.sb_list) == 1

    def test_render_deck_stats_logic(self, root):
        """Verify the UI analytics function correctly parses Pip requirements and Card Types."""
        panel = CustomDeckPanel(root, MagicMock(), Configuration(), MagicMock())

        panel.deck_list = [
            {
                "name": "Double Red",
                "mana_cost": "{R}{R}",
                "count": 2,
                "types": ["Creature"],
                "cmc": 4,
            },
            {
                "name": "Blue Cantrip",
                "mana_cost": "{U}",
                "count": 1,
                "types": ["Instant"],
                "cmc": 1,
            },
            {
                "name": "Mountain",
                "mana_cost": "",
                "count": 10,
                "types": ["Basic", "Land"],
                "cmc": 0,
            },
        ]

        # Force the UI to build the stats frame
        panel._render_deck_stats()
        root.update_idletasks()

        # Recursively extract text from all labels inside the stats frame and its sub-frames
        def get_all_text(widget):
            texts = []
            for child in widget.winfo_children():
                if isinstance(child, ttk.Label):
                    texts.append(str(child.cget("text")))
                texts.extend(get_all_text(child))
            return texts

        labels = get_all_text(panel.stats_frame)
        combined_text = " ".join(labels)

        assert "Creatures: 2" in combined_text
        assert "Non-Creatures: 1" in combined_text
        assert "Lands: 10" in combined_text

        # Verify Pips: 2 copies of {R}{R} = 4 Red Pips. 1 copy of {U} = 1 Blue Pip.
        assert "Red (R): 4" in combined_text
        assert "Blue (U): 1" in combined_text

        # Verify Curve calculation: ( (4*2) + (1*1) ) / 3 spells = 9 / 3 = 3.0
        assert "Avg CMC: 3.00" in combined_text

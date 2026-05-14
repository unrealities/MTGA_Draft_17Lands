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

import pytest
import tkinter
from unittest.mock import MagicMock, patch
from src.ui.dashboard_recap import DraftRecapScreen
from src.ui.styles import Theme


class TestDraftRecapScreen:
    @pytest.fixture
    def root(self):
        root = tkinter.Tk()
        Theme.apply(root, "Dark")
        yield root
        root.destroy()

    @pytest.fixture
    def mock_metrics(self):
        metrics = MagicMock()
        # Set global mean to 55.0 and standard deviation to 4.0
        metrics.get_metrics.return_value = (55.0, 4.0)
        return metrics

    def test_recap_calculates_grades_and_synergy(self, root, mock_metrics):
        """Verify the recap screen calculates Pool Grade and Extracts Top Tribes/Roles."""
        recap = DraftRecapScreen(root)

        pool = []
        # Add 23 great cards (GIHWR 60.0) -> Average will be 60.0.
        # Z-Score = (60.0 - 55.0) / 4.0 = 1.25.
        # Power = 75 + (1.25 * 12) = 90 (S Tier)
        for i in range(23):
            pool.append(
                {
                    "name": f"Great Card {i}",
                    "types": ["Creature"],
                    "subtypes": ["Ninja", "Human"],  # Tribal Synergy
                    "tags": ["removal"],  # Role Synergy
                    "deck_colors": {
                        "All Decks": {"gihwr": 60.0, "alsa": 1.0, "ata": 2.0}
                    },
                }
            )

        # The engine requires at least 40 cards to validate a draft pool
        for i in range(17):
            pool.append(
                {"name": "Plains", "types": ["Land", "Basic"], "deck_colors": {}}
            )

        recap.update_summary(pool, mock_metrics, "draft-123", "PremierDraft")

        # Verify Grade Label
        grade_text = recap.lbl_recovery_grade.cget("text")
        assert "90/100" in grade_text
        assert "S (God Tier)" in grade_text

        # Verify Tribal/Role Extraction
        tribes_text = recap.lbl_synergy_tribes.cget("text")
        assert "Ninja" in tribes_text
        assert "Human" in tribes_text

        roles_text = recap.lbl_synergy_roles.cget("text")
        assert "Removal" in roles_text

    def test_recap_detects_steals_and_reaches(self, root, mock_metrics):
        """Verify logic that identifies cards drafted later than their ALSA or earlier than their ATA."""
        recap = DraftRecapScreen(root)

        pool = []

        # In a 14-card pack, Pick 13 is very late.
        # This card has ALSA 3.0, but we got it P1P13! It's a massive steal (+10).
        # We also pad the pool to exactly 42 cards to trigger the logic block properly.
        pool.append(
            {
                "name": "Massive Steal",
                "types": ["Creature"],
                "deck_colors": {"All Decks": {"gihwr": 60.0, "alsa": 3.0}},
            }
        )

        for i in range(41):
            pool.append(
                {
                    "name": f"Filler {i}",
                    "types": ["Creature"],
                    "deck_colors": {
                        "All Decks": {"gihwr": 50.0, "alsa": 1.0, "ata": 1.0}
                    },
                }
            )

        # The first card in the array represents P1P1. The 13th card represents P1P13.
        # Let's insert the "Massive Steal" at index 12 (P1P13).
        steal_card = pool.pop(0)
        pool.insert(12, steal_card)

        recap.update_summary(pool, mock_metrics, "draft-123", "PremierDraft")

        steals_text = recap.lbl_recap_steals.cget("text")
        assert "Massive Steal" in steals_text
        assert "(P1P13" in steals_text  # Pack 1 Pick 13

    @patch("src.ui.dashboard_recap.threading.Thread")
    def test_17lands_api_request_triggers(self, mock_thread, root, mock_metrics):
        """Verify the 17Lands async fetch is spawned if a draft_id is provided."""
        recap = DraftRecapScreen(root)

        pool = [{"name": f"Card {i}", "deck_colors": {}} for i in range(40)]

        recap.update_summary(pool, mock_metrics, "valid-uuid-1234", "PremierDraft")

        # Verify the background thread was started to query the API
        mock_thread.assert_called_once()

    def test_recap_handles_empty_or_small_pools(self, root, mock_metrics):
        """Verify no errors are thrown if the pool is too small to analyze."""
        recap = DraftRecapScreen(root)

        # 10 cards is too small for a draft
        pool = [{"name": f"Card {i}", "deck_colors": {}} for i in range(10)]

        try:
            recap.update_summary(pool, mock_metrics, "draft-123", "PremierDraft")
        except Exception:
            pytest.fail("Recap screen crashed on small pool.")

        # UI should not have updated
        assert "Pool Power Grade: --" in recap.lbl_recovery_grade.cget("text")


def _long_pool():
    """A 50-card pool whose stat boxes all fill to six long lines."""
    pool = []
    for i in range(40):
        pool.append(
            {
                "name": f"Blossom-Blessed Archangel of Dawn {i}",
                "cmc": 1 + i % 6,
                "types": ["Creature"] if i % 2 else ["Sorcery"],
                "subtypes": ["Human", "Soldier", "Angel"],
                "tags": ["removal", "card_advantage", "evasion"],
                "rarity": "rare" if i % 3 == 0 else "uncommon",
                "deck_colors": {
                    "All Decks": {"gihwr": 52.0 + i % 9, "alsa": 1.5, "ata": 9.0}
                },
            }
        )
    pool.append(
        {"name": "Gilded Gate", "types": ["Land"], "deck_colors": {"All Decks": {}}}
    )
    pool += [{"name": "Plains", "types": ["Land", "Basic"]} for _ in range(9)]
    return pool


class TestDraftRecapLayout:
    """Issue #238: the recap must never silently crop its stat boxes."""

    @pytest.fixture
    def root(self):
        root = tkinter.Tk()
        Theme.apply(root, "Dark")
        yield root
        root.destroy()

    def _render(self, root, tk_scaling, width, height):
        root.tk.call("tk", "scaling", tk_scaling)
        host = tkinter.Toplevel(root)
        host.geometry(f"{width}x{height}+0+0")
        recap = DraftRecapScreen(host)
        recap.pack(fill="both", expand=True)
        metrics = MagicMock()
        metrics.get_metrics.return_value = (55.0, 3.5)
        with patch("src.ui.dashboard_recap.threading.Thread"):
            recap.update_summary(_long_pool(), metrics, "", "PremierDraft")
        for tab in range(3):
            recap.recap_notebook.select(tab)
            for _ in range(3):
                host.update()
        return recap

    def _stat_boxes(self, recap):
        return [
            getattr(recap, name).master
            for name in (
                "lbl_recap_archetypes",
                "lbl_recap_best",
                "lbl_recap_steals",
                "lbl_recap_reaches",
                "lbl_synergy_tribes",
                "lbl_synergy_roles",
                "lbl_synergy_staples",
                "lbl_synergy_lands",
                "lbl_recap_rares",
            )
        ]

    def _boxes_by_tab(self, recap):
        """Yield (tab index, stat box) with that tab selected and laid out."""
        tabs = recap.recap_notebook.tabs()
        for box in self._stat_boxes(recap):
            tab = next(i for i, t in enumerate(tabs) if str(box).startswith(t + "."))
            recap.recap_notebook.select(tab)
            recap.update()
            yield tab, box

    def test_short_pane_scrolls_instead_of_cropping(self, root):
        recap = self._render(root, 192 / 72, 900, 320)

        for tab, box in self._boxes_by_tab(recap):
            assert box.winfo_ismapped(), (tab, box.cget("text"))
            assert box.winfo_height() >= box.winfo_reqheight(), box.cget("text")

        for tab, scroller in enumerate(recap.tab_scrollers):
            recap.recap_notebook.select(tab)
            recap.update()
            assert scroller.canvas.yview() != (0.0, 1.0), tab

    def test_tall_pane_fills_without_scrolling(self, root):
        recap = self._render(root, 96 / 72, 1400, 1100)

        for tab, scroller in enumerate(recap.tab_scrollers):
            recap.recap_notebook.select(tab)
            recap.update()
            assert scroller.canvas.yview() == (0.0, 1.0), tab
            # The content stretches to the visible area so the grid rows expand.
            assert scroller.content.winfo_height() >= scroller.canvas.winfo_height()

    def test_stat_text_wraps_to_its_own_box(self, root):
        recap = self._render(root, 192 / 72, 900, 320)
        for _, box in self._boxes_by_tab(recap):
            label = box.winfo_children()[0]
            wrap = int(str(label.cget("wraplength")) or 0)
            assert 0 < wrap <= label.winfo_width()

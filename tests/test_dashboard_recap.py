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

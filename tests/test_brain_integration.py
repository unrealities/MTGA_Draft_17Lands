"""
tests/test_brain_integration.py
Integration test for the Draft Advisor (The Brain).
Verifies contextual scoring and reasoning logic.
"""

import pytest
import tkinter
from tkinter import ttk
import os
import json
import time
from src.ui.app import DraftApp
from src.log_scanner import ArenaScanner
from src.configuration import Configuration
from src.limited_sets import SetDictionary, SetInfo


# --- MOCK DATA GENERATOR ---
def create_mock_dataset(path):
    data = {
        "meta": {"version": 3.0, "game_count": 10000},
        "card_ratings": {
            "101": {
                "name": "Overwhelming Ancient",
                "cmc": 6,
                "types": ["Creature"],
                "deck_colors": {"All Decks": {"gihwr": 62.0, "alsa": 1.5}},
            },
            "102": {
                "name": "Reliable Bear",
                "cmc": 2,
                "types": ["Creature"],
                "deck_colors": {"All Decks": {"gihwr": 54.0, "alsa": 4.5}},
            },
            "103": {
                "name": "Final Strike",
                "cmc": 2,
                "types": ["Instant"],
                "deck_colors": {"All Decks": {"gihwr": 55.0, "alsa": 3.0}},
            },
        },
    }
    with open(path, "w") as f:
        json.dump(data, f)


class TestBrainIntegration:
    @pytest.fixture
    def env(self, tmp_path, monkeypatch):
        sets_dir = tmp_path / "Sets"
        sets_dir.mkdir()
        logs_dir = tmp_path / "Logs"
        logs_dir.mkdir()

        monkeypatch.setattr("src.constants.SETS_FOLDER", str(sets_dir))
        monkeypatch.setattr("src.constants.DRAFT_LOG_FOLDER", str(logs_dir))

        log_file = tmp_path / "Player.log"
        log_file.write_text("MTGA Log Start\n")

        dataset_path = sets_dir / "TEST_PremierDraft_All_Data.json"
        create_mock_dataset(dataset_path)

        mock_sets = SetDictionary(
            data={
                "Test Set": SetInfo(
                    arena=["TEST"], seventeenlands=["TEST"], set_code="TEST"
                )
            }
        )

        root = tkinter.Tk()
        root.withdraw()
        config = Configuration()
        config.settings.arena_log_location = str(log_file)

        # FIX: Ensure retrieve_unknown is True and Scanner is linked to mock sets
        scanner = ArenaScanner(str(log_file), mock_sets, retrieve_unknown=True)
        scanner.retrieve_set_data(str(dataset_path))

        app = DraftApp(root, scanner, config)

        yield {"app": app, "log": log_file, "root": root}
        root.destroy()

    def test_advisor_prioritizes_structural_needs(self, env):
        app, log, root = env["app"], env["log"], env["root"]

        # 1. Simulate Event Join (Crucial for setting scanner.draft_type)
        with open(log, "a") as f:
            f.write(
                '[UnityCrossThreadLogger]==> EventJoin {"id":"1","request":"{\\"EventName\\":\\"PremierDraft_TEST_20240101\\"}"}\n'
            )

        app._update_loop()
        root.update()

        # 2. Inject a 'clunky' card pool (Three 6-drops)
        app.orchestrator.scanner.taken_cards = ["101", "101", "101"]

        # 3. Simulate Pack Entry (Pick 16 to trigger 'Critical' logic)
        p1p16 = (
            '[UnityCrossThreadLogger]Draft.Notify {"draftId":"1","SelfPick":16,"SelfPack":2,'
            '"PackCards":"101,102,103"}\n'
        )
        with open(log, "a") as f:
            f.write(p1p16)

        # 4. Trigger Brain Logic
        app._update_loop()

        # 5. UI Pump (Wait for Advisor labels to render)
        # We loop update to ensure the labels are generated
        for _ in range(10):
            root.update_idletasks()
            root.update()
            time.sleep(0.05)

        advisor_labels = []

        def find_labels(widget):
            if isinstance(widget, (ttk.Label, tkinter.Label)):
                advisor_labels.append(str(widget.cget("text")))
            for child in widget.winfo_children():
                find_labels(child)

        find_labels(app.advisor_panel)

        # VERIFICATION:
        # A. Check for Interaction reasoning (Final Strike)
        assert any(
            "Critical Removal Need" in l or "Interaction Priority" in l
            for l in advisor_labels
        )

        # B. Check for Curve reasoning (Reliable Bear)
        assert any("2-Drops" in l for l in advisor_labels)

        # C. Verify the Dashboard 'Value' column is augmented
        tree = app.dashboard.get_treeview("pack")
        rows = tree.get_children()
        # Card 102 (Bear) should be near top due to structural bonus
        bear_row = [
            tree.item(r)["values"]
            for r in rows
            if "BEAR" in str(tree.item(r)["values"][0]).upper()
        ][0]
        # Contextual Score (index 1) should be > Raw WR (54.0)
        assert float(bear_row[1]) > 54.0

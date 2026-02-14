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
                "colors": ["G"],
                "mana_cost": "{4}{G}{G}",
                "deck_colors": {"All Decks": {"gihwr": 62.0, "alsa": 1.5}},
            },
            "102": {
                "name": "Reliable Bear",
                "cmc": 2,
                "types": ["Creature"],
                "colors": ["G"],
                "mana_cost": "{1}{G}",
                "deck_colors": {"All Decks": {"gihwr": 54.0, "alsa": 4.5}},
            },
            "103": {
                "name": "Final Strike",
                "cmc": 2,
                "types": ["Instant"],
                "colors": ["B"],
                "mana_cost": "{1}{B}",
                "deck_colors": {"All Decks": {"gihwr": 55.0, "alsa": 3.0}},
            },
            # A Splashable Bomb (Red, Single Pip)
            "104": {
                "name": "Fireball",
                "cmc": 3,
                "types": ["Sorcery"],
                "colors": ["R"],
                "mana_cost": "{2}{R}",
                "deck_colors": {
                    "All Decks": {"gihwr": 65.0, "alsa": 1.0}
                },  # High WR -> Bomb
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

        scanner = ArenaScanner(str(log_file), mock_sets, retrieve_unknown=True)
        scanner.retrieve_set_data(str(dataset_path))

        app = DraftApp(root, scanner, config)

        yield {"app": app, "log": log_file, "root": root}
        root.destroy()

    def test_advisor_prioritizes_structural_needs(self, env):
        app, log, root = env["app"], env["log"], env["root"]

        # 1. Simulate Event Join
        with open(log, "a") as f:
            f.write(
                '[UnityCrossThreadLogger]==> EventJoin {"id":"1","request":"{\\"EventName\\":\\"PremierDraft_TEST_20240101\\"}"}\n'
            )

        app._update_loop()
        root.update()

        # 2. Inject a 'clunky' card pool (Three 6-drops in Green)
        # This establishes "Green" as our main color
        app.orchestrator.scanner.taken_cards = ["101", "101", "101"]

        # 3. Simulate Pack Entry (Pick 20 - Late Pack 2)
        # We are SOLIDLY Green.
        # 102 (Green Bear) should be prioritized due to curve/color.
        # 103 (Black Instant) is off-color, single pip.
        # 104 (Red Bomb) is off-color, single pip (Splashable).
        p1p16 = (
            '[UnityCrossThreadLogger]Draft.Notify {"draftId":"1","SelfPick":20,"SelfPack":2,'
            '"PackCards":"101,102,103,104"}\n'
        )
        with open(log, "a") as f:
            f.write(p1p16)

        app._update_loop()
        for _ in range(5):
            root.update()
            time.sleep(0.01)

        # Get Recommendations via Dashboard
        tree = app.dashboard.get_treeview("pack")
        rows = tree.get_children()

        # Map Name -> Score
        scores = {}
        for r in rows:
            vals = tree.item(r)["values"]
            name = str(vals[0]).replace("⭐ ", "")  # Remove decorators
            score = float(vals[1])
            scores[name] = score

        # VERIFICATIONS

        # 1. Curve Need: Reliable Bear (102) should be boosted because we have 0 2-drops and are in Green.
        assert scores["Reliable Bear"] > 54.0  # Base WR 54.0

        # 2. Lane Commitment: Final Strike (103) is Black. We are Green.
        # It's late (Pick 20). Penalty should be heavy.
        # Base WR 55.0.
        assert scores["Final Strike"] < 50.0

        # 3. Splash Logic: Fireball (104). Base WR 65.0. Z-Score > 1.5. Single Pip {2}{R}.
        # This should be identified as a "Splashable Bomb" and penalized LESS than Final Strike.
        assert scores["Fireball"] > scores["Final Strike"]

"""
tests/test_brain_integration.py
Integration test for the Pro Tour Edition Advisor.
Verifies Karsten Math, Wheel Greed, and Weighted Scoring.
"""

import pytest
import tkinter
from tkinter import ttk
import os
import json
import time
from unittest.mock import patch  # Added patch import
from src.ui.app import DraftApp
from src.log_scanner import ArenaScanner
from src.configuration import Configuration
from src.limited_sets import SetDictionary, SetInfo
from src import constants
from src.utils import Result


# --- MOCK DATA GENERATOR ---
def create_mock_dataset(path):
    data = {
        "meta": {"version": 3.0, "game_count": 10000},
        "card_ratings": {
            "101": {
                "name": "Green Hulk",
                "cmc": 6,
                "types": ["Creature"],
                "colors": ["G"],
                "mana_cost": "{4}{G}{G}",
                "deck_colors": {"All Decks": {"gihwr": 62.0, "alsa": 2.0}},
            },
            "102": {
                "name": "Red Bomb Double Pip",
                "cmc": 4,
                "types": ["Creature"],
                "colors": ["R"],
                "mana_cost": "{2}{R}{R}",  # Unsplashable
                "deck_colors": {"All Decks": {"gihwr": 68.0, "alsa": 1.5}},
            },
            "103": {
                "name": "Black Removal Single Pip",
                "cmc": 2,
                "types": ["Instant"],
                "colors": ["B"],
                "mana_cost": "{1}{B}",  # Splashable
                "deck_colors": {"All Decks": {"gihwr": 58.0, "alsa": 3.0}},
            },
            "104": {
                "name": "Wheeling Dork",
                "cmc": 1,
                "types": ["Creature"],
                "colors": ["G"],
                "mana_cost": "{G}",
                # ALSA 13.0 means it goes very late
                "deck_colors": {"All Decks": {"gihwr": 55.0, "alsa": 13.0}},
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

        # PATCH: check_file_integrity to allow small datasets (the mock has <100 cards)
        # We need to return the dict from create_mock_dataset as the second return value
        with open(dataset_path, "r") as f:
            mock_data_dict = json.load(f)

        with patch(
            "src.dataset.check_file_integrity",
            return_value=(Result.VALID, mock_data_dict),
        ):
            scanner = ArenaScanner(str(log_file), mock_sets, retrieve_unknown=True)
            scanner.retrieve_set_data(str(dataset_path))

            # Explicitly set the draft type so the scanner processes the pack data
            scanner.draft_type = constants.LIMITED_TYPE_DRAFT_PREMIER_V2
            scanner.number_of_players = 8

            # PATCH: Prevent the app's internal timer from conflicting with test logic
            with patch("src.ui.app.DraftApp._schedule_update"):
                app = DraftApp(root, scanner, config)
                yield {"app": app, "log": log_file, "root": root}

        root.destroy()

    def test_pro_logic_scenarios(self, env):
        app, log, root = env["app"], env["log"], env["root"]

        # 1. Establish Green Lane
        app.orchestrator.scanner.taken_cards = ["101", "101", "101"]  # 3 Green Hulks

        # 2. Simulate Late Pack 2 (Pick 20)
        # We are Green.
        p2p5 = (
            '[UnityCrossThreadLogger]Draft.Notify {"draftId":"1","SelfPick":20,"SelfPack":2,'
            '"PackCards":"101,102,103,104"}\n'
        )
        with open(log, "a") as f:
            f.write(p2p5)

        # Force update manually
        app._update_loop()

        # Pump events
        for _ in range(5):
            root.update()

        tree = app.dashboard.get_treeview("pack")
        rows = tree.get_children()

        scores = {}
        for r in rows:
            vals = tree.item(r)["values"]
            name = str(vals[0]).replace("⭐ ", "")
            # Ensure index 1 exists (score)
            if len(vals) > 1:
                score = float(vals[1])
                scores[name] = score

        # --- VERIFICATION 1: Double Pip Penalty ---
        # "Red Bomb Double Pip" has 68% GIHWR (Highest in pack).
        # But we are Green, and it costs {2}{R}{R}.
        # Score should be 0 or very low.
        assert "Red Bomb Double Pip" in scores
        assert scores["Red Bomb Double Pip"] < 10.0

        # --- VERIFICATION 2: Single Pip Splash ---
        # "Black Removal Single Pip" is {1}{B}. 58% WR.
        # Should be scored higher than the Double Pip bomb because it's splashable.
        assert "Black Removal Single Pip" in scores
        assert scores["Black Removal Single Pip"] > scores["Red Bomb Double Pip"]

    def test_wheel_greed_logic(self, env):
        app, log, root = env["app"], env["log"], env["root"]

        # Pick 2.
        p1p2 = (
            '[UnityCrossThreadLogger]Draft.Notify {"draftId":"1","SelfPick":2,"SelfPack":1,'
            '"PackCards":"101,104"}\n'
        )
        with open(log, "a") as f:
            f.write(p1p2)

        app._update_loop()
        for _ in range(5):
            root.update()

        tree = app.dashboard.get_treeview("pack")
        rows = tree.get_children()

        scores = {}
        for r in rows:
            vals = tree.item(r)["values"]
            name = str(vals[0]).replace("⭐ ", "")
            if len(vals) > 1:
                score = float(vals[1])
                scores[name] = score

        # "Wheeling Dork" (104) has ALSA 13.0.
        # At Pick 2, it is extremely likely to wheel.
        # Engine should suppress its score relative to its raw power.
        # Raw WR 55.0.
        # Wheel Penalty 0.8x -> Effective ~44.
        assert "Wheeling Dork" in scores
        assert scores["Wheeling Dork"] < 50.0

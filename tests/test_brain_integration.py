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
from unittest.mock import patch
from src.ui.app import DraftApp
from src.log_scanner import ArenaScanner
from src.configuration import Configuration
from src.limited_sets import SetDictionary, SetInfo
from src import constants
from src.advisor.engine import DraftAdvisor
from src.utils import Result
from src.constants import BASE_DIR


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
            "105": {
                "name": "Golgari Guildgate",
                "cmc": 0,
                "types": ["Land"],
                "colors": ["B", "G"],
                "mana_cost": "",
                "deck_colors": {"All Decks": {"gihwr": 52.0, "alsa": 5.0}},
            },
            # Filler cards to prevent VOR scarcity bonus from ruining test math
            "106": {
                "name": "Filler G1",
                "cmc": 2,
                "types": ["Creature"],
                "colors": ["G"],
                "deck_colors": {"All Decks": {"gihwr": 56.0, "alsa": 5.0}},
            },
            "107": {
                "name": "Filler G2",
                "cmc": 2,
                "types": ["Creature"],
                "colors": ["G"],
                "deck_colors": {"All Decks": {"gihwr": 56.0, "alsa": 5.0}},
            },
            "108": {
                "name": "Filler G3",
                "cmc": 2,
                "types": ["Creature"],
                "colors": ["G"],
                "deck_colors": {"All Decks": {"gihwr": 56.0, "alsa": 5.0}},
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
        temp_dir = tmp_path / "Temp"
        temp_dir.mkdir()

        monkeypatch.setattr("src.constants.SETS_FOLDER", str(sets_dir))
        monkeypatch.setattr("src.constants.DRAFT_LOG_FOLDER", str(logs_dir))
        monkeypatch.setattr("src.constants.TEMP_FOLDER", str(temp_dir))

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

        # 1. Simulate Late Pack 2 (Pick 20)
        p2p5 = (
            '[UnityCrossThreadLogger]Draft.Notify {"draftId":"1","SelfPick":20,"SelfPack":2,'
            '"PackCards":"102,103,104,106"}\n'
        )
        with open(log, "a") as f:
            f.write(p2p5)

        # Force update manually
        app._update_loop()

        # 2. Establish a Green-Black lane: 3 Green Hulks, 2 Black removal
        # spells. Set after the log is read, as a new draft clears the pool.
        app.orchestrator.scanner.taken_cards = ["101", "101", "101", "103", "103"]
        app._refresh_ui_data()

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

        # --- VERIFICATION 1: The dashboard shows the advisor's scores ---
        scanner = app.orchestrator.scanner
        metrics = scanner.retrieve_set_metrics()
        pack = scanner.retrieve_current_pack_cards()
        recs = DraftAdvisor(metrics, scanner.retrieve_taken_cards()).evaluate_pack(
            pack, 5, current_pack=2
        )
        assert len(scanner.retrieve_taken_cards()) == 5
        assert scores == {r.card_name: round(r.contextual_score) for r in recs}

        # --- VERIFICATION 2: Off-color penalty ---
        # "Red Bomb Double Pip" has 68% GIHWR (Highest in pack), but we are
        # Green/Black, so it scores less than it would for an empty pool.
        red = next(r for r in recs if r.card_name == "Red Bomb Double Pip")
        fresh = next(
            r
            for r in DraftAdvisor(metrics, []).evaluate_pack(pack, 5, current_pack=2)
            if r.card_name == "Red Bomb Double Pip"
        )
        assert red.contextual_score < fresh.contextual_score
        assert any(reason.startswith("Off-Color") for reason in red.reasoning)

    def test_wheel_greed_logic(self, env):
        app, log, root = env["app"], env["log"], env["root"]

        # Pick 2.
        p1p2 = (
            '[UnityCrossThreadLogger]Draft.Notify {"draftId":"1","SelfPick":2,"SelfPack":1,'
            '"PackCards":"101,102,103,105,104"}\n'
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
        assert "Wheeling Dork" in scores
        assert scores["Wheeling Dork"] < 50.0

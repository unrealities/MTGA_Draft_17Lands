"""
tests/test_integration_log_pipeline.py
"""

import pytest
import tkinter
import os
import shutil
import time
from unittest.mock import patch
from src.ui.app import DraftApp
from src.log_scanner import ArenaScanner
from src.configuration import Configuration
from src.limited_sets import SetDictionary, SetInfo
from src.ui.styles import Theme

OTJ_SNAPSHOT = os.path.join(
    os.getcwd(), "tests", "data", "OTJ_PremierDraft_Data_2024_5_3.json"
)


class TestLogPipelineIntegration:
    @pytest.fixture
    def env(self, tmp_path, monkeypatch):
        temp_sets = tmp_path / "Sets"
        temp_sets.mkdir()
        temp_logs = tmp_path / "Logs"
        temp_logs.mkdir()
        monkeypatch.setattr("src.constants.SETS_FOLDER", str(temp_sets))
        monkeypatch.setattr("src.constants.DRAFT_LOG_FOLDER", str(temp_logs))

        log_file = tmp_path / "Player.log"
        log_file.write_text("MTGA Log Start\n")
        target_path = temp_sets / "OTJ_PremierDraft_All_Data.json"
        shutil.copy(OTJ_SNAPSHOT, target_path)

        mock_sets = SetDictionary(
            data={
                "Outlaws": SetInfo(
                    arena=["OTJ"], seventeenlands=["OTJ"], set_code="OTJ"
                )
            }
        )
        mock_data = (
            [
                (
                    "OTJ",
                    "PremierDraft",
                    "All",
                    "2024-04-16",
                    "2024-05-03",
                    5000,
                    str(target_path),
                    "2024-05-03 12:00:00",
                )
            ],
            [],
        )
        monkeypatch.setattr(
            "src.log_scanner.retrieve_local_set_list", lambda *a, **k: mock_data
        )
        monkeypatch.setattr(
            "src.utils.retrieve_local_set_list", lambda *a, **k: mock_data
        )

        config = Configuration()
        config.settings.arena_log_location = str(log_file)
        config.card_data.latest_dataset = "OTJ_PremierDraft_All_Data.json"

        root = tkinter.Tk()
        # Initialize theme to stabilize style database
        Theme.apply(root, "Dark")
        root.withdraw()

        scanner = ArenaScanner(
            str(log_file),
            mock_sets,
            sets_location=str(temp_sets),
            retrieve_unknown=True,
        )
        scanner.file_size = 0

        # We must prevent the scheduled update loop from running wild during tests
        with patch("src.ui.app.DraftApp._schedule_update"):
            app = DraftApp(root, scanner, config)
            # Cancel any potentially lingering tasks (though patch should catch them)
            if app._update_task_id:
                try:
                    root.after_cancel(app._update_task_id)
                except:
                    pass

            yield {"app": app, "log": log_file, "root": root}

        try:
            root.destroy()
        except tkinter.TclError:
            pass

    def test_full_draft_cycle_and_auto_filter_logic(self, env):
        app, log, root = env["app"], env["log"], env["root"]
        with open(log, "a") as f:
            f.write(
                f'[UnityCrossThreadLogger]==> Event_Join {{"id":"1","request":"{{\\"EventName\\":\\"PremierDraft_OTJ_20240416\\"}}"}}\n'
            )

        # Manually trigger the update loop logic since we patched the scheduler
        app._update_loop()

        ready = False
        for _ in range(50):
            root.update()
            if not app._loading and "OTJ" in app.vars["data_source"].get():
                ready = True
                break
            time.sleep(0.1)
        assert ready

        p1p1 = (
            '[UnityCrossThreadLogger]==> LogBusinessEvents {"id":"2","request":"{\\"PackNumber\\":1,\\"PickNumber\\":1,'
            '\\"CardsInPack\\":[90734,90584,90631,90362,90440,90349,90486,90527,90406,90439,90488,90480,90388,90459]}"}\n'
        )
        with open(log, "a") as f:
            f.write(p1p1)

        # Pumping the loop to ensure detection
        for _ in range(2):
            app._update_loop()
            root.update()

        tree = app.dashboard.get_treeview("pack")
        rows = []
        for _ in range(50):  # Increase wait for slow CI environments
            root.update()
            rows = tree.get_children()
            if len(rows) >= 14:
                break
            time.sleep(0.1)

        assert len(rows) >= 14

        # Verify that the table is populated with known cards from the pack.
        first_row_val = str(tree.item(rows[0])["values"][0])
        assert any(
            x in first_row_val for x in ["Back for More", "90734", "Vadmir", "90459"]
        )

    def test_signals_and_missing_cards_logic(self, env):
        app, log, root = env["app"], env["log"], env["root"]
        with open(log, "a") as f:
            f.write(
                f'[UnityCrossThreadLogger]==> Event_Join {{"id":"1","request":"{{\\"EventName\\":\\"PremierDraft_OTJ\\"}}"}}\n'
            )
        app._update_loop()
        for _ in range(30):
            root.update()
            if not app._loading and "OTJ" in app.vars["data_source"].get():
                break
            time.sleep(0.1)

        p1p1 = (
            '[UnityCrossThreadLogger]==> LogBusinessEvents {"id":"2","request":"{\\"PackNumber\\":1,\\"PickNumber\\":1,'
            '\\"CardsInPack\\":[90734, 90584, 90459]}"}\n'
        )
        with open(log, "a") as f:
            f.write(p1p1)
        app._update_loop()
        root.update()

        pick1 = '[UnityCrossThreadLogger]==> Event_PlayerDraftMakePick {"id":"3","request":"{\\"Pack\\":1,\\"Pick\\":1,\\"GrpId\\":90734}"}\n'
        with open(log, "a") as f:
            f.write(pick1)
        app._update_loop()
        root.update()

        p1p9 = '[UnityCrossThreadLogger]Draft.Notify {"draftId":"1","SelfPick":9,"SelfPack":1,"PackCards":"90459"}\n'
        with open(log, "a") as f:
            f.write(p1p9)
        app._update_loop()
        root.update()

        tree = app.dashboard.get_treeview("missing")
        rows = []
        for _ in range(30):
            root.update_idletasks()
            root.update()
            rows = tree.get_children()
            if len(rows) > 0:
                break
            time.sleep(0.1)

        assert len(rows) > 0
        missing_names = [str(tree.item(r)["values"][0]) for r in rows]
        assert any("Wrangler" in name or "90584" in name for name in missing_names)

# tests/test_splash_robust.py
import pytest
import tkinter
import time
from unittest.mock import MagicMock, patch
from src.ui.windows.splash import SplashWindow


class TestSplashWindow:
    @pytest.fixture
    def root(self):
        root = tkinter.Tk()
        yield root
        root.destroy()

    def test_splash_completes_task_and_triggers_callback(self, root):
        """Verify that the result of the task is correctly passed to on_complete."""

        def mock_task(progress_cb):
            progress_cb("working")
            return {"data": 123}

        completion_result = []

        def on_done(result, splash_inst):
            completion_result.append(result)
            splash_inst.close()

        with patch("tkinter.Toplevel.wm_overrideredirect"):
            splash = SplashWindow(root, mock_task, on_done)

            # Allow the queue loop to pump
            for _ in range(20):
                root.update()
                if completion_result:
                    break
                time.sleep(0.05)

            assert len(completion_result) == 1
            assert completion_result[0]["data"] == 123
            assert splash.status_var.get() == "WORKING"

    def test_splash_handles_task_exception(self, root):
        """Verify background exceptions are caught and displayed."""

        def broken_task(progress_cb):
            raise RuntimeError("Database Locked")

        with patch("tkinter.Toplevel.wm_overrideredirect"), patch(
            "tkinter.messagebox.showerror"
        ) as mock_err:
            splash = SplashWindow(root, broken_task, MagicMock())

            for _ in range(20):
                root.update()
                if "ERROR" in splash.status_var.get():
                    break
                time.sleep(0.05)

            assert splash.status_var.get() == "LOAD ERROR"
            mock_err.assert_called_once()
            assert "Database Locked" in mock_err.call_args[0][1]

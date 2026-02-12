"""
src/ui/windows/splash.py
Provides a non-blocking splash screen with robust error catching during app hand-off.
"""

import tkinter
from tkinter import ttk, messagebox
import threading
import queue
import logging
from typing import Callable, Any, Optional

from src.ui.styles import Theme

logger = logging.getLogger(__name__)


class SplashWindow:
    """
    A self-contained splash screen that executes a background task.
    Prevents the main application window from appearing until data is ready.
    """

    def __init__(
        self,
        root: tkinter.Tk,
        task: Callable[[Callable[[str], None]], Any],
        on_complete: Callable[[Any, "SplashWindow"], None],
    ):
        """
        :param root: The root Tk instance (will be hidden).
        :param task: A function taking a progress callback and returning a result.
        :param on_complete: Callback triggered in the main thread when task finishes.
        """
        self.root = root
        self.task = task
        self.on_complete = on_complete
        self.queue: queue.Queue = queue.Queue()

        # UI State
        self.status_var = tkinter.StringVar(value="INITIALIZING...")
        self.splash: Optional[tkinter.Toplevel] = None

        self._build_splash_ui()
        self._center_window()

        # Hide main window and start execution
        self.root.withdraw()
        self._worker_thread = threading.Thread(target=self._run_task, daemon=True)
        self._worker_thread.start()

        # Start polling the queue in the main loop
        self._check_queue()

    def _build_splash_ui(self) -> None:
        """Constructs the frameless splash UI."""
        self.splash = tkinter.Toplevel(self.root)
        self.splash.title("Loading...")
        self.splash.attributes("-topmost", True)

        # Handle platform-specific transparency/decoration logic
        try:
            self.splash.overrideredirect(True)
        except Exception:
            self.splash.wm_overrideredirect(True)

        self.splash.configure(bg=Theme.BG_PRIMARY)
        container = ttk.Frame(self.splash, padding=30, style="Card.TFrame")
        container.pack(fill="both", expand=True)

        ttk.Label(
            container,
            text="MTGA DRAFT TOOL",
            font=(Theme.FONT_FAMILY, 14, "bold"),
            foreground=Theme.ACCENT,
            background=Theme.BG_SECONDARY,
        ).pack(pady=(0, 5))

        ttk.Label(
            container,
            textvariable=self.status_var,
            font=(Theme.FONT_FAMILY, 9),
            foreground=Theme.TEXT_MAIN,
            background=Theme.BG_SECONDARY,
        ).pack(pady=(0, 15))

        self.progress = ttk.Progressbar(container, mode="indeterminate", length=250)
        self.progress.pack(pady=(0, 10))
        self.progress.start(15)

    def _center_window(self) -> None:
        """Centers the splash screen relative to the monitor."""
        if not self.splash:
            return
        self.splash.update_idletasks()
        sw, sh = self.splash.winfo_screenwidth(), self.splash.winfo_screenheight()
        w, h = self.splash.winfo_width(), self.splash.winfo_height()
        self.splash.geometry(f"+{(sw-w)//2}+{(sh-h)//2}")

    def _run_task(self) -> None:
        """Runs the payload in a background thread and queues the result."""
        try:
            # We pass a lambda that puts messages into our thread-safe queue
            result = self.task(lambda msg: self.queue.put(("progress", msg)))
            self.queue.put(("success", result))
        except Exception as e:
            logger.exception("Splash background task failed.")
            self.queue.put(("error", str(e)))

    def _check_queue(self) -> None:
        """Periodic check for messages from the background thread."""
        if (
            not self.root.winfo_exists()
            or not self.splash
            or not self.splash.winfo_exists()
        ):
            return

        try:
            while True:
                msg_type, data = self.queue.get_nowait()
                if msg_type == "progress":
                    self.status_var.set(str(data).upper())
                elif msg_type == "success":
                    try:
                        self.on_complete(data, self)
                    except Exception as e:
                        self._handle_critical_error(f"Post-Load UI Error: {e}")
                    return
                elif msg_type == "error":
                    self._handle_critical_error(data)
                    return
        except queue.Empty:
            # Continue polling
            self.root.after(20, self._check_queue)

    def _handle_critical_error(self, message: str) -> None:
        """Stops animation and alerts user of startup failure."""
        logger.error(message)
        self.status_var.set("LOAD ERROR")
        self.progress.stop()
        messagebox.showerror("Startup Error", f"Failed to start:\n\n{message}")

    def close(self) -> None:
        """Explicitly closes the splash window."""
        if self.splash and self.splash.winfo_exists():
            self.splash.destroy()
            self.splash = None

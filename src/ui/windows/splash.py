"""
src/ui/windows/splash.py

This module implements a splash screen/loading window.
It runs tasks in a separate thread and updates the UI with progress.
"""

import tkinter
from tkinter import ttk
import threading
import queue
from typing import Callable, Any
from src.logger import create_logger
from src.ui.styles import Theme

logger = create_logger()


class SplashWindow:
    def __init__(
        self,
        root: tkinter.Tk,
        task: Callable[[Callable[[str], None]], Any],
        on_complete: Callable[[Any], None],
    ):
        self.root = root
        self.task = task
        self.on_complete = on_complete
        self.queue = queue.Queue()

        logger.info("Initializing Splash Window")

        # Configure Root for Splash
        self.root.title("MTGA Draft Tool - Loading")
        self.root.configure(bg=Theme.BG_PRIMARY)

        # UI Elements Container
        self.container = ttk.Frame(self.root, padding=20, style="Card.TFrame")
        self.container.pack(fill="both", expand=True)

        ttk.Label(self.container, text="MTGA Draft Tool", style="Header.TLabel").pack(
            pady=(0, 10)
        )

        self.status_var = tkinter.StringVar(value="Initializing...")
        ttk.Label(
            self.container, textvariable=self.status_var, style="Muted.TLabel"
        ).pack(pady=(0, 5))

        self.progress = ttk.Progressbar(
            self.container, mode="indeterminate", length=300
        )
        self.progress.pack(pady=(0, 10))
        self.progress.start(10)

        # Center Window
        self.root.update_idletasks()
        w = 350
        h = 150
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

        # Force visibility
        self.root.deiconify()
        self.root.lift()
        self.root.update()

        # Start Task with a slight delay to ensure window renders
        self.root.after(200, self._start_thread)

    def _start_thread(self):
        logger.info("Starting background loading thread")
        threading.Thread(target=self._run_task, daemon=True).start()
        self._check_queue()

    def _progress_callback(self, message):
        """Thread-safe callback to put messages in queue."""
        self.queue.put(("progress", message))

    def _run_task(self):
        try:
            logger.info("Running loading task...")
            result = self.task(self._progress_callback)
            logger.info("Loading task complete.")
            self.queue.put(("success", result))
        except Exception as e:
            logger.error(f"Error in loading task: {e}")
            self.queue.put(("error", e))

    def _check_queue(self):
        try:
            while True:  # Process all pending messages
                msg_type, data = self.queue.get_nowait()

                if msg_type == "progress":
                    self.status_var.set(data)
                    self.root.update_idletasks()

                elif msg_type == "success":
                    logger.info("Splash finished, cleaning up")
                    self._cleanup()
                    self.on_complete(data)
                    return

                elif msg_type == "error":
                    self.status_var.set(f"Error: {data}")
                    self.progress.stop()
                    # Keep window open to show error
                    return

        except queue.Empty:
            self.root.after(100, self._check_queue)

    def _cleanup(self):
        """Remove splash widgets and restore window frame."""
        self.progress.stop()
        self.container.destroy()
        self.root.withdraw()

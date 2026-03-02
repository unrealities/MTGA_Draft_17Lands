# -*- coding: utf-8 -*-
import threading


class UIProgress:
    """Handles UI updates and progress tracking with thread safety."""

    def __init__(self, progress=None, status=None, ui=None, initial_progress: int = 0):
        self.progress = progress
        self.initial_progress = initial_progress
        self.status = status
        self.ui = ui

    def _update_ui(self):
        """Update the UI if available."""
        if self.ui and self.ui.winfo_exists():
            self.ui.update()

    def _update_status(self, message: str):
        """Update status message safely across threads."""
        if self.status:
            if threading.current_thread() is threading.main_thread():
                self.status.set(message)
                self._update_ui()
            elif self.ui:

                def callback():
                    if hasattr(self.ui, "winfo_exists") and self.ui.winfo_exists():
                        self.status.set(message)

                try:
                    self.ui.after(0, callback)
                except RuntimeError:
                    pass  # Safely ignore during headless test execution

    def _update_progress(self, value: float, increment: bool = True):
        """Update progress bar value safely across threads."""
        if self.progress:

            def _apply():
                if (
                    not hasattr(self.progress, "winfo_exists")
                    or not self.progress.winfo_exists()
                ):
                    return
                if increment:
                    self.initial_progress += value
                    self.progress["value"] = self.initial_progress
                else:
                    self.progress["value"] = value
                self._update_ui()

            if threading.current_thread() is threading.main_thread():
                _apply()
            elif self.ui:
                try:
                    self.ui.after(0, _apply)
                except RuntimeError:
                    pass  # Safely ignore during headless test execution

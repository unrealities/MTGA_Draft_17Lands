# -*- coding: utf-8 -*-

class UIProgress:
    """Handles UI updates and progress tracking."""
    def __init__(self, progress=None, status=None, ui=None, initial_progress: int = 0):
        self.progress = progress
        self.initial_progress = initial_progress
        self.status = status
        self.ui = ui

    def _update_ui(self):
        """Update the UI if available."""
        if self.ui:
            self.ui.update()

    def _update_status(self, message: str):
        """Update status message and refresh UI."""
        if self.status:
            self.status.set(message)
            self._update_ui()

    def _update_progress(self, value: float, increment: bool = True):
        """Update progress bar value."""
        if self.progress:
            if increment:
                self.initial_progress += value
                self.progress["value"] = self.initial_progress
            else:
                self.progress["value"] = value
            self._update_ui()
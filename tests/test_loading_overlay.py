"""
tests/test_loading_overlay.py
The loading overlay must not force redraws while hidden.
"""

import tkinter
from unittest.mock import patch

import pytest

from src.ui.loading_overlay import LoadingOverlay
from src.ui.styles import Theme


@pytest.fixture
def root():
    root = tkinter.Tk()
    Theme.apply(root, "Dark")
    yield root
    root.destroy()


def test_update_status_skips_redraw_while_hidden(root):
    """Deck-builder progress arrives on every pick while the overlay is hidden;
    a forced update_idletasks per message stalled the UI for 0.3-0.5 s each."""
    overlay = LoadingOverlay(root)
    with patch.object(overlay, "update_idletasks") as redraw:
        overlay.update_status("Building...")
        redraw.assert_not_called()
    assert overlay.status_lbl.cget("text") == "Building..."


def test_update_status_redraws_while_shown(root):
    """Test roots are withdrawn under the shared fixtures, so the mapped state
    is stubbed rather than relying on the window manager."""
    overlay = LoadingOverlay(root)
    overlay.show("Loading Draft")
    with patch.object(overlay, "winfo_ismapped", return_value=True), patch.object(
        overlay, "update_idletasks"
    ) as redraw:
        overlay.update_status("Syncing...")
        redraw.assert_called_once()
    overlay.hide()

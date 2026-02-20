"""
tests/conftest.py
Global pytest configuration and fixtures.
"""

import pytest
import tkinter
from src.ui.styles import Theme

# Global singleton for Tkinter root
_shared_root = None


@pytest.fixture(scope="session", autouse=True)
def session_tk_root():
    """
    Creates a single, persistent Tkinter root for the entire test session.
    This prevents 'TclError: application has been destroyed' which occurs
    when ttk.Style tries to reuse a destroyed Tcl interpreter from a previous test.
    """
    global _shared_root
    _shared_root = tkinter.Tk()
    _shared_root.withdraw()

    # Initialize the theme engine once for the session
    Theme.apply(_shared_root, "Dark")

    yield _shared_root

    # Destroy only when the entire pytest session completes
    try:
        _shared_root.quit()
        _shared_root.update()
    except Exception:
        pass


@pytest.fixture(autouse=True)
def patch_tk_lifecycle(monkeypatch, session_tk_root):
    """
    Intercepts Tk() and destroy() calls from individual tests to force
    them to use the session_tk_root singleton.
    Also intercepts all Messagebox popups so tests run headless
    """
    # Force tkinter.Tk() to return our singleton
    monkeypatch.setattr(tkinter, "Tk", lambda *args, **kwargs: session_tk_root)

    # Disable destroy() on the singleton so tests can't accidentally kill it
    monkeypatch.setattr(session_tk_root, "destroy", lambda: None)

    # MOCK MESSAGEBOXES GLOBALLY: Prevent UI popups during automated tests
    import tkinter.messagebox as mb

    monkeypatch.setattr(mb, "askyesno", lambda *args, **kwargs: True)
    monkeypatch.setattr(mb, "showinfo", lambda *args, **kwargs: None)
    monkeypatch.setattr(mb, "showwarning", lambda *args, **kwargs: None)
    monkeypatch.setattr(mb, "showerror", lambda *args, **kwargs: None)

    # Clean up any leftover widgets from previous tests to ensure test isolation
    for widget in session_tk_root.winfo_children():
        try:
            widget.destroy()
        except tkinter.TclError:
            pass

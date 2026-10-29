"""
tests/conftest.py
Global pytest configuration and fixtures.
"""

import pytest
import tkinter
from src.ui.styles import Theme
from unittest.mock import patch
from ttkbootstrap.style import StyleBuilderTTK


# Global singleton for Tkinter root
_shared_root = None


@pytest.fixture(autouse=True)
def reset_theme():
    """Reset Theme class variables after each test to prevent cross-test pollution."""
    orig_bg = Theme.BG_PRIMARY
    orig_accent = Theme.ACCENT
    orig_text = Theme.TEXT_MAIN
    yield
    Theme.BG_PRIMARY = orig_bg
    Theme.ACCENT = orig_accent
    Theme.TEXT_MAIN = orig_text


@pytest.fixture(autouse=True)
def patch_ttkbootstrap_crash():
    """
    Prevents ttkbootstrap from crashing when it tries to re-style
    widgets that are currently being destroyed by the test runner.
    """
    original_update = StyleBuilderTTK.update_combobox_popdown_style

    def safe_update(self, widget):
        try:
            # Check if the widget is still a valid Tcl object
            if widget.winfo_exists():
                original_update(self, widget)
        except (tkinter.TclError, Exception):
            # Widget is destroyed or Tcl path is invalid; skip it
            pass

    # Use 'autospec=True' or ensure the signature matches (self, widget)
    with patch.object(
        StyleBuilderTTK, "update_combobox_popdown_style", autospec=True
    ) as mock_method:
        # We manually link the mock to our safe_update logic
        mock_method.side_effect = safe_update
        yield


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

    # Keep the host usable while the suite runs: no test window may appear
    # on screen, raise itself or take focus. Every Toplevel (subclasses
    # included — patched on the base class so pre-bound subclasses are
    # covered) starts withdrawn; deiconify maps it OFF-SCREEN (mapping is
    # required by tests that measure widget geometry), geometry positions are
    # clamped off-screen, and lift/focus_force/topmost are no-ops everywhere.
    OFFSCREEN = "+4000+4000"

    import re as _re

    def _offscreen_geom(value):
        if isinstance(value, str) and "+" in value:
            head = value.split("+")[0]
            return head + OFFSCREEN if head else OFFSCREEN
        return value

    _top_init = tkinter.Toplevel.__init__
    _top_deiconify = tkinter.Toplevel.deiconify
    _top_geometry = tkinter.Toplevel.geometry
    _top_attributes = tkinter.Toplevel.attributes

    def _quiet_init(self, *args, **kwargs):
        _top_init(self, *args, **kwargs)
        self.withdraw()

    def _quiet_deiconify(self):
        _top_deiconify(self)
        try:
            _top_geometry(self, OFFSCREEN)
        except Exception:
            pass

    def _quiet_geometry(self, value=None):
        if value is None:
            return _top_geometry(self)
        return _top_geometry(self, _offscreen_geom(value))

    def _quiet_attributes(self, *args, **kwargs):
        if args and args[0] == "-topmost":
            return None
        return _top_attributes(self, *args, **kwargs)

    monkeypatch.setattr(tkinter.Toplevel, "__init__", _quiet_init)
    monkeypatch.setattr(tkinter.Toplevel, "deiconify", _quiet_deiconify)
    monkeypatch.setattr(tkinter.Toplevel, "geometry", _quiet_geometry)
    monkeypatch.setattr(tkinter.Toplevel, "attributes", _quiet_attributes)
    monkeypatch.setattr(tkinter.Toplevel, "lift", lambda self, aboveThis=None: None)
    monkeypatch.setattr(
        tkinter.Toplevel, "focus_force", lambda self: None
    )

    # Same treatment for the session root (a Tk, not a Toplevel).
    monkeypatch.setattr(session_tk_root, "lift", lambda *a, **k: None)
    monkeypatch.setattr(session_tk_root, "focus_force", lambda *a, **k: None)
    _root_deiconify = session_tk_root.deiconify
    _root_geometry = session_tk_root.geometry

    def _root_quiet_deiconify():
        _root_deiconify()
        try:
            _root_geometry(OFFSCREEN)
        except Exception:
            pass

    def _root_quiet_geometry(value=None):
        if value is None:
            return _root_geometry()
        return _root_geometry(_offscreen_geom(value))

    monkeypatch.setattr(session_tk_root, "deiconify", _root_quiet_deiconify)
    monkeypatch.setattr(session_tk_root, "geometry", _root_quiet_geometry)
    _root_attributes = session_tk_root.attributes

    def _root_quiet_attributes(*args, **kwargs):
        if args and args[0] == "-topmost":
            return None
        return _root_attributes(*args, **kwargs)

    monkeypatch.setattr(session_tk_root, "attributes", _root_quiet_attributes)

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
            # Force completion of all background idle tasks before starting a new test
            session_tk_root.update_idletasks()
            session_tk_root.update()
            widget.destroy()
        except tkinter.TclError:
            pass


@pytest.fixture(autouse=True)
def clean_draft_state():
    """Ensures the active draft state file is wiped before and after every test
    so the log scanner doesn't accidentally resume a draft from a previous test!"""
    import os
    from src import constants

    state_file = os.path.join(constants.TEMP_FOLDER, "active_draft_state.json")

    if os.path.exists(state_file):
        try:
            os.remove(state_file)
        except Exception:
            pass

    yield

    if os.path.exists(state_file):
        try:
            os.remove(state_file)
        except Exception:
            pass


@pytest.fixture
def mock_style(self):
    """Patches ttk.Style so it doesn't attempt to contact a real Tcl interpreter."""
    with patch("src.ui.styles.ttk.Style") as mock:
        style_instance = mock.return_value
        colors_mock = MagicMock()
        style_instance.colors = colors_mock

        # Prevent the mock from leaking into the color variables
        style_instance.lookup.return_value = ""

        # Setup default behavior for colors
        colors_mock.bg = "#1e1e1e"  # Default Dark
        colors_mock.secondary = "gray"
        colors_mock.inputbg = "white"
        colors_mock.fg = "white"
        colors_mock.primary = "#4dabff"
        colors_mock.success = "green"
        colors_mock.danger = "red"
        colors_mock.warning = "orange"

        yield style_instance


@pytest.fixture(autouse=True)
def patch_dataset_skip_unresolved():
    """Ensure the Dataset class does not drop unresolved IDs during tests so we can verify pipeline tracking."""
    from src.dataset import Dataset

    original = Dataset.skip_unresolved_ids
    Dataset.skip_unresolved_ids = False
    yield
    Dataset.skip_unresolved_ids = original


@pytest.fixture(autouse=True)
def clear_deck_cache_between_tests():
    """GLOBAL_DECK_CACHE is module-level and keyed on (event_type, dataset_name,
    len(pool), name:count signatures) — card stats are not part of the key, so two
    tests with same-shaped pools would share cached variants across tests."""
    from src.advisor import deck_builder

    deck_builder.GLOBAL_DECK_CACHE.clear()
    yield
    deck_builder.GLOBAL_DECK_CACHE.clear()


@pytest.fixture
def production_resolution(monkeypatch):
    """Opt into production ID-resolution semantics. The autouse
    patch_dataset_skip_unresolved fixture flips Dataset.skip_unresolved_ids to False
    for every test; tests that exercise unresolved-ID dropping must pin the
    production default (True) with this fixture."""
    from src.dataset import Dataset

    monkeypatch.setattr(Dataset, "skip_unresolved_ids", True)


@pytest.fixture(autouse=True)
def isolate_dataset_index(tmp_path, monkeypatch):
    """Keep the persisted dataset index (Temp/dataset_index.json) out of tests:
    a mocked filename that matches a real file in Sets/ would otherwise be served
    from the real index instead of the test's mocked contents."""
    import src.utils as utils

    monkeypatch.setattr(utils, "_index_path", lambda: str(tmp_path / "dataset_index.json"))
    yield

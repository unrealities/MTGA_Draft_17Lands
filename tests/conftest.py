"""
tests/conftest.py
Global pytest configuration and fixtures.
"""

import faulthandler
import os
import sys
import threading
import pytest
import tkinter
from src.ui.styles import Theme
from unittest.mock import patch
from ttkbootstrap.style import StyleBuilderTTK


# Global singleton for Tkinter root
_shared_root = None

# A test (setup + call + teardown) running longer than this is treated as hung:
# the run names it, dumps every thread's stack and exits instead of stalling
# until someone notices. Override with PYTEST_HANG_TIMEOUT=<seconds>; 0 disables.
HANG_TIMEOUT = float(os.environ.get("PYTEST_HANG_TIMEOUT", "60"))


def _terminal_stderr_fd(config):
    """The real stderr: pytest's output capture swaps fd 2 for a temp file."""
    capman = config.pluginmanager.getplugin("capturemanager")
    try:
        return capman._global_capturing.err.targetfd_save
    except AttributeError:
        return sys.__stderr__.fileno()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item, nextitem):
    if HANG_TIMEOUT <= 0:
        yield
        return

    err_fd = _terminal_stderr_fd(item.config)

    def name_the_hang():
        msg = f"\n\nHANG: {item.nodeid} exceeded {HANG_TIMEOUT:g}s; dumping stacks\n"
        os.write(err_fd, msg.encode())

    # The Python timer names the test; faulthandler's C watchdog dumps and
    # exits even if the main thread is stuck inside Tcl holding the GIL.
    namer = threading.Timer(HANG_TIMEOUT, name_the_hang)
    namer.daemon = True
    namer.start()
    faulthandler.dump_traceback_later(HANG_TIMEOUT + 1, exit=True, file=err_fd)
    try:
        yield
    finally:
        faulthandler.cancel_dump_traceback_later()
        namer.cancel()


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

    # Disable destroy() on the singleton so tests can't accidentally kill it
    monkeypatch.setattr(session_tk_root, "destroy", lambda: None)

    # MOCK MESSAGEBOXES GLOBALLY: Prevent UI popups during automated tests
    import tkinter.messagebox as mb

    monkeypatch.setattr(mb, "askyesno", lambda *args, **kwargs: True)
    monkeypatch.setattr(mb, "showinfo", lambda *args, **kwargs: None)
    monkeypatch.setattr(mb, "showwarning", lambda *args, **kwargs: None)
    monkeypatch.setattr(mb, "showerror", lambda *args, **kwargs: None)

    # Clean up any leftover widgets from previous tests to ensure test isolation.
    # Hide and destroy everything *before* flushing events: on Windows, an
    # update() while a previous test's app or Toplevel is still on screen can
    # stall indefinitely repainting it (seen with the root left mapped after
    # leaving Mini Mode, and with leftover Sealed Studio windows).
    session_tk_root.withdraw()
    for widget in session_tk_root.winfo_children():
        try:
            widget.destroy()
        except tkinter.TclError:
            pass
    # Force completion of all background idle tasks before starting a new test
    try:
        session_tk_root.update_idletasks()
        session_tk_root.update()
    except tkinter.TclError:
        pass


@pytest.fixture(autouse=True)
def restore_tk_scaling(session_tk_root):
    """Tests may set `tk scaling` to emulate high-DPI displays; the shared root
    would otherwise carry that into every later test's font measurements."""
    scaling = session_tk_root.tk.call("tk", "scaling")
    yield
    session_tk_root.tk.call("tk", "scaling", scaling)


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
def isolate_dataset_index(tmp_path, monkeypatch):
    """Keep the persisted dataset index (Temp/dataset_index.json) out of tests:
    a mocked filename that matches a real file in Sets/ would otherwise be served
    from the real index instead of the test's mocked contents."""
    import src.utils as utils

    monkeypatch.setattr(utils, "_index_path", lambda: str(tmp_path / "dataset_index.json"))
    yield

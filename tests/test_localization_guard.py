"""
tests/test_localization_guard.py
Regression tests for the ttkbootstrap msgcat guard installed by main.py.

Background: on distributions shipping Tcl 9 (Fedora 42+, Nobara, Bazzite) the
frozen Linux build dies at startup with:

    _tkinter.TclError: invalid command name "::msgcat::mcmset"

main.py already wraps `initialize_localities` to swallow that error, but the
guard used to patch only `ttkbootstrap.localization.msgs.initialize_localities`.
`ttkbootstrap/localization/__init__.py` does `from .msgs import
initialize_localities`, binding its own reference at import time, and
`Style.__init__` calls `localization.initialize_localities()` -- so the guard
never covered the actual call site.
"""

import tkinter
import pytest

import main  # noqa: F401  (importing installs the guards)
from ttkbootstrap import localization
from ttkbootstrap.localization import msgs


class TestLocalizationGuard:
    def test_msgs_reference_is_patched(self):
        """The original guard: the name inside the msgs module."""
        assert msgs.initialize_localities.__name__ == "_safe_initialize_localities"

    def test_package_reference_is_patched(self):
        """
        The call site actually used by ttkbootstrap.style.Style.__init__.
        This is the assertion that fails without the fix.
        """
        assert (
            localization.initialize_localities.__name__
            == "_safe_initialize_localities"
        )

    def test_guard_swallows_msgcat_failure(self, monkeypatch):
        """
        Simulate a Tcl runtime whose msgcat lacks ::msgcat::mcmset and verify
        the call site no longer propagates the error.
        """

        def boom(*args, **kwargs):
            raise tkinter.TclError('invalid command name "::msgcat::mcmset"')

        monkeypatch.setattr(localization.MessageCatalog, "set_many", boom)

        # Must not raise.
        localization.initialize_localities()

    def test_unguarded_call_would_have_raised(self, monkeypatch):
        """
        Sanity check that the simulation above is faithful: the *original*
        implementation does propagate the TclError.
        """

        def boom(*args, **kwargs):
            raise tkinter.TclError('invalid command name "::msgcat::mcmset"')

        monkeypatch.setattr(localization.MessageCatalog, "set_many", boom)

        original = msgs.initialize_localities.__wrapped_original__
        with pytest.raises(tkinter.TclError):
            original()

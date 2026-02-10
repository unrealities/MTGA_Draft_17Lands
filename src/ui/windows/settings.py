"""
src/ui/windows/settings.py
Complete Preferences UI.
"""

import tkinter
from tkinter import ttk, messagebox
from typing import Callable, Dict, Any, List, Tuple

from src import constants
from src.configuration import (
    Configuration,
    reset_configuration,
    write_configuration,
    read_configuration,
)
from src.ui.styles import Theme
from src.ui.components import identify_safe_coordinates


class SettingsWindow(tkinter.Toplevel):
    def __init__(self, parent, configuration, on_update_callback):
        super().__init__(parent)
        self.configuration = configuration
        self.on_update_callback = on_update_callback

        self.title("Preferences")
        self.resizable(False, False)
        self.configure(bg=Theme.BG_PRIMARY)
        self.transient(parent)

        self.vars = {}
        self.trace_ids = []
        self.column_options = constants.COLUMNS_OPTIONS_EXTRA_DICT.copy()

        self._build_ui()
        self._load_settings()

        self.update_idletasks()
        x, y = identify_safe_coordinates(
            parent, self.winfo_width(), self.winfo_height(), 50, 50
        )
        self.geometry(f"+{x}+{y}")
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        container = ttk.Frame(self, padding=15)
        container.pack(fill="both", expand=True)

        # COLUMNS
        ttk.Label(container, text="DATA COLUMNS", style="Header.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 5)
        )
        for i in range(6):
            ttk.Label(container, text=f"Column {i+2}:").grid(
                row=i + 1, column=0, sticky="e", padx=5
            )
            var = tkinter.StringVar()
            self.vars[f"column_{i+2}"] = var
            ttk.OptionMenu(
                container,
                var,
                "Disabled",
                *self.column_options.keys(),
                style="TMenubutton",
            ).grid(row=i + 1, column=1, sticky="ew", pady=1)

        # APPEARANCE
        r = 8
        ttk.Label(container, text="APPEARANCE", style="Header.TLabel").grid(
            row=r, column=0, columnspan=2, sticky="w", pady=(10, 5)
        )

        ttk.Label(container, text="Value Format:").grid(
            row=r + 1, column=0, sticky="e", padx=5
        )
        self.vars["result_format"] = tkinter.StringVar()
        ttk.OptionMenu(
            container,
            self.vars["result_format"],
            "Percentage",
            *constants.RESULT_FORMAT_LIST,
            style="TMenubutton",
        ).grid(row=r + 1, column=1, sticky="ew")

        # FEATURES
        r = 11
        ttk.Label(container, text="FEATURES", style="Header.TLabel").grid(
            row=r, column=0, columnspan=2, sticky="w", pady=(10, 5)
        )

        features = [
            ("Display Draft Stats", "stats_enabled"),
            ("Display Signals", "signals_enabled"),
            ("Display Missing Cards", "missing_enabled"),
            ("Highlight Row Colors", "card_colors_enabled"),
            ("Use Color Identity (Abilities)", "color_identity_enabled"),
            ("Enable P1P1 OCR", "p1p1_ocr_enabled"),
            ("Auto-Switch Filter", "auto_highest_enabled"),
            ("Update Notifications", "update_notifications_enabled"),
        ]

        for i, (lbl, key) in enumerate(features):
            var = tkinter.IntVar()
            self.vars[key] = var
            ttk.Checkbutton(container, text=lbl, variable=var).grid(
                row=r + 1 + i, column=0, columnspan=2, sticky="w", padx=20
            )

        # FOOTER
        footer = ttk.Frame(container)
        footer.grid(row=30, column=0, columnspan=2, pady=(15, 0), sticky="ew")
        ttk.Button(footer, text="Restore Defaults", command=self._reset).pack(
            side="right"
        )

    def _load_settings(self):
        s = self.configuration.settings
        self._toggle_traces(False)

        def get_lbl(val):
            for k, v in self.column_options.items():
                if v == val:
                    return k
            return "Disabled"

        for i in range(2, 8):
            self.vars[f"column_{i}"].set(get_lbl(getattr(s, f"column_{i}")))
        self.vars["result_format"].set(s.result_format)

        for key in [
            "stats_enabled",
            "signals_enabled",
            "missing_enabled",
            "card_colors_enabled",
            "color_identity_enabled",
            "p1p1_ocr_enabled",
            "auto_highest_enabled",
            "update_notifications_enabled",
        ]:
            self.vars[key].set(int(getattr(s, key, True)))

        self._toggle_traces(True)

    def _toggle_traces(self, enable):
        if enable:
            for k, v in self.vars.items():
                tid = v.trace_add("write", lambda *a, key=k: self._on_change(key))
                self.trace_ids.append((v, tid))
        else:
            for v, tid in self.trace_ids:
                try:
                    v.trace_remove("write", tid)
                except:
                    pass
            self.trace_ids.clear()

    def _on_change(self, key):
        val = self.vars[key].get()
        if key.startswith("column_"):
            setattr(
                self.configuration.settings,
                key,
                self.column_options.get(val, "disabled"),
            )
        elif isinstance(val, int):
            setattr(self.configuration.settings, key, bool(val))
        else:
            setattr(self.configuration.settings, key, val)
        write_configuration(self.configuration)
        if self.on_update_callback:
            self.on_update_callback()

    def _reset(self):
        if messagebox.askyesno("Confirm", "Reset all settings?"):
            reset_configuration()
            self._load_settings()

    def _on_close(self):
        self._toggle_traces(False)
        self.destroy()

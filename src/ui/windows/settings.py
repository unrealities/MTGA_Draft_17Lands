"""
src/ui/windows/settings.py
Configuration UI for the MTGA Draft Tool.
"""

import tkinter
from tkinter import ttk, messagebox
from typing import Callable, Dict, List, Tuple

from src import constants
from src.configuration import Configuration, reset_configuration, write_configuration
from src.ui.styles import Theme
from src.ui.components import identify_safe_coordinates


class SettingsWindow(tkinter.Toplevel):
    def __init__(
        self, parent, configuration: Configuration, on_update_callback: Callable
    ):
        super().__init__(parent)
        self.configuration = configuration
        self.on_update_callback = on_update_callback

        self.title("Preferences")
        self.resizable(False, False)
        self.configure(bg=Theme.BG_PRIMARY)
        self.transient(parent)

        self.vars: Dict[str, tkinter.Variable] = {}
        self.trace_ids: List[Tuple[tkinter.Variable, str]] = []
        self.column_options = constants.COLUMNS_OPTIONS_EXTRA_DICT.copy()

        self._build_ui()
        self._load_settings()

        # Window positioning
        self.update_idletasks()
        x, y = identify_safe_coordinates(
            parent, self.winfo_width(), self.winfo_height(), 50, 50
        )
        self.geometry(f"+{x}+{y}")

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        container = ttk.Frame(self, padding=15)
        container.pack(fill="both", expand=True)

        # --- SECTION: DATA COLUMNS ---
        ttk.Label(container, text="DATA COLUMNS", style="Header.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 5)
        )

        # Columns 2 through 7 (Column 1 is always 'Card Name')
        dropdown_keys = list(self.column_options.keys())
        for i in range(6):
            col_idx = i + 2
            ttk.Label(container, text=f"Column {col_idx}:").grid(
                row=i + 1, column=0, sticky="e", padx=5
            )

            var = tkinter.StringVar()
            self.vars[f"column_{col_idx}"] = var

            om = ttk.OptionMenu(
                container, var, "Disabled", *dropdown_keys, style="TMenubutton"
            )
            om.grid(row=i + 1, column=1, sticky="ew", pady=1)

        # --- SECTION: APPEARANCE & FORMAT ---
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

        # --- SECTION: FEATURE TOGGLES ---
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

        for i, (label, key) in enumerate(features):
            var = tkinter.IntVar()
            self.vars[key] = var
            ttk.Checkbutton(container, text=label, variable=var).grid(
                row=r + 1 + i, column=0, columnspan=2, sticky="w", padx=20
            )

        # --- FOOTER ---
        footer = ttk.Frame(container)
        footer.grid(row=30, column=0, columnspan=2, pady=(15, 0), sticky="ew")
        ttk.Button(footer, text="Restore Defaults", command=self._reset_defaults).pack(
            side="right"
        )

    def _load_settings(self):
        """Populates UI from the configuration object."""
        s = self.configuration.settings
        self._toggle_traces(False)

        # Reverse lookup for column labels - 1% Dev Robustness
        def get_label(internal_val):
            for k, v in self.column_options.items():
                if v == internal_val:
                    return k
            # Fallback to the standard Disabled label defined in constants
            return constants.FIELD_LABEL_DISABLED

        for i in range(2, 8):
            key = f"column_{i}"
            self.vars[key].set(get_label(getattr(s, key)))

        self.vars["result_format"].set(s.result_format)

        checkbox_keys = [
            "stats_enabled",
            "signals_enabled",
            "missing_enabled",
            "card_colors_enabled",
            "color_identity_enabled",
            "p1p1_ocr_enabled",
            "auto_highest_enabled",
            "update_notifications_enabled",
        ]

        for key in checkbox_keys:
            # Ensure we handle potential missing keys from older config versions
            current_val = getattr(s, key, True)
            self.vars[key].set(int(current_val))

        self._toggle_traces(True)

    def _toggle_traces(self, enable: bool):
        if enable:
            for k, v in self.vars.items():
                tid = v.trace_add(
                    "write", lambda *a, key=k: self._on_setting_changed(key)
                )
                self.trace_ids.append((v, tid))
        else:
            for var, tid in self.trace_ids:
                try:
                    var.trace_remove("write", tid)
                except:
                    pass
            self.trace_ids.clear()

    def _on_setting_changed(self, key: str):
        """Persists changes and notifies the main application."""
        val = self.vars[key].get()

        if key.startswith("column_"):
            internal_val = self.column_options.get(val, constants.DATA_FIELD_DISABLED)
            setattr(self.configuration.settings, key, internal_val)
        elif isinstance(val, int):
            # Checkbox values
            setattr(self.configuration.settings, key, bool(val))
        else:
            setattr(self.configuration.settings, key, val)

        write_configuration(self.configuration)

        if self.on_update_callback:
            self.on_update_callback()

    def _reset_defaults(self):
        if messagebox.askyesno(
            "Confirm Reset", "Are you sure you want to restore all settings to default?"
        ):
            reset_configuration()
            from src.configuration import read_configuration

            new_conf, _ = read_configuration()
            self.configuration.settings = new_conf.settings
            self._load_settings()

    def _on_close(self):
        self._toggle_traces(False)
        self.destroy()

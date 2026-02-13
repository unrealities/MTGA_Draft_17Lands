"""
src/ui/windows/settings.py
Professional Configuration UI for the MTGA Draft Tool.
Streamlined for Tactical Intelligence and Layered Styling.
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
        self.transient(parent)  # Keeps window on top of main app

        self.vars: Dict[str, tkinter.Variable] = {}
        self.trace_ids: List[Tuple[tkinter.Variable, str]] = []

        self._build_ui()
        self._load_settings()

        # Center and Focus
        self.update_idletasks()
        x, y = identify_safe_coordinates(
            parent, self.winfo_width(), self.winfo_height(), 50, 50
        )
        self.geometry(f"+{x}+{y}")
        self.grab_set()  # Modal interaction

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        container = ttk.Frame(self, padding=20)
        container.pack(fill="both", expand=True)

        # --- SECTION: DATA FORMAT ---
        ttk.Label(
            container, text="DATA EVALUATION", font=(Theme.FONT_FAMILY, 9, "bold")
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        ttk.Label(container, text="Win Rate Format:", foreground=Theme.TEXT_MUTED).grid(
            row=1, column=0, sticky="e", padx=5
        )
        self.vars["result_format"] = tkinter.StringVar()
        fmt_om = ttk.OptionMenu(
            container,
            self.vars["result_format"],
            "",
            *constants.RESULT_FORMAT_LIST,
            style="TMenubutton",
        )
        fmt_om.grid(row=1, column=1, sticky="ew", pady=2)

        # --- SECTION: ADVISOR & HUD ---
        r = 10
        ttk.Label(
            container, text="INTELLIGENCE & HUD", font=(Theme.FONT_FAMILY, 9, "bold")
        ).grid(row=r, column=0, columnspan=2, sticky="w", pady=(20, 10))

        features = [
            (
                "Enable Tactical Advisor (The Brain)",
                "stats_enabled",
            ),  # 'stats_enabled' powers the Advisor View
            ("Display Lane Signals", "signals_enabled"),
            ("Display Missing (Wheel) Cards", "missing_enabled"),
            ("Highlight Row by Mana Cost", "card_colors_enabled"),
            ("Show Color Identity (Abilities)", "color_identity_enabled"),
            ("Enable P1P1 OCR", "p1p1_ocr_enabled"),
            (
                "Auto-Switch Dataset to Event",
                "auto_highest_enabled",
            ),  # 'auto_highest' powers auto-sync
            ("Check for Dataset Updates", "update_notifications_enabled"),
        ]

        for i, (label, key) in enumerate(features):
            var = tkinter.IntVar()
            self.vars[key] = var
            ttk.Checkbutton(container, text=label, variable=var).grid(
                row=r + 1 + i, column=0, columnspan=2, sticky="w", padx=10, pady=2
            )

        # --- FOOTER ---
        footer = ttk.Frame(container)
        footer.grid(row=50, column=0, columnspan=2, pady=(25, 0), sticky="ew")

        ttk.Button(footer, text="Restore Defaults", command=self._reset_defaults).pack(
            side="left"
        )
        ttk.Button(footer, text="Done", command=self._on_close).pack(side="right")

    def _load_settings(self):
        """Populates UI from the configuration object."""
        s = self.configuration.settings
        self._toggle_traces(False)

        # Standard settings
        self.vars["result_format"].set(s.result_format)

        # Checkbox logic
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
            val = getattr(s, key, True)
            self.vars[key].set(int(val))

        self._toggle_traces(True)

    def _toggle_traces(self, enable: bool):
        """Standard trace management to prevent save-loops during loading."""
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
        """Persists single change and notifies the main application."""
        val = self.vars[key].get()

        # Handle type conversion
        if isinstance(val, int) and key != "result_format":
            setattr(self.configuration.settings, key, bool(val))
        else:
            setattr(self.configuration.settings, key, val)

        write_configuration(self.configuration)

        # Immediate visual update if something like 'Row Colors' was toggled
        if self.on_update_callback:
            self.on_update_callback()

    def _reset_defaults(self):
        """Restores pro-level baseline configuration."""
        if messagebox.askyesno("Confirm Reset", "Restore all settings to default?"):
            reset_configuration()
            from src.configuration import read_configuration

            new_conf, _ = read_configuration()
            self.configuration.settings = new_conf.settings
            self._load_settings()
            if self.on_update_callback:
                self.on_update_callback()

    def _on_close(self):
        self._toggle_traces(False)
        self.destroy()

"""
src/ui/windows/settings.py

This module implements the Settings window for the MTGA Draft Tool.
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
    """
    The Settings Window allows users to configure data columns, toggle features,
    and adjust UI appearance. Changes are persisted to config.json immediately.
    """

    def __init__(
        self,
        parent: tkinter.Tk,
        configuration: Configuration,
        on_update_callback: Callable[[], None],
    ):
        super().__init__(parent)
        self.configuration = configuration
        self.on_update_callback = on_update_callback

        self.title("Application Settings")
        self.resizable(False, False)
        self.configure(bg=Theme.BG_PRIMARY)
        self.transient(parent)

        # Initialize storage for UI variables
        self.vars: Dict[str, tkinter.Variable] = {}
        self.trace_ids: List[Tuple[tkinter.Variable, str]] = []

        self.column_options = constants.COLUMNS_OPTIONS_EXTRA_DICT.copy()

        self._build_ui()
        self._load_current_settings()

        self.update_idletasks()
        self._position_window(parent)

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        main_frame = ttk.Frame(self, padding=20)
        main_frame.pack(fill="both", expand=True)

        # --- Section 1: Data Columns ---
        ttk.Label(main_frame, text="Data Columns", style="SubHeader.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 10)
        )

        column_configs = [
            ("Column 2:", "column_2"),
            ("Column 3:", "column_3"),
            ("Column 4:", "column_4"),
            ("Column 5:", "column_5"),
            ("Column 6:", "column_6"),
            ("Column 7:", "column_7"),
        ]

        current_row = 1
        dropdown_options = list(self.column_options.keys())

        for label_text, config_attr in column_configs:
            ttk.Label(main_frame, text=label_text).grid(
                row=current_row, column=0, sticky="e", padx=(0, 10), pady=2
            )
            var = tkinter.StringVar()
            self.vars[config_attr] = var
            om = ttk.OptionMenu(
                main_frame,
                var,
                dropdown_options[0],
                *dropdown_options,
                style="TMenubutton",
            )
            om.grid(row=current_row, column=1, sticky="ew", pady=2)
            current_row += 1

        # --- Section 2: General Options ---
        ttk.Label(
            main_frame, text="Display & Formatting", style="SubHeader.TLabel"
        ).grid(row=current_row, column=0, columnspan=2, sticky="w", pady=(15, 10))
        current_row += 1

        # Get list of available themes from styles.py
        theme_options = list(Theme.PALETTES.keys())

        general_configs = [
            ("Theme:", "theme", theme_options),
            ("Filter Format:", "filter_format", constants.DECK_FILTER_FORMAT_LIST),
            ("Win Rate Format:", "result_format", constants.RESULT_FORMAT_LIST),
            ("UI Scaling:", "ui_size", list(constants.UI_SIZE_DICT.keys())),
        ]

        for label_text, config_attr, options in general_configs:
            ttk.Label(main_frame, text=label_text).grid(
                row=current_row, column=0, sticky="e", padx=(0, 10), pady=2
            )
            var = tkinter.StringVar()
            self.vars[config_attr] = var
            om = ttk.OptionMenu(
                main_frame, var, options[0], *options, style="TMenubutton"
            )
            om.grid(row=current_row, column=1, sticky="ew", pady=2)
            current_row += 1

        # --- Section 3: Feature Toggles ---
        ttk.Label(main_frame, text="Features", style="SubHeader.TLabel").grid(
            row=current_row, column=0, columnspan=2, sticky="w", pady=(15, 10)
        )
        current_row += 1

        checkbox_configs = [
            ("Display Draft Stats", "stats_enabled"),
            ("Display Signal Scores", "signals_enabled"),
            ("Display Missing Cards", "missing_enabled"),
            ("Enable Auto-Highest Rated", "auto_highest_enabled"),
            ("Enable P1P1 OCR", "p1p1_ocr_enabled"),
            ("Enable Color Row Highlighting", "card_colors_enabled"),
            ("Use Color Identity (Abilities)", "color_identity_enabled"),
            ("Enable Update Notifications", "update_notifications_enabled"),
            ("Enable Missing Dataset Alerts", "missing_notifications_enabled"),
        ]

        for label_text, config_attr in checkbox_configs:
            var = tkinter.IntVar()
            self.vars[config_attr] = var
            cb = ttk.Checkbutton(
                main_frame, text=label_text, variable=var, onvalue=1, offvalue=0
            )
            cb.grid(
                row=current_row, column=0, columnspan=2, sticky="w", padx=20, pady=1
            )
            current_row += 1

        # --- Section 4: Footer ---
        footer_frame = ttk.Frame(main_frame)
        footer_frame.grid(
            row=current_row, column=0, columnspan=2, pady=(20, 0), sticky="ew"
        )

        btn_reset = ttk.Button(
            footer_frame, text="Restore Defaults", command=self._restore_defaults
        )
        btn_reset.pack(side="right")

    def _load_current_settings(self):
        settings = self.configuration.settings
        self._toggle_traces(enable=False)

        try:

            def get_label_for_value(val, default):
                for label, key in self.column_options.items():
                    if key == val:
                        return label
                return default

            self.vars["column_2"].set(
                get_label_for_value(settings.column_2, constants.COLUMN_2_DEFAULT)
            )
            self.vars["column_3"].set(
                get_label_for_value(settings.column_3, constants.COLUMN_3_DEFAULT)
            )
            self.vars["column_4"].set(
                get_label_for_value(settings.column_4, constants.COLUMN_4_DEFAULT)
            )
            self.vars["column_5"].set(
                get_label_for_value(settings.column_5, constants.COLUMN_5_DEFAULT)
            )
            self.vars["column_6"].set(
                get_label_for_value(settings.column_6, constants.COLUMN_6_DEFAULT)
            )
            self.vars["column_7"].set(
                get_label_for_value(settings.column_7, constants.COLUMN_7_DEFAULT)
            )

            self.vars["theme"].set(getattr(settings, "theme", "Dark"))
            self.vars["filter_format"].set(settings.filter_format)
            self.vars["result_format"].set(settings.result_format)
            self.vars["ui_size"].set(settings.ui_size)

            self.vars["stats_enabled"].set(int(settings.stats_enabled))
            self.vars["signals_enabled"].set(int(settings.signals_enabled))
            self.vars["missing_enabled"].set(int(settings.missing_enabled))
            self.vars["auto_highest_enabled"].set(int(settings.auto_highest_enabled))
            self.vars["p1p1_ocr_enabled"].set(int(settings.p1p1_ocr_enabled))
            self.vars["card_colors_enabled"].set(int(settings.card_colors_enabled))
            self.vars["color_identity_enabled"].set(
                int(settings.color_identity_enabled)
            )
            self.vars["update_notifications_enabled"].set(
                int(settings.update_notifications_enabled)
            )
            self.vars["missing_notifications_enabled"].set(
                int(settings.missing_notifications_enabled)
            )

        except Exception as e:
            print(f"Error loading settings: {e}")

        self._toggle_traces(enable=True)

    def _toggle_traces(self, enable: bool):
        if enable:
            if not self.trace_ids:
                for key, var in self.vars.items():
                    cb_name = var.trace_add(
                        "write", lambda *args, k=key: self._on_setting_change(k)
                    )
                    self.trace_ids.append((var, cb_name))
        else:
            for var, cb_name in self.trace_ids:
                try:
                    var.trace_remove("write", cb_name)
                except tkinter.TclError:
                    pass
            self.trace_ids.clear()

    def _on_setting_change(self, config_key: str):
        try:
            var = self.vars[config_key]
            val = var.get()

            if config_key.startswith("column_"):
                internal_val = self.column_options.get(val, constants.COLUMN_2_DEFAULT)
                setattr(self.configuration.settings, config_key, internal_val)
            elif isinstance(val, int):
                setattr(self.configuration.settings, config_key, bool(val))
            else:
                setattr(self.configuration.settings, config_key, val)

            write_configuration(self.configuration)

            # Special handling for Theme change
            if config_key == "theme":
                messagebox.showinfo(
                    "Restart Required",
                    "Theme changes will take effect after restarting the application.",
                )

            if self.on_update_callback:
                self.on_update_callback()

        except Exception as e:
            print(f"Error updating setting {config_key}: {e}")

    def _restore_defaults(self):
        if messagebox.askyesno(
            "Restore Defaults",
            "Are you sure you want to reset all settings to default?",
        ):
            reset_configuration()
            new_config, _ = read_configuration()
            self.configuration.settings = new_config.settings
            self._load_current_settings()
            self._on_setting_change("ui_size")
            if self.on_update_callback:
                self.on_update_callback()

    def _position_window(self, parent):
        w = self.winfo_width()
        h = self.winfo_height()
        x, y = identify_safe_coordinates(parent, w, h, 50, 50)
        self.wm_geometry(f"+{x}+{y}")

    def _on_close(self):
        self._toggle_traces(enable=False)
        self.destroy()

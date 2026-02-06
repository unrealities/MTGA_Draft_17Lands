"""
src/ui/windows/settings.py

This module implements the Settings window for the MTGA Draft Tool.
It handles configuration updates, UI scaling, and restoring defaults.
"""

import tkinter
from tkinter import ttk
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

        # Initialize storage for UI variables to prevent garbage collection
        self.vars: Dict[str, tkinter.Variable] = {}
        self.trace_ids: List[Tuple[tkinter.Variable, str]] = []

        # Data mapping for columns (Label -> Internal Key)
        # We perform a shallow copy to ensure we don't modify the constant
        self.column_options = constants.COLUMNS_OPTIONS_EXTRA_DICT.copy()

        # Build the UI
        self._build_ui()

        # Load current values
        self._load_current_settings()

        # Position window
        self.update_idletasks()
        self._position_window(parent)

        # Bind close event
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        """Constructs the settings interface."""
        main_frame = ttk.Frame(self, padding=20)
        main_frame.pack(fill="both", expand=True)

        # --- Section 1: Data Columns ---
        ttk.Label(main_frame, text="Data Columns", style="SubHeader.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 10)
        )

        # Configuration for column dropdowns
        # (UI Label, Config Attribute Name)
        column_configs = [
            ("Column 2:", "column_2"),
            ("Column 3:", "column_3"),
            ("Column 4:", "column_4"),
            ("Column 5:", "column_5"),
            ("Column 6:", "column_6"),
            ("Column 7:", "column_7"),
        ]

        # Generate Column Dropdowns
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

        # Configuration for general dropdowns
        # (UI Label, Config Attribute, Options List)
        general_configs = [
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

        # Configuration for Checkboxes
        # (Checkbox Text, Config Attribute)
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
        """Maps values from the Configuration object to UI variables."""
        settings = self.configuration.settings

        # Temporarily disable traces to prevent writing back to config while loading
        self._toggle_traces(enable=False)

        try:
            # 1. Map Columns (Value -> Label)
            # We need to find which Label corresponds to the stored Value
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

            # 2. Map General Options
            self.vars["filter_format"].set(settings.filter_format)
            self.vars["result_format"].set(settings.result_format)
            self.vars["ui_size"].set(settings.ui_size)

            # 3. Map Toggles (Boolean -> 1/0)
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

        # Re-enable traces to catch user updates
        self._toggle_traces(enable=True)

    def _toggle_traces(self, enable: bool):
        """Enables or disables the write trace on all variables."""
        if enable:
            if not self.trace_ids:
                for key, var in self.vars.items():
                    # We pass the key (config attribute name) to the callback
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
        """Callback when any UI variable changes."""
        try:
            var = self.vars[config_key]
            val = var.get()

            # Map Column Labels back to Internal Keys if necessary
            if config_key.startswith("column_"):
                # Val is the Label (e.g., "ALSA: ..."), we need the key (e.g., "alsa")
                internal_val = self.column_options.get(val, constants.COLUMN_2_DEFAULT)
                setattr(self.configuration.settings, config_key, internal_val)
            elif isinstance(val, int):
                # Handle booleans
                setattr(self.configuration.settings, config_key, bool(val))
            else:
                # Handle standard strings
                setattr(self.configuration.settings, config_key, val)

            # Persist changes
            write_configuration(self.configuration)

            # Notify main app to redraw/logic update
            if self.on_update_callback:
                self.on_update_callback()

        except Exception as e:
            print(f"Error updating setting {config_key}: {e}")

    def _restore_defaults(self):
        """Restores default settings, updates UI, and persists."""
        if tkinter.messagebox.askyesno(
            "Restore Defaults",
            "Are you sure you want to reset all settings to default?",
        ):
            reset_configuration()
            # We need to reload the configuration object in the parent or re-read it here
            # Since configuration is passed by reference, we might need to re-read values
            new_config, _ = read_configuration()

            # Update local reference (though attributes need to be copied if reference is shared strictly)
            # A safer way is to copy attributes over:
            self.configuration.settings = new_config.settings

            self._load_current_settings()
            self._on_setting_change("ui_size")  # Trigger update

            if self.on_update_callback:
                self.on_update_callback()

    def _position_window(self, parent):
        w = self.winfo_width()
        h = self.winfo_height()
        x, y = identify_safe_coordinates(parent, w, h, int(50), int(50))
        self.wm_geometry(f"+{x}+{y}")

    def _on_close(self):
        self._toggle_traces(enable=False)
        self.destroy()

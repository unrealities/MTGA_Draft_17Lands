"""
src/ui/top_bar.py
Contains the application's top control bar, including the status indicator,
Mini Mode toggle, and all dynamic dataset/format dropdowns.
"""

import tkinter
from tkinter import ttk
import os
import re
import logging
from datetime import datetime

from src import constants
from src.ui.styles import Theme
from src.ui.components import ColorFilterSelector
from src.utils import retrieve_local_set_list
from src.configuration import write_configuration

logger = logging.getLogger(__name__)


class TopBarControls(ttk.Frame):
    def __init__(self, parent, app_context):
        super().__init__(parent, padding=Theme.scaled_val(5))
        self.app = app_context
        self.history_files = {}

        self._build_ui()

    def _build_ui(self):
        # ROW 1: Status & Overlay
        row1 = ttk.Frame(self)
        row1.pack(fill="x", pady=(0, Theme.scaled_val(5)))

        self.status_dot = ttk.Label(
            row1, text="●", font=Theme.scaled_font(16), bootstyle="secondary"
        )
        self.status_dot.pack(side="left", padx=Theme.scaled_val(5))

        self.lbl_status = ttk.Label(
            row1,
            textvariable=self.app.vars["status_text"],
            font=Theme.scaled_font(11, "bold"),
            bootstyle="primary",
        )
        self.lbl_status.pack(side="left", padx=(0, Theme.scaled_val(10)))

        ttk.Button(
            row1,
            text="Mini Mode",
            bootstyle="info-outline",
            command=self.app._enable_overlay,
            width=-10,
        ).pack(side="right", padx=Theme.scaled_val(5))

        self.combo_history = ttk.Combobox(
            row1,
            textvariable=self.app.vars["set_label"],
            state="readonly",
            font=Theme.scaled_font(10, "bold"),
            width=36,
            justify="right",
        )
        self.combo_history.pack(side="right", padx=Theme.scaled_val(10))
        self.combo_history.bind("<<ComboboxSelected>>", self._on_history_select)
        self.combo_history.bind("<Button-1>", lambda e: self.update_history_dropdown())

        # ROW 2: Controls
        row2 = ttk.Frame(self)
        row2.pack(fill="x")

        self.btn_reload = ttk.Button(
            row2,
            text="Reload",
            command=self.app._force_reload,
            width=7,
            bootstyle="secondary-outline",
        )
        self.btn_reload.pack(side="left", padx=Theme.scaled_val(2))

        self.dataset_controls_frame = ttk.Frame(row2)
        self.dataset_controls_frame.pack(side="right")

        # Shared selector widget (the Card Pool tab uses the same class).
        self.filter_selector = ColorFilterSelector(
            self.dataset_controls_frame,
            self.app.orchestrator.scanner,
            self.app.configuration,
            variable=self.app.vars["deck_filter"],
            status_first=True,
        )
        self.filter_selector.pack(side="right")
        # Aliases: tests and other modules reach these widgets by name.
        self.om_filter = self.filter_selector.option_menu
        self.lbl_auto_detect = self.filter_selector.status_label

        self.om_group = ttk.OptionMenu(
            self.dataset_controls_frame,
            self.app.vars["selected_group"],
            "",
            style="TMenubutton",
        )
        self.om_group.pack(side="right", padx=Theme.scaled_val(2))

        self.om_event = ttk.OptionMenu(
            self.dataset_controls_frame,
            self.app.vars["selected_event"],
            "",
            style="TMenubutton",
        )
        self.om_event.pack(side="right", padx=Theme.scaled_val(2))

        # Wire up Traces
        self.app.vars["deck_filter"].trace_add(
            "write", lambda *a: self.on_filter_ui_change()
        )
        self.app.vars["selected_event"].trace_add(
            "write", lambda *a: self.on_event_change()
        )
        self.app.vars["selected_group"].trace_add(
            "write", lambda *a: self.on_group_change()
        )

    # --- UI STATE UPDATERS ---

    def update_status_dot(self, current_ts, prev_ts):
        """Updates the status dot color to indicate if the log is actively writing."""
        # Reconfiguring with the same value still dirties the widget, which on
        # macOS makes CoreAnimation recomposite the whole window on every tick;
        # only reconfigure when the state actually flips.
        bootstyle = "success" if current_ts != prev_ts else "secondary"
        if bootstyle != getattr(self, "_status_dot_bootstyle", None):
            self.status_dot.config(bootstyle=bootstyle)
            self._status_dot_bootstyle = bootstyle

    def update_auto_detect_label(self, colors):
        """Updates the label that tells the user what lane 'Auto' has detected."""
        if self.app.configuration.settings.deck_filter != constants.FILTER_OPTION_AUTO:
            self.lbl_auto_detect.config(text="")
            return

        active_color = colors[0] if colors else constants.FILTER_OPTION_ALL_DECKS
        if active_color == constants.FILTER_OPTION_ALL_DECKS:
            self.lbl_auto_detect.config(text="(Auto: Detecting...)")
        else:
            described = self.filter_selector.describe_color(active_color)
            self.lbl_auto_detect.config(text=f"(Auto: {described})")

    def set_history_dropdown_state(self, state):
        self.combo_history.configure(state=state)

    # --- DROPDOWN POPULATORS ---

    def update_history_dropdown(self):
        self.history_files = {}
        options = []

        live_path = self.app.configuration.settings.arena_log_location
        if live_path and os.path.exists(live_path):
            set_display = getattr(self.app, "detected_set_code", "Arena")
            if (
                hasattr(self.app.orchestrator.scanner, "set_list")
                and self.app.orchestrator.scanner.set_list.data
            ):
                for name, info in self.app.orchestrator.scanner.set_list.data.items():
                    if info.set_code == set_display:
                        set_display = name
                        break

            live_label = f"🔴 Live: {set_display}"
            self.history_files[live_label] = live_path
            options.append(live_label)

        if os.path.exists(constants.DRAFT_LOG_FOLDER):
            files = []
            for f in os.listdir(constants.DRAFT_LOG_FOLDER):
                if f.startswith("DraftLog_") and f.endswith(".log"):
                    filepath = os.path.join(constants.DRAFT_LOG_FOLDER, f)
                    try:
                        mtime = os.path.getmtime(filepath)
                        files.append((f, filepath, mtime))
                    except Exception:
                        pass
            files.sort(key=lambda x: x[2], reverse=True)

            for f, filepath, mtime in files:
                parts = f.replace(".log", "").split("_")
                if len(parts) >= 4:
                    card_set = parts[1]
                    event = parts[2]
                else:
                    card_set = "UNKNOWN"
                    event = "Draft"

                dt_str = datetime.fromtimestamp(mtime).strftime("%m-%d %H:%M")
                display_str = f"📂 {card_set} {event} ({dt_str})"
                self.history_files[display_str] = filepath
                options.append(display_str)

        self.combo_history["values"] = options
        current_selection = self.app.vars["set_label"].get()
        if "Missing Dataset" in current_selection:
            return

        current_log = os.path.basename(self.app.orchestrator.scanner.arena_file)
        target_option = options[0] if options else ""

        for opt, path in self.history_files.items():
            if os.path.basename(path) == current_log:
                target_option = opt
                break

        self.app.vars["set_label"].set(target_option)

    def _set_dropdown_options(self, menu_widget, variable, options):
        menu = menu_widget["menu"]
        menu.delete(0, "end")
        for opt in options:
            menu.add_command(label=opt, command=tkinter._setit(variable, opt))

    def update_deck_filter_options(self):
        if self.app._loading and self.app.vars["deck_filter"].get() != "":
            return

        old_loading = self.app._loading
        self.app._loading = True
        try:
            self.filter_selector.sync(
                selected_key=self.app.configuration.settings.deck_filter
            )
            self.app.deck_filter_map = self.filter_selector.filter_map
            # sync() falls back to Auto when the dataset lacks the saved key.
            self.app.configuration.settings.deck_filter = (
                self.filter_selector.selected_key
            )
        finally:
            self.app._loading = old_loading

    def update_data_sources(self):
        try:
            current_set, current_event_type = (
                self.app.orchestrator.scanner.retrieve_current_limited_event()
            )
            event_transitioned = False
            current_draft_id = self.app.orchestrator.scanner.current_draft_id

            if (
                current_draft_id
                and not self.app.current_draft_id
                and current_set == self.app.active_event_set
                and current_event_type == self.app.active_event_type
            ):
                self.app.current_draft_id = current_draft_id

            if (
                current_set != self.app.active_event_set
                or current_event_type != self.app.active_event_type
                or self.app.orchestrator.new_event_detected
                or (current_draft_id and current_draft_id != self.app.current_draft_id)
            ):
                event_transitioned = True
                self.app.active_event_set = current_set
                self.app.active_event_type = current_event_type
                self.app.current_draft_id = current_draft_id
                self.app.orchestrator.new_event_detected = False

            if not current_set:
                self.dataset_controls_frame.pack_forget()
                self.om_event["menu"].delete(0, "end")
                self.om_group["menu"].delete(0, "end")
                return
            else:
                self.dataset_controls_frame.pack(side="right")

            full_set_name = current_set
            if (
                self.app.orchestrator.scanner.set_list
                and self.app.orchestrator.scanner.set_list.data
            ):
                for name, info in self.app.orchestrator.scanner.set_list.data.items():
                    if info.set_code == current_set:
                        full_set_name = name
                        break

            self.app.detected_set_code = current_set
            all_files, _ = retrieve_local_set_list()
            self.app.current_set_data_map = {}

            def normalize_code(code_string):
                return re.sub(r"[^A-Z0-9]", "", str(code_string).upper())

            normalized_current = normalize_code(current_set)

            for f in all_files:
                file_set, f_event, f_group, _, _, _, f_path, _ = f
                if normalize_code(file_set) != normalized_current:
                    continue
                if f_event not in self.app.current_set_data_map:
                    self.app.current_set_data_map[f_event] = {}
                self.app.current_set_data_map[f_event][f_group] = f_path

            available_events = sorted(list(self.app.current_set_data_map.keys()))

            if not available_events:
                self.dataset_controls_frame.pack(side="right")
                self.app.vars["set_label"].set(f"{full_set_name} (Missing Dataset)")
                self.om_event["menu"].delete(0, "end")
                self.om_group["menu"].delete(0, "end")
                return

            self.app.vars["set_label"].set(full_set_name)
            self.update_history_dropdown()

            self._set_dropdown_options(
                self.om_event, self.app.vars["selected_event"], available_events
            )

            current_selection = self.app.vars["selected_event"].get()

            if event_transitioned:
                if current_event_type in available_events:
                    target_event = current_event_type
                elif constants.LIMITED_TYPE_STRING_DRAFT_PREMIER in available_events:
                    target_event = constants.LIMITED_TYPE_STRING_DRAFT_PREMIER
                else:
                    target_event = available_events[0]
            else:
                target_event = (
                    current_selection
                    if current_selection in available_events
                    else available_events[0]
                )

            if self.app.vars["selected_event"].get() != target_event:
                self.app.vars["selected_event"].set(target_event)
            else:
                self.on_event_change()

        except Exception as e:
            logger.error(f"Error in update_data_sources: {e}")

    # --- EVENT HANDLERS ---

    def on_filter_ui_change(self):
        if not self.app._initialized or self.app._loading:
            return
        label = self.app.vars["deck_filter"].get()
        self.app.configuration.settings.deck_filter = self.app.deck_filter_map.get(
            label, label
        )
        write_configuration(self.app.configuration)
        self.app._refresh_ui_data()

    def _on_history_select(self, event):
        selection = self.app.vars["set_label"].get()
        if selection in self.history_files:
            filepath = self.history_files[selection]
            self.combo_history.configure(state="disabled")
            self.app.vars["status_text"].set("Queuing Draft...")

            if hasattr(self.app, "loading_overlay"):
                title_name = selection.replace("📂 ", "").replace("🔴 ", "")
                self.app.loading_overlay.show(f"Loading: {title_name}")
                self.app.loading_overlay.update_status("Queuing Draft...")

            self.app.root.update_idletasks()
            self.app.orchestrator.set_file_and_scan(filepath)

            if self.app.tabs_visible and "🔴 Live" not in selection:
                self.app.notebook.select(self.app.panel_suggest)

    def on_event_change(self):
        if not self.app._initialized:
            return
        evt = self.app.vars["selected_event"].get()
        if not evt or evt not in self.app.current_set_data_map:
            return

        available_groups = sorted(list(self.app.current_set_data_map[evt].keys()))
        self._set_dropdown_options(
            self.om_group, self.app.vars["selected_group"], available_groups
        )

        target_group = self.app.vars["selected_group"].get()
        if target_group not in available_groups:
            target_group = (
                "All"
                if "All" in available_groups
                else (available_groups[0] if available_groups else "")
            )

        if target_group and self.app.vars["selected_group"].get() != target_group:
            self.app.vars["selected_group"].set(target_group)
        else:
            self.on_group_change()

    def on_group_change(self):
        if not self.app._initialized:
            return
        evt = self.app.vars["selected_event"].get()
        grp = self.app.vars["selected_group"].get()

        if (
            evt in self.app.current_set_data_map
            and grp in self.app.current_set_data_map[evt]
        ):
            path = self.app.current_set_data_map[evt][grp]
            current_loaded = self.app.configuration.card_data.latest_dataset

            if os.path.basename(path) != current_loaded:
                if hasattr(self.app, "loading_overlay"):
                    self.app.loading_overlay.show(f"Evaluating {evt} ({grp})")
                    self.app.loading_overlay.update_status("Processing dataset...")
                self.app.root.update_idletasks()

                self.app.vars["status_text"].set("Loading Dataset...")
                try:
                    self.app.orchestrator.scanner.retrieve_set_data(path)
                    self.app.configuration.card_data.latest_dataset = os.path.basename(
                        path
                    )
                    write_configuration(self.app.configuration)
                    from src.card_logic import clear_deck_cache

                    clear_deck_cache()
                except Exception as e:
                    logger.error(f"Dataset load error: {e}")

                self.app.vars["status_text"].set("Ready")
                self.update_data_sources()
                self.update_deck_filter_options()
                self.app.orchestrator.request_math_update()
                self.app._refresh_ui_data()

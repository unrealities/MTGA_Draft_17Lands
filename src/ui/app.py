"""
src/ui/app.py
Main UI Orchestrator. Coordinates Logic (Orchestrator) and UI (App).
"""

import tkinter
from tkinter import ttk, filedialog, messagebox
import os
from typing import Dict, List, Any, Optional

from src import constants
from src.configuration import write_configuration
from src.card_logic import filter_options, get_deck_metrics
from src.utils import retrieve_local_set_list
from src.ui.styles import Theme
from src.ui.components import CardToolTip
from src.ui.dashboard import DashboardFrame
from src.ui.orchestrator import DraftOrchestrator
from src.notifications import Notifications
from src.ui.windows.overlay import CompactOverlay
from src.ui.advisor_view import AdvisorPanel

# Windows
from src.ui.windows.taken_cards import TakenCardsPanel
from src.ui.windows.suggest_deck import SuggestDeckPanel
from src.ui.windows.compare import ComparePanel
from src.ui.windows.download import DownloadWindow
from src.ui.windows.tier_list import TierListWindow
from src.ui.windows.settings import SettingsWindow


class DraftApp:
    def __init__(self, root: tkinter.Tk, scanner, configuration, splash=None):
        self.root = root
        self.configuration = configuration

        # 1. State Initialization
        self.vars: Dict[str, tkinter.Variable] = {}
        self.deck_filter_map: Dict[str, str] = {}
        self.overlay_window: Optional[CompactOverlay] = None
        self._initialized = False
        self._rebuilding_ui = False
        self._loading = False
        self._update_task_id: Optional[str] = None
        self.previous_timestamp = 0
        self.current_pack_data = []
        self.current_missing_data = []

        # New State for Set Selection
        self.current_set_data_map: Dict[str, Dict[str, str]] = {}
        self.detected_set_code = ""

        # 2. Logic Initialization
        self.orchestrator = DraftOrchestrator(
            scanner, configuration, self._refresh_ui_data
        )

        # 3. View Construction
        self.root.withdraw()
        self._setup_variables()
        self._build_layout()
        self._setup_menu()

        # 4. Attach Infrastructure
        self.notifications = Notifications(
            self.root, scanner.set_list, configuration, self.panel_data
        )
        self.root.bind(
            "<<ShowDataTab>>", lambda e: self.notebook.select(self.panel_data)
        )

        # 5. Boot Synchronization
        self._initialized = True
        self.orchestrator.scanner.log_enable(self.configuration.settings.draft_log_enabled)
        self._update_data_sources()
        self._update_deck_filter_options()

        # Apply Configuration Styling
        current_scale = constants.UI_SIZE_DICT.get(
            self.configuration.settings.ui_size, 1.0
        )
        Theme.apply(
            self.root,
            palette=self.configuration.settings.theme,
            engine=getattr(self.configuration.settings, "theme_base", "clam"),
            custom_path=getattr(self.configuration.settings, "theme_custom_path", ""),
            scale=current_scale,
        )

        self._refresh_ui_data()

        # Logic: Default to Datasets tab if no valid data source is loaded
        # This guides users to download data immediately upon first launch
        if not self.configuration.card_data.latest_dataset:
            self.notebook.select(self.panel_data)

        # Trigger update checks immediately
        self.root.after(1000, self.notifications.check_for_updates)

        # 6. Reveal
        if splash:
            splash.close()
        self.root.title(f"MTGA Draft Tool v{constants.APPLICATION_VERSION}")
        self.root.deiconify()
        self._schedule_update()

    def _setup_variables(self):
        self.vars["deck_filter"] = tkinter.StringVar(
            value=self.configuration.settings.deck_filter
        )
        self.vars["set_label"] = tkinter.StringVar(value="NO SET")
        self.vars["selected_event"] = tkinter.StringVar(value="")
        self.vars["selected_group"] = tkinter.StringVar(value="")
        self.vars["status_text"] = tkinter.StringVar(value="Ready")
        self.vars["event_info"] = tkinter.StringVar(value="Scan logs...")
        self.vars["deck_filter"].trace_add(
            "write", lambda *a: self._on_filter_ui_change()
        )
        self.vars["selected_event"].trace_add(
            "write", lambda *a: self._on_event_change()
        )
        self.vars["selected_group"].trace_add(
            "write", lambda *a: self._on_group_change()
        )

    def _build_layout(self):
        if hasattr(self, "main_container"):
            self.main_container.destroy()
        self.main_container = ttk.Frame(self.root, padding=8)
        self.main_container.pack(fill="both", expand=True)

        # --- HEADER CONTAINER (Two Rows) ---
        header_frame = ttk.Frame(self.main_container, style="Card.TFrame", padding=5)
        header_frame.pack(fill="x", pady=(0, 10))

        # ROW 1: Status & Overlay
        row1 = ttk.Frame(header_frame, style="Card.TFrame")
        row1.pack(fill="x", pady=(0, 5))

        self.status_dot = ttk.Label(row1, text="●", foreground=Theme.TEXT_MUTED)
        self.status_dot.pack(side="left", padx=5)

        ttk.Label(
            row1,
            textvariable=self.vars["event_info"],
            font=(Theme.FONT_FAMILY, 9, "bold"),
        ).pack(side="left")

        ttk.Label(row1, text=" | ", foreground=Theme.TEXT_MUTED).pack(side="left")
        ttk.Label(row1, textvariable=self.vars["status_text"]).pack(side="left")

        ttk.Button(
            row1,
            text="Overlay Mode",
            bootstyle="info-outline",
            command=self._enable_overlay,
            width=12,
        ).pack(side="right", padx=5)

        # ROW 2: Controls
        row2 = ttk.Frame(header_frame, style="Card.TFrame")
        row2.pack(fill="x")

        # Controls (Left)
        # Split Refresh into "Logs" (Fast, IO only) and "P1P1" (Slow, OCR)
        ttk.Button(
            row2, text="Logs", command=lambda: self._manual_refresh(False), width=6
        ).pack(side="left", padx=2)
        ttk.Button(
            row2, text="P1P1", command=lambda: self._manual_refresh(True), width=6
        ).pack(side="left", padx=2)

        # Filter (Right)
        self.om_filter = ttk.OptionMenu(
            row2, self.vars["deck_filter"], "", style="TMenubutton"
        )
        self.om_filter.pack(side="right", padx=2)

        # Group (Right)
        self.om_group = ttk.OptionMenu(
            row2, self.vars["selected_group"], "", style="TMenubutton"
        )
        self.om_group.pack(side="right", padx=2)

        # Event (Right)
        self.om_event = ttk.OptionMenu(
            row2, self.vars["selected_event"], "", style="TMenubutton"
        )
        self.om_event.pack(side="right", padx=2)

        # Set Label (Right)
        self.lbl_set_code = ttk.Label(
            row2,
            textvariable=self.vars["set_label"],
            font=(Theme.FONT_FAMILY, 9, "bold"),
            foreground=Theme.ACCENT,
            padding=(5, 2),
        )
        self.lbl_set_code.pack(side="right", padx=5)

        # --- BODY ---
        self.advisor_panel = AdvisorPanel(self.main_container)
        self.advisor_panel.pack(fill="x", pady=(0, 10))

        self.splitter = ttk.PanedWindow(self.main_container, orient=tkinter.VERTICAL)
        self.splitter.pack(fill="both", expand=True)

        self.dashboard = DashboardFrame(
            self.splitter,
            self.configuration,
            self._on_card_select,
            self._refresh_ui_data,
        )
        self.splitter.add(self.dashboard, weight=4)

        self.notebook = ttk.Notebook(self.splitter)
        self.splitter.add(self.notebook, weight=3)

        self.panel_taken = TakenCardsPanel(
            self.notebook, self.orchestrator.scanner, self.configuration
        )
        self.panel_suggest = SuggestDeckPanel(
            self.notebook, self.orchestrator.scanner, self.configuration
        )
        self.panel_compare = ComparePanel(
            self.notebook, self.orchestrator.scanner, self.configuration
        )
        self.panel_data = DownloadWindow(
            self.notebook,
            self.orchestrator.scanner.set_list,
            self.configuration,
            self._on_dataset_update,
        )
        self.panel_tiers = TierListWindow(
            self.notebook, self.configuration, self._refresh_ui_data
        )

        self.notebook.add(self.panel_data, text=" Datasets ")
        self.notebook.add(self.panel_taken, text=" Card Pool ")
        self.notebook.add(self.panel_suggest, text=" Deck Builder ")
        self.notebook.add(self.panel_compare, text=" Comparisons ")
        self.notebook.add(self.panel_tiers, text=" Tier Lists ")

    def _setup_menu(self):
        m = tkinter.Menu(self.root)
        self.root.config(menu=m)

        # File Menu
        file_m = tkinter.Menu(m, tearoff=0)
        m.add_cascade(label="File", menu=file_m)
        file_m.add_command(label="Preferences...", command=self._open_settings)
        file_m.add_separator()
        file_m.add_command(label="Read Draft Log...", command=self._read_draft_log)
        file_m.add_command(label="Read Player.log...", command=self._read_player_log)
        file_m.add_separator()
        file_m.add_command(label="Export Draft (CSV)", command=self._export_csv)
        file_m.add_command(label="Export Draft (JSON)", command=self._export_json)
        file_m.add_separator()
        file_m.add_command(label="Exit", command=self.root.destroy)

        # Theme Menu
        theme_m = tkinter.Menu(m, tearoff=0)
        m.add_cascade(label="Theme", menu=theme_m)

        # 1. System / Native Option
        theme_m.add_command(
            label="System (Native)",
            command=lambda: self._update_theme(new_palette="System"),
        )
        theme_m.add_separator()

        # 2. Mana Flairs (Bootstrap Themes)
        for name in Theme.THEME_MAPPING.keys():
            if name == "System":
                continue
            theme_m.add_command(
                label=f"Mana Flair: {name}",
                command=lambda n=name: self._update_theme(new_palette=n),
            )

        # 3. Custom TCL
        custom_m = tkinter.Menu(theme_m, tearoff=0)
        theme_m.add_cascade(label="Custom Themes (.tcl)", menu=custom_m)
        custom_m.add_command(
            label="Browse for .tcl...", command=self._browse_custom_tcl
        )

        # Discover existing custom themes
        for name, path in Theme.discover_custom_themes().items():
            custom_m.add_command(
                label=name, command=lambda p=path: self._update_theme(new_custom=p)
            )

    def _update_theme(self, new_engine=None, new_palette=None, new_custom=None):
        s = self.configuration.settings
        if new_engine:
            s.theme_base = new_engine
        if new_palette:
            s.theme = new_palette
        if new_custom:
            s.theme_custom_path = new_custom
        else:
            s.theme_custom_path = ""

        write_configuration(self.configuration)
        current_scale = constants.UI_SIZE_DICT.get(s.ui_size, 1.0)
        Theme.apply(
            self.root,
            palette=s.theme,
            engine=getattr(s, "theme_base", "clam"),
            custom_path=s.theme_custom_path,
            scale=current_scale,
        )
        self._refresh_ui_data()

    def _browse_custom_tcl(self):
        f = filedialog.askopenfilename(
            filetypes=(("Tcl files", "*.tcl"), ("All", "*.*"))
        )
        if f:
            self._update_theme(new_custom=f)

    def _refresh_ui_data(self):
        """
        Atomic UI update cycle.
        Synchronizes The Brain, The Dashboard (Signals/Curve), and Sub-panels.
        """
        if not self._initialized or self._rebuilding_ui:
            return

        # 1. State Retrieval
        es, et = self.orchestrator.scanner.retrieve_current_limited_event()
        pk, pi = self.orchestrator.scanner.retrieve_current_pack_and_pick()

        metrics = self.orchestrator.scanner.retrieve_set_metrics()
        tier_data = self.orchestrator.scanner.retrieve_tier_data()
        taken_cards = self.orchestrator.scanner.retrieve_taken_cards()
        pack_cards = self.orchestrator.scanner.retrieve_current_pack_cards()
        missing_cards = self.orchestrator.scanner.retrieve_current_missing_cards()

        # 2. Intelligence Layer (The Brain)
        from src.advisor.engine import DraftAdvisor

        advisor = DraftAdvisor(metrics, taken_cards)
        recommendations = advisor.evaluate_pack(pack_cards, pi)

        # 3. View Updates
        # Header
        self.vars["event_info"].set(f"{es} {et}" if es else "Scan logs...")
        self.vars["status_text"].set(f"Pack {pk} Pick {pi}")

        # Advisor Summary
        if hasattr(self, "advisor_panel"):
            self.advisor_panel.update_recommendations(recommendations)

        # Dashboard Logic
        colors = filter_options(
            taken_cards,
            self.configuration.settings.deck_filter,
            metrics,
            self.configuration,
        )

        # Update Main Dashboard
        self.dashboard.update_pack_data(
            pack_cards,
            colors,
            metrics,
            tier_data,
            pi,
            source_type="pack",
            recommendations=recommendations,
        )
        self.dashboard.update_pack_data(
            missing_cards, colors, metrics, tier_data, pi, source_type="missing"
        )

        # Update Overlay if active
        if self.overlay_window:
            self.overlay_window.update_data(pack_cards, colors, metrics, tier_data, pi)

        self.dashboard.update_signals(self._calculate_signals(metrics))
        self.dashboard.update_stats(get_deck_metrics(taken_cards).distribution_all)

        # Tab Refresh
        for p in [self.panel_taken, self.panel_suggest, self.panel_compare]:
            p.refresh()

        self.dashboard.update_deck_balance(taken_cards)

    def _calculate_signals(self, metrics):
        """Helper to compute current lane signals."""
        from src.signals import SignalCalculator

        calc = SignalCalculator(metrics)
        history = self.orchestrator.scanner.retrieve_draft_history()
        scores = {c: 0.0 for c in constants.CARD_COLORS}
        for entry in history:
            if entry["Pack"] == 2:
                continue  # Focus on lane rewards
            pack_cards = self.orchestrator.scanner.set_data.get_data_by_id(
                entry["Cards"]
            )
            for c, v in calc.calculate_pack_signals(pack_cards, entry["Pick"]).items():
                scores[c] += v
        return scores

    def _update_signals_logic(self, metrics):
        from src.signals import SignalCalculator

        calc = SignalCalculator(metrics)
        history = self.orchestrator.scanner.retrieve_draft_history()
        scores = {c: 0.0 for c in constants.CARD_COLORS}
        for entry in history:
            if entry["Pack"] == 2:
                continue
            pack_cards = self.orchestrator.scanner.set_data.get_data_by_id(
                entry["Cards"]
            )
            for c, v in calc.calculate_pack_signals(pack_cards, entry["Pick"]).items():
                scores[c] += v
        self.dashboard.update_signals(scores)

    def _update_loop(self):
        if not self.root.winfo_exists():
            return
        if self.orchestrator.update_cycle():
            self._update_data_sources()
            self._update_deck_filter_options()
        try:
            ts = os.stat(self.orchestrator.scanner.arena_file).st_mtime
            self.status_dot.config(
                foreground=(
                    Theme.SUCCESS if ts != self.previous_timestamp else Theme.TEXT_MUTED
                )
            )
            self.previous_timestamp = ts
        except:
            pass
        self._schedule_update()

    def _schedule_update(self):
        self._update_task_id = self.root.after(1000, self._update_loop)

    def _on_filter_ui_change(self):
        if not self._initialized:
            return
        label = self.vars["deck_filter"].get()
        self.configuration.settings.deck_filter = self.deck_filter_map.get(label, label)
        write_configuration(self.configuration)
        self._refresh_ui_data()

    def _update_data_sources(self):
        """
        INTELLIGENT DATA SOURCE MANAGER
        Detects current set from logs, filters available datasets, and auto-selects defaults.
        """
        # 1. Detect active draft
        current_set, current_event_type = (
            self.orchestrator.scanner.retrieve_current_limited_event()
        )

        # Determine strictness: If we have a draft, we MUST show that set.
        # If logs are empty, show "NO SET" or handle error.

        if not current_set:
            self.vars["set_label"].set("NO SET")
            self.lbl_set_code.config(foreground=Theme.ERROR)
            self._set_dropdown_options(self.om_event, self.vars["selected_event"], [])
            self._set_dropdown_options(self.om_group, self.vars["selected_group"], [])
            return

        self.detected_set_code = current_set
        self.vars["set_label"].set(f"SET: {current_set}")
        self.lbl_set_code.config(foreground=Theme.ACCENT)

        # 2. Parse all local datasets
        # Format: (Set, Event, Group, ..., Path, ...)
        all_files, _ = retrieve_local_set_list()

        # Build Map: event_type -> user_group -> path
        # Filter ONLY for the detected set
        self.current_set_data_map = {}

        for f in all_files:
            file_set, f_event, f_group, _, _, _, f_path, _ = f

            # Normalize Set Codes (handle [Y24OTJ] vs OTJ if needed, simplified here)
            if file_set != current_set:
                continue

            if f_event not in self.current_set_data_map:
                self.current_set_data_map[f_event] = {}

            self.current_set_data_map[f_event][f_group] = f_path

        # 3. Populate Event Dropdown
        available_events = list(self.current_set_data_map.keys())
        if not available_events:
            self.vars["set_label"].set(f"SET: {current_set} (No Data)")
            self.lbl_set_code.config(foreground=Theme.WARNING)
            self._set_dropdown_options(self.om_event, self.vars["selected_event"], [])
            return

        self._set_dropdown_options(
            self.om_event, self.vars["selected_event"], available_events
        )

        # 4. Auto-Select Event Type
        # Priority: Exact Match > PremierDraft > First Available
        target_event = available_events[0]
        if current_event_type and current_event_type in available_events:
            target_event = current_event_type
        elif "PremierDraft" in available_events:
            target_event = "PremierDraft"

        if self.vars["selected_event"].get() != target_event:
            self.vars["selected_event"].set(target_event)

    def _set_dropdown_options(self, menu_widget, variable, options):
        """
        Manually populates a specific OptionMenu and explicitly binds the click command
        to the provided variable. This bypasses potential issues with ttk.OptionMenu's
        internal variable binding not being exposed via cget.
        """
        menu = menu_widget["menu"]
        menu.delete(0, "end")
        for opt in options:
            menu.add_command(label=opt, command=tkinter._setit(variable, opt))

    def _on_event_change(self):
        """Called when Event Dropdown changes."""
        if not self._initialized:
            return

        evt = self.vars["selected_event"].get()
        if not evt or evt not in self.current_set_data_map:
            return

        available_groups = list(self.current_set_data_map[evt].keys())
        self._set_dropdown_options(
            self.om_group, self.vars["selected_group"], available_groups
        )

        # Auto-Select Group (Default to All)
        target_group = "All"
        if "All" not in available_groups and available_groups:
            target_group = available_groups[0]

        self.vars["selected_group"].set(target_group)
        # This triggers _on_group_change which loads the file

    def _on_group_change(self):
        """Called when User Group changes. Performs the actual file load."""
        if not self._initialized:
            return

        evt = self.vars["selected_event"].get()
        grp = self.vars["selected_group"].get()

        if evt in self.current_set_data_map and grp in self.current_set_data_map[evt]:
            path = self.current_set_data_map[evt][grp]

            # Avoid reloading if it's the same file
            current_loaded = self.configuration.card_data.latest_dataset
            if os.path.basename(path) != current_loaded:
                self.orchestrator.scanner.retrieve_set_data(path)
                self.configuration.card_data.latest_dataset = os.path.basename(path)
                write_configuration(self.configuration)
                self._update_deck_filter_options()
                self._refresh_ui_data()

    def _update_deck_filter_options(self):
        rate_map = self.orchestrator.scanner.retrieve_color_win_rate(
            self.configuration.settings.filter_format
        )
        self.deck_filter_map = rate_map
        menu = self.om_filter["menu"]
        menu.delete(0, "end")
        for label in rate_map.keys():
            menu.add_command(
                label=label, command=lambda v=label: self.vars["deck_filter"].set(v)
            )
        rev = {v: k for k, v in rate_map.items()}
        self.vars["deck_filter"].set(
            rev.get(
                self.configuration.settings.deck_filter,
                self.configuration.settings.deck_filter,
            )
        )

    def _manual_refresh(self, use_ocr=False):
        if self.orchestrator.scanner.draft_data_search(use_ocr, False):
            self._refresh_ui_data()

    def _on_card_select(self, event, table, source_type):
        selection = table.selection()
        if not selection:
            return
        data_list = (
            self.current_pack_data
            if source_type == "pack"
            else self.current_missing_data
        )
        item_vals = table.item(selection[0])["values"]
        card_name = str(item_vals[0]).replace("*", "")
        found = next(
            (c for c in data_list if c[constants.DATA_FIELD_NAME] == card_name), None
        )
        if found:
            arch = self.orchestrator.scanner.set_data.get_card_archetypes_by_field(
                card_name, constants.DATA_FIELD_GIHWR
            )
            current_scale = constants.UI_SIZE_DICT.get(
                self.configuration.settings.ui_size, 1.0
            )
            CardToolTip(
                table,
                card_name,
                found.get(constants.DATA_FIELD_DECK_COLORS, {}),
                found.get(constants.DATA_SECTION_IMAGES, []),
                self.configuration.features.images_enabled,
                current_scale,
                archetypes=arch,
            )

    def _open_settings(self):
        def _on_settings_changed():
            # Dynamically refresh theme scaling if changed
            s = self.configuration.settings
            self.orchestrator.scanner.log_enable(s.draft_log_enabled)
            current_scale = constants.UI_SIZE_DICT.get(s.ui_size, 1.0)
            Theme.apply(
                self.root,
                palette=s.theme,
                engine=getattr(s, "theme_base", "clam"),
                custom_path=s.theme_custom_path,
                scale=current_scale,
            )
            self._update_deck_filter_options()
            self._refresh_ui_data()

        SettingsWindow(self.root, self.configuration, _on_settings_changed)

    def _read_draft_log(self):
        f = filedialog.askopenfilename(filetypes=(("Log", "*.log"), ("All", "*.*")))
        if f:
            self.orchestrator.scanner.set_arena_file(f)
            self._manual_refresh()

    def _read_player_log(self):
        """Opens a file dialog to manually select the Player.log file."""
        f = filedialog.askopenfilename(filetypes=(("Log", "*.log"), ("All", "*.*")))
        if f:
            self.orchestrator.scanner.set_arena_file(f)
            self._manual_refresh()

    def _export_csv(self):
        h = self.orchestrator.scanner.retrieve_draft_history()
        if not h:
            return
        from src.card_logic import export_draft_to_csv

        data = export_draft_to_csv(
            h,
            self.orchestrator.scanner.set_data,
            self.orchestrator.scanner.picked_cards,
        )
        f = filedialog.asksaveasfile(mode="w", defaultextension=".csv")
        if f:
            with f:
                f.write(data)
            messagebox.showinfo("Success", "Export Complete.")

    def _export_json(self):
        h = self.orchestrator.scanner.retrieve_draft_history()
        if not h:
            return
        from src.card_logic import export_draft_to_json

        data = export_draft_to_json(
            h,
            self.orchestrator.scanner.set_data,
            self.orchestrator.scanner.picked_cards,
        )
        f = filedialog.asksaveasfile(mode="w", defaultextension=".json")
        if f:
            with f:
                f.write(data)
            messagebox.showinfo("Success", "Export Complete.")

    def _on_dataset_update(self):
        self._update_data_sources()
        self._refresh_ui_data()

    def _enable_overlay(self):
        """Hides Main Window, Shows Overlay"""
        if self.overlay_window:
            return

        self.root.withdraw()  # Hide Main

        self.overlay_window = CompactOverlay(
            self.root, self.orchestrator, self.configuration, self._disable_overlay
        )
        self._refresh_ui_data()

    def _disable_overlay(self):
        """Destroys Overlay, Shows Main Window"""
        if self.overlay_window:
            self.overlay_window.destroy()
            self.overlay_window = None
        self.root.deiconify()
        self._refresh_ui_data()

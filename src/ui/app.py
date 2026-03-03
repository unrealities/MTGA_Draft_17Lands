"""
src/ui/app.py
Main UI Orchestrator. Updated for Async Background Updates.
"""

import tkinter
from tkinter import ttk, filedialog, messagebox
import os
import sys
import queue
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
    def __init__(self, root: tkinter.Tk, scanner, configuration):
        self.root = root
        self.configuration = configuration

        # 1. IMMEDIATE STATE INITIALIZATION
        # We define every single attribute here with default values.
        # This prevents AttributeErrors if background threads fire mid-constructor.
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
        self.tabs_visible = True

        # NEW STATE FOR SET SELECTION & TRACKING
        self.current_set_data_map: Dict[str, Dict[str, str]] = {}
        self.detected_set_code = ""
        self.active_event_set = ""
        self.active_event_type = ""
        self._notified_missing_sets = set()

        # 2. CORE LOGIC SERVICE
        # Instantiate the logic orchestrator (background thread)
        self.orchestrator = DraftOrchestrator(
            scanner, configuration, self._refresh_ui_data
        )

        # 3. BUILD UI SHELL (Widget Creation Only)
        # These calls create the Tkinter objects but do not perform math/IO
        self._setup_variables()
        self._build_layout()
        self._setup_menu()

        # 4. ATTACH INFRASTRUCTURE SERVICES
        # Notifications requires self.panel_data (created in _build_layout)
        self.notifications = Notifications(
            self.root, scanner.set_list, configuration, self.panel_data
        )

        # 5. VIRTUAL EVENT BINDINGS
        self.root.bind(
            "<<ShowDataTab>>",
            lambda e: self._ensure_tabs_visible()
            or self.notebook.select(self.panel_data),
        )

        # 6. INITIAL THEME APPLICATION
        # Apply theme based on config so widgets aren't the default "Grey" on flicker
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

        # 7. FINAL WINDOW PROTOCOL & METADATA
        self.root.title(f"MTGA Draft Tool v{constants.APPLICATION_VERSION}")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # 8. ENABLE LOGGING
        self.orchestrator.scanner.log_enable(
            self.configuration.settings.draft_log_enabled
        )

        # Transition to initialized state
        # main.py will now call root.after(10, app._perform_boot_sync)
        self._loading = True
        self._initialized = True

    def _perform_boot_sync(self):
        """Phase 1: Immediate synchronization of critical UI components."""
        if not self._initialized:
            return

        try:
            self.vars["status_text"].set("Syncing with Arena...")

            # 1. APPLY GEOMETRY
            try:
                geom = self.configuration.settings.main_window_geometry
                if geom and "x" in geom and not geom.startswith("1x1"):
                    self.root.geometry(geom)
                else:
                    self.root.geometry("1200x800")

                self.root.update_idletasks()

                sash_pos = self.configuration.settings.paned_window_sash
                if sash_pos > 50:
                    self.splitter.sashpos(0, sash_pos)
            except Exception as e:
                import logging

                logging.getLogger(__name__).warning(
                    f"Failed to apply window preferences: {e}"
                )

            # 2. START THE ENGINE
            self.orchestrator.start()

            # 3. SYNC DROPDOWNS (CRITICAL FIX: Ensure this is called!)
            try:
                self._update_data_sources()
                self._update_deck_filter_options()
            except Exception as e:
                import logging

                logging.getLogger(__name__).error(
                    f"Dropdown sync failed: {e}", exc_info=True
                )

            # 4. INITIAL REFRESH
            self._refresh_ui_data()

            # 5. DEFER HEAVY TABS
            self.root.after(500, self._perform_deep_sync)

        finally:
            self._loading = False

    def _perform_deep_sync(self):
        """Phase 2: Population of heavy tabs (Deck Builder, Card Pool)."""
        self.vars["status_text"].set("Ready")

        for p in [self.panel_taken, self.panel_suggest]:
            try:
                p.refresh()
            except:
                pass

        if not self.configuration.card_data.latest_dataset:
            self.notebook.select(self.panel_data)

        # Non-critical network tasks
        self.root.after(1500, self._background_update_checks)

    def _background_update_checks(self):
        """Executes non-critical network checks once the app is stable."""
        # Safety Guard: Ensure notifications object exists
        if not hasattr(self, "notifications") or self.notifications is None:
            logger.warning("Background check skipped: Notifications service not ready.")
            return

        # 1. Check for App Updates (in a separate thread)
        import threading

        def _check_app():
            try:
                from src.app_update import AppUpdate

                v, _ = AppUpdate().retrieve_file_version()
                if v and float(v) > constants.APPLICATION_VERSION:
                    self.root.after(0, lambda: self.notify_app_update(v))
            except Exception as e:
                logger.error(f"App update check failed: {e}")

        threading.Thread(target=_check_app, daemon=True).start()

        # 2. Check for Dataset Updates
        try:
            self.notifications.check_dataset()
        except Exception as e:
            logger.error(f"Dataset update check failed: {e}")

    def _restore_sash(self):
        try:
            sash_pos = getattr(self.configuration.settings, "paned_window_sash", 400)
            if sash_pos > 0:
                self.splitter.sashpos(0, sash_pos)
        except Exception:
            pass

    def _on_close(self):
        """Save geometry and sash state before closing."""
        try:
            # If the window is zoomed (maximized), don't save that as the default geom
            # Otherwise it will open as a weird fixed-size giant window next time
            if self.root.state() == "normal":
                self.configuration.settings.main_window_geometry = self.root.geometry()

            # Save the current divider position
            try:
                self.configuration.settings.paned_window_sash = self.splitter.sashpos(0)
            except:
                pass

            write_configuration(self.configuration)

            # Stop threads
            if hasattr(self, "orchestrator"):
                self.orchestrator.stop()

        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

        self.root.destroy()

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

        # --- HEADER CONTAINER ---
        header_frame = ttk.Frame(self.main_container, style="Card.TFrame", padding=5)
        header_frame.pack(fill="x", pady=(0, 10))

        # ROW 1: Status & Overlay
        row1 = ttk.Frame(header_frame, style="Card.TFrame")
        row1.pack(fill="x", pady=(0, 5))

        self.status_dot = ttk.Label(row1, text="●", foreground=Theme.TEXT_MAIN)
        self.status_dot.pack(side="left", padx=5)

        ttk.Label(
            row1,
            textvariable=self.vars["event_info"],
            font=(Theme.FONT_FAMILY, 9, "bold"),
        ).pack(side="left")

        ttk.Label(row1, text=" | ", foreground=Theme.TEXT_MAIN).pack(side="left")
        ttk.Label(row1, textvariable=self.vars["status_text"]).pack(side="left")

        ttk.Button(
            row1,
            text="Mini Mode",
            bootstyle="info-outline",
            command=self._enable_overlay,
            width=12,
        ).pack(side="right", padx=5)

        self.btn_toggle_tabs = ttk.Button(
            row1,
            text="▼ Hide Tabs",
            bootstyle="secondary-outline",
            command=self._toggle_tabs,
            width=10,
        )
        self.btn_toggle_tabs.pack(side="right", padx=5)

        self.sidebar_visible = self.configuration.settings.collapsible_states.get(
            "sidebar_panel", True
        )
        self.btn_toggle_sidebar = ttk.Button(
            row1,
            text="◀ Hide Sidebar" if self.sidebar_visible else "▶ Show Sidebar",
            bootstyle="secondary-outline",
            command=self._toggle_sidebar,
            width=13,
        )
        self.btn_toggle_sidebar.pack(side="right", padx=5)

        # ROW 2: Controls
        row2 = ttk.Frame(header_frame, style="Card.TFrame")
        row2.pack(fill="x")

        # Controls (Left)
        self.btn_reload = ttk.Button(
            row2, text="Reload", command=self._force_reload, width=7
        )
        self.btn_reload.pack(side="left", padx=2)

        self.btn_p1p1 = ttk.Button(
            row2, text="P1P1", command=lambda: self._manual_refresh(True), width=6
        )

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
        self.splitter.add(self.notebook, weight=2)

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

    def _toggle_tabs(self):
        if self.tabs_visible:
            self.splitter.forget(self.notebook)
            self.btn_toggle_tabs.config(text="▲ Show Tabs")
            self.tabs_visible = False
        else:
            self.splitter.add(self.notebook, weight=2)
            self.btn_toggle_tabs.config(text="▼ Hide Tabs")
            self.tabs_visible = True

    def _toggle_sidebar(self):
        self.sidebar_visible = not self.sidebar_visible
        self.dashboard.set_sidebar_visible(self.sidebar_visible)
        self.btn_toggle_sidebar.config(
            text="◀ Hide Sidebar" if self.sidebar_visible else "▶ Show Sidebar"
        )
        self.configuration.settings.collapsible_states["sidebar_panel"] = (
            self.sidebar_visible
        )
        write_configuration(self.configuration)

    def _ensure_tabs_visible(self):
        if not self.tabs_visible:
            self._toggle_tabs()

    def _setup_menu(self):
        m = tkinter.Menu(self.root)
        self.root.config(menu=m)

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
        file_m.add_command(label="Exit", command=self._on_close)

        theme_m = tkinter.Menu(m, tearoff=0)
        m.add_cascade(label="Theme", menu=theme_m)
        theme_m.add_command(
            label="System (Native)",
            command=lambda: self._update_theme(new_palette="System"),
        )
        theme_m.add_separator()

        for name in Theme.THEME_MAPPING.keys():
            if name == "System":
                continue
            theme_m.add_command(
                label=f"Mana Flair: {name}",
                command=lambda n=name: self._update_theme(new_palette=n),
            )

        custom_m = tkinter.Menu(theme_m, tearoff=0)
        theme_m.add_cascade(label="Custom Themes (.tcl)", menu=custom_m)
        custom_m.add_command(
            label="Browse for .tcl...", command=self._browse_custom_tcl
        )

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

        if hasattr(self, "lbl_set_code") and self.lbl_set_code.winfo_exists():
            self.lbl_set_code.configure(foreground=Theme.ACCENT)

        self._refresh_ui_data()

    def _browse_custom_tcl(self):
        f = filedialog.askopenfilename(
            filetypes=(("Tcl files", "*.tcl"), ("All", "*.*"))
        )
        if f:
            self._update_theme(new_custom=f)

    def _refresh_ui_data(self):
        """
        Core UI Synchronization Logic (v4.06 Pro).
        Uses non-blocking locks and defensive checks for Mock compatibility.
        """
        if not self._initialized or self._rebuilding_ui:
            return

        # 1. TRY-LOCK: Prevent UI hang if scanner is busy
        lock_acquired = self.orchestrator.scanner.lock.acquire(blocking=False)
        if not lock_acquired:
            return

        try:
            # DATA SNAPSHOT
            es, et = self.orchestrator.scanner.retrieve_current_limited_event()
            pk, pi = self.orchestrator.scanner.retrieve_current_pack_and_pick()
            metrics = self.orchestrator.scanner.retrieve_set_metrics()
            tier_data = self.orchestrator.scanner.retrieve_tier_data()
            taken_cards = self.orchestrator.scanner.retrieve_taken_cards()
            pack_cards = self.orchestrator.scanner.retrieve_current_pack_cards()
            missing_cards = self.orchestrator.scanner.retrieve_current_missing_cards()
            history = self.orchestrator.scanner.retrieve_draft_history()
        finally:
            self.orchestrator.scanner.lock.release()

        # 2. ADVISOR & SIGNAL MATH
        from src.advisor.engine import DraftAdvisor
        from src.signals import SignalCalculator

        advisor = DraftAdvisor(metrics, taken_cards)
        recommendations = advisor.evaluate_pack(pack_cards, pi)

        sig_calc = SignalCalculator(metrics)
        scores = {c: 0.0 for c in constants.CARD_COLORS}
        for entry in history:
            if entry["Pack"] == 2:
                continue
            h_pack = self.orchestrator.scanner.set_data.get_data_by_id(entry["Cards"])
            for c, v in sig_calc.calculate_pack_signals(h_pack, entry["Pick"]).items():
                scores[c] += v

        # 3. DRAW BASIC UI ELEMENTS
        self.vars["event_info"].set(f"{es} {et}" if es else "Waiting for draft...")
        self.vars["status_text"].set(f"Pack {pk} Pick {pi}" if pk > 0 else "Idle")

        if self.configuration.settings.p1p1_ocr_enabled and pk <= 1 and pi <= 1:
            self.btn_p1p1.pack(side="left", padx=2, after=self.btn_reload)
        else:
            self.btn_p1p1.pack_forget()

        # 4. REFRESH DASHBOARD
        colors = filter_options(
            taken_cards,
            self.configuration.settings.deck_filter,
            metrics,
            self.configuration,
        )

        self.dashboard.update_recommendations(recommendations)
        self.dashboard.update_signals(scores)
        self.dashboard.update_pack_data(
            pack_cards, colors, metrics, tier_data, pi, "pack", recommendations
        )
        self.dashboard.update_pack_data(
            missing_cards, colors, metrics, tier_data, pi, "missing"
        )

        deck_metrics = get_deck_metrics(taken_cards)
        self.dashboard.update_stats(deck_metrics.distribution_all)
        self.dashboard.update_deck_balance(taken_cards)

        if self.overlay_window:
            self.overlay_window.update_data(
                pack_cards, colors, metrics, tier_data, pi, recommendations
            )

        # 5. DEFENSIVE TAB REFRESH (Fixed for Pytest)
        # Check if panels have 'refresh' to support Mock objects in tests
        for p in [
            self.panel_taken,
            self.panel_suggest,
            self.panel_compare,
            self.panel_tiers,
        ]:
            try:
                if hasattr(p, "refresh"):
                    p.refresh()
            except Exception:
                pass

        self.current_pack_data = pack_cards
        self.current_missing_data = missing_cards

    def _calculate_signals(self, metrics):
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
        return scores

    def _update_loop(self):
        """UI Poll Loop: Checks the orchestrator's queue for updates."""
        if not self.root.winfo_exists():
            return

        is_test = "pytest" in sys.modules
        if not self.orchestrator.is_alive() or is_test:
            self.orchestrator.step_process()

        # 1. Process Logic Updates from Background Thread
        update_detected = False
        while True:
            try:
                self.orchestrator.update_queue.get_nowait()
                update_detected = True
            except queue.Empty:
                break

        if update_detected:
            # Check if event changed to update dropdowns
            self._update_data_sources()
            self._update_deck_filter_options()
            self._refresh_ui_data()
            if is_test:
                self.root.update()

        # 2. Update status dot color based on file modified time
        try:
            ts = os.stat(self.orchestrator.scanner.arena_file).st_mtime
            self.status_dot.config(
                foreground=(
                    Theme.SUCCESS if ts != self.previous_timestamp else Theme.TEXT_MAIN
                )
            )
            self.previous_timestamp = ts
        except:
            pass

        self._schedule_update()

    def _schedule_update(self):
        self._update_task_id = self.root.after(100, self._update_loop)

    def _on_filter_ui_change(self):
        # Guard: Don't trigger if we are mid-boot or mid-update
        if not self._initialized or self._loading:
            return
        label = self.vars["deck_filter"].get()
        self.configuration.settings.deck_filter = self.deck_filter_map.get(label, label)
        write_configuration(self.configuration)
        self._refresh_ui_data()

    def _update_data_sources(self):
        """Synchronizes UI dropdowns with the detected set and local files."""
        import re
        from src import constants

        try:
            current_set, current_event_type = (
                self.orchestrator.scanner.retrieve_current_limited_event()
            )

            event_transitioned = False
            if (
                current_set != self.active_event_set
                or current_event_type != self.active_event_type
                or self.orchestrator.new_event_detected
            ):

                event_transitioned = True
                self.active_event_set = current_set
                self.active_event_type = current_event_type
                self.orchestrator.new_event_detected = False

            if not current_set:
                self.vars["set_label"].set("NO SET")
                self._set_dropdown_options(
                    self.om_event, self.vars["selected_event"], []
                )
                self._set_dropdown_options(
                    self.om_group, self.vars["selected_group"], []
                )
                return

            # Map the raw Set Code to the Human-Readable Set Name
            full_set_name = current_set
            if (
                self.orchestrator.scanner.set_list
                and self.orchestrator.scanner.set_list.data
            ):
                for name, info in self.orchestrator.scanner.set_list.data.items():
                    if info.set_code == current_set:
                        full_set_name = name
                        break

            self.detected_set_code = current_set
            display_name = (
                full_set_name
                if len(full_set_name) <= 25
                else full_set_name[:22] + "..."
            )

            all_files, _ = retrieve_local_set_list()
            self.current_set_data_map = {}

            # UNIVERSAL MATCHER: Strips all punctuation/spaces for a pure alphanumeric comparison
            def normalize_code(code_string):
                return re.sub(r"[^A-Z0-9]", "", str(code_string).upper())

            normalized_current = normalize_code(current_set)

            for f in all_files:
                file_set, f_event, f_group, _, _, _, f_path, _ = f

                if normalize_code(file_set) != normalized_current:
                    continue

                if f_event not in self.current_set_data_map:
                    self.current_set_data_map[f_event] = {}
                self.current_set_data_map[f_event][f_group] = f_path

            available_events = list(self.current_set_data_map.keys())

            # If no data is found for the event, clear dropdowns and alert the user
            if not available_events:
                self.vars["set_label"].set(f"SET: {display_name} (No Data)")
                self._set_dropdown_options(
                    self.om_event, self.vars["selected_event"], []
                )
                self._set_dropdown_options(
                    self.om_group, self.vars["selected_group"], []
                )
                return

            self.vars["set_label"].set(f"SET: {display_name}")
            self._set_dropdown_options(
                self.om_event, self.vars["selected_event"], available_events
            )

            current_selection = self.vars["selected_event"].get()

            # STATE TRANSITION LOGIC:
            # 1. Try to select the exact event type you are playing (e.g. QuickDraft)
            # 2. Fallback to PremierDraft (The baseline format for 17Lands data)
            # 3. Fallback to the first available dataset
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

            # Apply the selection and trigger UI updates
            if self.vars["selected_event"].get() != target_event:
                self.vars["selected_event"].set(target_event)
            else:
                self._on_event_change()

        except Exception as e:
            import logging

            logging.getLogger(__name__).error(
                f"Error in _update_data_sources: {e}", exc_info=True
            )

    def _set_dropdown_options(self, menu_widget, variable, options):
        menu = menu_widget["menu"]
        menu.delete(0, "end")
        for opt in options:
            menu.add_command(label=opt, command=tkinter._setit(variable, opt))

    def _on_event_change(self):
        if not self._initialized:
            return
        evt = self.vars["selected_event"].get()
        if not evt or evt not in self.current_set_data_map:
            return
        available_groups = list(self.current_set_data_map[evt].keys())
        self._set_dropdown_options(
            self.om_group, self.vars["selected_group"], available_groups
        )
        target_group = self.vars["selected_group"].get()
        if target_group not in available_groups:
            target_group = (
                "All"
                if "All" in available_groups
                else (available_groups[0] if available_groups else "")
            )
        if target_group and self.vars["selected_group"].get() != target_group:
            self.vars["selected_group"].set(target_group)
        else:
            self._on_group_change()

    def _on_group_change(self):
        if not self._initialized:
            return
        evt = self.vars["selected_event"].get()
        grp = self.vars["selected_group"].get()
        if evt in self.current_set_data_map and grp in self.current_set_data_map[evt]:
            path = self.current_set_data_map[evt][grp]
            current_loaded = self.configuration.card_data.latest_dataset
            if os.path.basename(path) != current_loaded:
                self.orchestrator.scanner.retrieve_set_data(path)
                self.configuration.card_data.latest_dataset = os.path.basename(path)
                write_configuration(self.configuration)
                self._update_deck_filter_options()
                self.orchestrator.request_math_update()
                self._refresh_ui_data()

    def _force_reload(self):
        """Perform a complete deep-scan of the Arena logs to rebuild the state."""
        self.vars["status_text"].set("Deep Scanning Log...")
        self.root.update_idletasks()

        with self.orchestrator.scanner.lock:
            self.orchestrator.scanner.clear_draft(True)

        self.orchestrator.trigger_full_scan()

    def _update_deck_filter_options(self):
        """Refreshes the Deck Filter dropdown with latest 17Lands win rates."""
        # Logic Guard: Allow execution during startup/tests by checking if var is empty
        if self._loading and self.vars["deck_filter"].get() != "":
            return

        old_loading = self._loading
        self._loading = True
        try:
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

            current_setting = self.configuration.settings.deck_filter
            if current_setting not in rate_map.values():
                current_setting = constants.FILTER_OPTION_AUTO
                self.configuration.settings.deck_filter = current_setting

            target_label = next(
                (label for label, key in rate_map.items() if key == current_setting),
                current_setting,
            )
            self.vars["deck_filter"].set(target_label)
        finally:
            self._loading = old_loading

    def _manual_refresh(self, use_ocr=False):
        save_img = (
            self.configuration.settings.save_screenshot_enabled if use_ocr else False
        )
        if use_ocr:
            self.btn_p1p1.config(state="disabled")
            if self.overlay_window and hasattr(self.overlay_window, "btn_scan"):
                self.overlay_window.btn_scan.config(state="disabled")

            def update_btn_text(msg):
                def _update():
                    if self.btn_p1p1.winfo_exists():
                        self.btn_p1p1.config(text=msg)
                    if (
                        self.overlay_window
                        and hasattr(self.overlay_window, "btn_scan")
                        and self.overlay_window.btn_scan.winfo_exists()
                    ):
                        self.overlay_window.btn_scan.config(text=msg)

                try:
                    self.root.after(0, _update)
                except RuntimeError:
                    pass

            def _scan_thread():
                data_found = self.orchestrator.scanner.run_ocr_workflow(
                    save_img, status_callback=update_btn_text
                )
                try:
                    self.root.after(0, lambda: self._on_scan_complete(data_found))
                except RuntimeError:
                    pass

            import threading

            threading.Thread(target=_scan_thread, daemon=True).start()
        else:
            if self.orchestrator.scanner.draft_data_search(False, save_img):
                self._refresh_ui_data()

    def _on_scan_complete(self, data_found):
        if self.btn_p1p1.winfo_exists():
            self.btn_p1p1.config(text="P1P1", state="normal")
        if (
            self.overlay_window
            and hasattr(self.overlay_window, "btn_scan")
            and self.overlay_window.btn_scan.winfo_exists()
        ):
            self.overlay_window.btn_scan.config(text="SCAN P1P1", state="normal")

        if data_found:
            self.orchestrator.request_math_update()
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
        try:
            name_idx = table.active_fields.index("name")
            raw_name = str(item_vals[name_idx])
            card_name = (
                raw_name.replace("⭐ ", "").replace("[+] ", "").replace("*", "").strip()
            )
        except ValueError:
            return
        found = next(
            (c for c in data_list if c[constants.DATA_FIELD_NAME] == card_name), None
        )
        if found:
            current_scale = constants.UI_SIZE_DICT.get(
                self.configuration.settings.ui_size, 1.0
            )
            CardToolTip(
                table, found, self.configuration.features.images_enabled, current_scale
            )

    def notify_app_update(self, new_version):
        self.root.title(
            f"MTGA Draft Tool v{constants.APPLICATION_VERSION} (Update Available: v{new_version})"
        )
        prompt = f"A new version of the MTGA Draft Tool (v{new_version}) is available.\n\nWould you like to download it now?"
        if messagebox.askyesno("Update Available", prompt):
            from src.utils import open_file

            open_file(
                "https://github.com/unrealities/MTGA_Draft_17Lands/releases/latest"
            )

    def _open_settings(self):
        def _on_settings_changed():
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
            if s.p1p1_ocr_enabled:
                self.btn_p1p1.pack(side="left", padx=2, after=self.btn_reload)
            else:
                self.btn_p1p1.pack_forget()
            self._update_deck_filter_options()
            self._refresh_ui_data()

        parent_window = self.overlay_window if self.overlay_window else self.root
        SettingsWindow(parent_window, self.configuration, _on_settings_changed)

    def _read_draft_log(self):
        f = filedialog.askopenfilename(filetypes=(("Log", "*.log"), ("All", "*.*")))
        if f:
            self.orchestrator.scanner.set_arena_file(f)
            self._manual_refresh()

    def _read_player_log(self):
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
        self.orchestrator.request_math_update()
        self._refresh_ui_data()

    def _enable_overlay(self):
        if self.overlay_window:
            return
        self.root.withdraw()
        self.overlay_window = CompactOverlay(
            self.root, self, self.configuration, self._disable_overlay
        )
        self._refresh_ui_data()

    def _disable_overlay(self):
        if self.overlay_window:
            self.overlay_window.destroy()
            self.overlay_window = None
        self.root.deiconify()
        self._refresh_ui_data()

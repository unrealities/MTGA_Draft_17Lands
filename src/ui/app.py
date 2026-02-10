"""
src/ui/app.py
Professional Dashboard Orchestrator.
Coordinates between Log Scanner, Dashboard View, and Management Panels.
"""

import tkinter
from tkinter import ttk, filedialog, messagebox
import os
from typing import Dict

from src import constants
from src.configuration import Configuration, write_configuration
from src.log_scanner import ArenaScanner
from src.card_logic import filter_options
from src.ui.styles import Theme
from src.ui.components import CardToolTip
from src.ui.dashboard import DashboardFrame  # New Modular Component
from src.ui.windows.settings import SettingsWindow
from src.notifications import Notifications

# Tab Panel Imports
from src.ui.windows.taken_cards import TakenCardsPanel
from src.ui.windows.suggest_deck import SuggestDeckPanel
from src.ui.windows.compare import ComparePanel
from src.ui.windows.download import DownloadWindow
from src.ui.windows.tier_list import TierListWindow


class DraftApp:
    def __init__(
        self, root: tkinter.Tk, scanner: ArenaScanner, configuration: Configuration
    ):
        self.scanner = scanner
        self.configuration = configuration
        self.root = root

        self._initialized = False
        self._loading = False
        self.previous_timestamp = 0
        self.deck_filter_map: Dict[str, str] = {}
        self.current_pack_data = []
        self.current_missing_data = []

        self.root.deiconify()
        self.root.title(f"MTGA Draft Tool v{constants.APPLICATION_VERSION}")
        self.root.geometry("1250x850")

        Theme.apply(self.root, getattr(configuration.settings, "theme", "Dark"))

        self.vars: Dict[str, tkinter.Variable] = {}
        self._setup_variables()
        self._build_layout()
        self._setup_menu()

        self.notifications = Notifications(
            self.root, self.scanner.set_list, self.configuration, self.panel_data
        )
        self.root.bind(
            "<<ShowDataTab>>", lambda e: self.notebook.select(self.panel_data)
        )

        self._update_data_sources()
        self._update_deck_filter_options()
        self._perform_startup_sync()

        self._initialized = True
        self.root.update()
        self._refresh_ui_data()

        self.root.after(1000, self._update_loop)

    def _setup_variables(self):
        self.vars["deck_filter"] = tkinter.StringVar(
            value=self.configuration.settings.deck_filter
        )
        self.vars["data_source"] = tkinter.StringVar(value="None")
        self.vars["status_text"] = tkinter.StringVar(value="Ready")
        self.vars["event_info"] = tkinter.StringVar(value="Scan logs...")

        self.vars["deck_filter"].trace_add(
            "write", lambda *a: self._on_filter_ui_change()
        )
        self.vars["data_source"].trace_add(
            "write", lambda *a: self._on_source_change_event()
        )

    def _perform_startup_sync(self):
        label = self.vars["data_source"].get()
        sources = self.scanner.retrieve_data_sources()
        if label in sources:
            self.scanner.retrieve_set_data(sources[label])
            self._update_deck_filter_options()

    def _build_layout(self):
        if hasattr(self, "main_container"):
            self.main_container.destroy()
        self.main_container = ttk.Frame(self.root, padding=8)
        self.main_container.pack(fill="both", expand=True)

        # 1. Action Bar
        bar = ttk.Frame(self.main_container, style="Card.TFrame", padding=10)
        bar.pack(fill="x", pady=(0, 10))
        info = ttk.Frame(bar, style="Card.TFrame")
        info.pack(side="left")
        self.status_dot = ttk.Label(info, text="●", style="Status.TLabel")
        self.status_dot.pack(side="left", padx=5)
        ttk.Label(
            info, textvariable=self.vars["event_info"], style="Status.TLabel"
        ).pack(side="left")
        ttk.Label(info, text="|", style="Dashboard.Muted.TLabel").pack(
            side="left", padx=10
        )
        ttk.Label(
            info, textvariable=self.vars["status_text"], style="Dashboard.TLabel"
        ).pack(side="left")

        ctrl = ttk.Frame(bar, style="Card.TFrame")
        ctrl.pack(side="right")
        ttk.Label(ctrl, text="Source:", style="Dashboard.Muted.TLabel").pack(
            side="left"
        )
        self.om_source = ttk.OptionMenu(
            ctrl,
            self.vars["data_source"],
            self.vars["data_source"].get(),
            style="TMenubutton",
        )
        self.om_source.pack(side="left", padx=5)
        ttk.Label(ctrl, text="Filter:", style="Dashboard.Muted.TLabel").pack(
            side="left"
        )
        self.om_filter = ttk.OptionMenu(
            ctrl,
            self.vars["deck_filter"],
            self.vars["deck_filter"].get(),
            style="TMenubutton",
        )
        self.om_filter.pack(side="left", padx=5)
        ttk.Button(
            ctrl,
            text="Refresh Logs",
            width=12,
            command=lambda: self._manual_refresh(use_ocr=True),
        ).pack(side="left", padx=(10, 5))

        self.splitter = ttk.PanedWindow(self.main_container, orient=tkinter.VERTICAL)
        self.splitter.pack(fill="both", expand=True)

        # 2. THE DASHBOARD (Modular)
        self.dashboard = DashboardFrame(
            self.splitter, self.configuration, self._on_table_select
        )
        self.splitter.add(self.dashboard, weight=4)

        # 3. THE NOTEBOOK
        self.notebook = ttk.Notebook(self.splitter)
        self.splitter.add(self.notebook, weight=3)
        self.panel_taken = TakenCardsPanel(
            self.notebook, self.scanner, self.configuration
        )
        self.panel_suggest = SuggestDeckPanel(
            self.notebook, self.scanner, self.configuration
        )
        self.panel_compare = ComparePanel(
            self.notebook, self.scanner, self.configuration
        )
        self.panel_data = DownloadWindow(
            self.notebook,
            self.scanner.set_list,
            self.configuration,
            self._on_dataset_update,
        )
        self.panel_tiers = TierListWindow(self.notebook, self._refresh_ui_data)

        self.notebook.add(self.panel_taken, text=" Card Pool ")
        self.notebook.add(self.panel_suggest, text=" Deck Builder ")
        self.notebook.add(self.panel_compare, text=" Comparisons ")
        self.notebook.add(self.panel_data, text=" Dataset Manager ")
        self.notebook.add(self.panel_tiers, text=" Tier Lists ")

    def _refresh_ui_data(self):
        if not self._initialized or self._loading:
            return
        es, et = self.scanner.retrieve_current_limited_event()
        pk, pi = self.scanner.retrieve_current_pack_and_pick()
        self.vars["event_info"].set(f"{es} {et}" if es else "Scan logs...")
        self.vars["status_text"].set(f"P{pk} Pick {pi}")

        metrics = self.scanner.retrieve_set_metrics()
        tier_data = self.scanner.retrieve_tier_data()
        colors = filter_options(
            self.scanner.retrieve_taken_cards(),
            self.configuration.settings.deck_filter,
            metrics,
            self.configuration,
        )

        # Refresh Dashboard Tables
        self.current_pack_data = self.scanner.retrieve_current_pack_cards()
        self.dashboard.update_pack_data(
            self.current_pack_data, colors, metrics, tier_data, pi, "pack"
        )

        self.current_missing_data = self.scanner.retrieve_current_missing_cards()
        self.dashboard.update_pack_data(
            self.current_missing_data, colors, metrics, tier_data, pi, "missing"
        )

        # Refresh Signals
        from src.signals import SignalCalculator

        calc = SignalCalculator(metrics)
        history = self.scanner.retrieve_draft_history()
        scores = {c: 0.0 for c in constants.CARD_COLORS}
        for entry in history:
            if entry["Pack"] == 2:
                continue
            for c, v in calc.calculate_pack_signals(
                self.scanner.set_data.get_data_by_id(entry["Cards"]), entry["Pick"]
            ).items():
                scores[c] += v
        self.dashboard.update_signals(scores)

        # Refresh Pool Curve
        from src.card_logic import get_deck_metrics

        m = get_deck_metrics(self.scanner.retrieve_taken_cards())
        self.dashboard.update_stats(m.distribution_all)

        # Sync Tabs
        self.panel_taken.refresh()
        self.panel_suggest.refresh()
        self.panel_compare.refresh()

    def _on_table_select(self, event, table, source_type):
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
            stats = found.get(constants.DATA_FIELD_DECK_COLORS, {})
            images = found.get(constants.DATA_SECTION_IMAGES, [])
            archetypes = self.scanner.set_data.get_card_archetypes_by_field(
                card_name, constants.DATA_FIELD_GIHWR
            )
            CardToolTip(
                table,
                card_name,
                stats,
                images,
                self.configuration.features.images_enabled,
                1.0,
                archetypes=archetypes,
            )

    def _on_filter_ui_change(self):
        if not self._initialized:
            return
        label = self.vars["deck_filter"].get()
        self.configuration.settings.deck_filter = self.deck_filter_map.get(label, label)
        write_configuration(self.configuration)
        self._refresh_ui_data()

    def _on_source_change_event(self):
        if not self._initialized:
            return
        label = self.vars["data_source"].get()
        sources = self.scanner.retrieve_data_sources()
        if label in sources:
            self._loading = True
            self.vars["status_text"].set("LOADING...")
            self.status_dot.config(foreground=Theme.WARNING)
            self.root.update()
            self.scanner.retrieve_set_data(sources[label])
            self.configuration.card_data.latest_dataset = os.path.basename(
                sources[label]
            )
            write_configuration(self.configuration)
            self._loading = False
            self._update_deck_filter_options()
            self._refresh_ui_data()

    def _update_loop(self):
        update = False
        if self.scanner.draft_start_search():
            update = True
            self._update_data_sources()
            self._update_deck_filter_options()
        if self.scanner.draft_data_search(use_ocr=False, save_screenshot=False):
            update = True
        if update:
            self._refresh_ui_data()
        try:
            ts = os.stat(self.scanner.arena_file).st_mtime
            if not self._loading:
                self.status_dot.config(
                    foreground=(
                        Theme.SUCCESS
                        if ts != self.previous_timestamp
                        else Theme.TEXT_MUTED
                    )
                )
            self.previous_timestamp = ts
        except:
            self.status_dot.config(foreground=Theme.ERROR)
        self.root.after(1000, self._update_loop)

    def _manual_refresh(self, use_ocr=False):
        if self.scanner.draft_data_search(use_ocr=use_ocr, save_screenshot=False):
            self._refresh_ui_data()

    def _setup_menu(self):
        m = tkinter.Menu(self.root)
        self.root.config(menu=m)
        f = tkinter.Menu(m, tearoff=0)
        m.add_cascade(label="File", menu=f)
        f.add_command(label="Read Draft Log...", command=self._read_draft_log)
        f.add_command(label="Read Player.log...", command=self._read_player_log)
        f.add_separator()
        f.add_command(label="Export Draft (CSV)", command=self._export_csv)
        f.add_command(label="Export Draft (JSON)", command=self._export_json)
        f.add_separator()
        f.add_command(label="Exit", command=self.root.destroy)
        t = tkinter.Menu(m, tearoff=0)
        m.add_cascade(label="Theme", menu=t)
        for theme_name in Theme.PALETTES.keys():
            t.add_command(
                label=theme_name,
                command=lambda name=theme_name: self._change_theme(name),
            )
        d = tkinter.Menu(m, tearoff=0)
        m.add_cascade(label="Data", menu=d)
        d.add_command(
            label="Open Dataset Manager",
            command=lambda: self.notebook.select(self.panel_data),
        )
        d.add_command(
            label="Open Tier List Manager",
            command=lambda: self.notebook.select(self.panel_tiers),
        )
        s = tkinter.Menu(m, tearoff=0)
        m.add_cascade(label="Settings", menu=s)
        s.add_command(label="Preferences...", command=self._open_settings)

    def _change_theme(self, name):
        Theme.apply(self.root, name)
        self.configuration.settings.theme = name
        write_configuration(self.configuration)
        self._build_layout()
        self._refresh_ui_data()

    def _open_settings(self):
        SettingsWindow(self.root, self.configuration, self._on_settings_closed)

    def _on_settings_closed(self):
        self._build_layout()
        self._refresh_ui_data()

    def _update_data_sources(self):
        all_s = self.scanner.retrieve_data_sources()
        es, _ = self.scanner.retrieve_current_limited_event()
        display = {
            k: v for k, v in all_s.items() if not es or f"[{es}]" in k or "TIER" in k
        } or all_s
        menu = self.om_source["menu"]
        menu.delete(0, "end")
        for label in display:
            menu.add_command(
                label=label, command=lambda v=label: self.vars["data_source"].set(v)
            )
        cur = self.vars["data_source"].get()
        if cur not in display:
            found = next(iter(display)) if display else "None"
            for lbl, pth in display.items():
                if os.path.basename(pth) == self.configuration.card_data.latest_dataset:
                    found = lbl
                    break
            self.vars["data_source"].set(found)

    def _update_deck_filter_options(self):
        rate_map = self.scanner.retrieve_color_win_rate(
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

    def _on_dataset_update(self):
        self._update_data_sources()
        self._refresh_ui_data()

    def _read_draft_log(self):
        f = filedialog.askopenfilename(filetypes=(("Log", "*.log"), ("All", "*.*")))
        if f:
            self.scanner.set_arena_file(f)
            self._manual_refresh()

    def _read_player_log(self):
        from src.file_extractor import search_arena_log_locations

        loc = search_arena_log_locations([])
        self.scanner.set_arena_file(loc) if loc else None
        self._refresh_ui_data()

    def _export_csv(self):
        h = self.scanner.retrieve_draft_history()
        if h:
            from src.card_logic import export_draft_to_csv

            data = export_draft_to_csv(
                h, self.scanner.set_data, self.scanner.picked_cards
            )
            f = filedialog.asksaveasfile(mode="w", defaultextension=".csv")
            f.write(data) if f else None

    def _export_json(self):
        h = self.scanner.retrieve_draft_history()
        if h:
            from src.card_logic import export_draft_to_json

            data = export_draft_to_json(
                h, self.scanner.set_data, self.scanner.picked_cards
            )
            f = filedialog.asksaveasfile(mode="w", defaultextension=".json")
            f.write(data) if f else None

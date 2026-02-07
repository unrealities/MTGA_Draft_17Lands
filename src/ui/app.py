"""
src/ui/app.py

This module contains the main application class `DraftApp`.
"""

import tkinter
from tkinter import ttk, filedialog, messagebox
import webbrowser
import os
from typing import Dict

from src import constants
from src.configuration import Configuration, write_configuration
from src.log_scanner import ArenaScanner
from src.card_logic import filter_options, field_process_sort
from src.ui.styles import Theme
from src.ui.components import ModernTreeview, CardToolTip
from src.ui.windows.settings import SettingsWindow
from src.ui.windows.taken_cards import TakenCardsWindow
from src.ui.windows.suggest_deck import SuggestDeckWindow
from src.ui.windows.compare import CompareWindow
from src.ui.windows.download import DownloadWindow
from src.ui.windows.tier_list import TierListWindow
from src.notifications import Notifications
from src.card_logic import CardResult


class DraftApp:
    def __init__(
        self, root: tkinter.Tk, scanner: ArenaScanner, configuration: Configuration
    ):
        self.scanner = scanner
        self.configuration = configuration
        self.root = root

        # Clean up Root (Remove Splash widgets if any remain)
        for widget in self.root.winfo_children():
            widget.destroy()

        # Configure Root
        self.root.deiconify()
        self.root.title(f"MTGA Draft Tool v{constants.APPLICATION_VERSION}")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Re-apply theme just to be safe
        current_theme = getattr(configuration.settings, "theme", "Dark")
        Theme.apply(self.root, current_theme)

        # State
        self.vars: Dict[str, tkinter.Variable] = {}
        self.windows: Dict[str, tkinter.Toplevel] = {}
        self.log_check_id = None
        self.previous_timestamp = 0
        self.deck_filter_map: Dict[str, str] = {}

        # UI Setup
        self.download_window = DownloadWindow(
            self.root,
            self.scanner.set_list,
            self.configuration,
            self._on_dataset_update,
        )

        self._setup_variables()
        self._build_layout()
        self._setup_menu()

        # Data Init
        self._update_data_sources()
        self._update_deck_filter_options()
        self._rebuild_tables()

        self._start_log_check()
        self.root.after(1000, self._update_loop)

        # Defer notifications so window renders first
        self.root.after(500, self._init_notifications)

    def _init_notifications(self):
        self.notifications = Notifications(
            self.root, self.scanner.set_list, self.configuration, self.download_window
        )
        self.notifications.check_for_updates()

    def run(self):
        self.root.mainloop()

    def _setup_variables(self):
        self.vars["deck_filter"] = tkinter.StringVar(
            value=constants.DECK_FILTER_DEFAULT
        )
        self.vars["data_source"] = tkinter.StringVar(value="None")
        self.vars["pack_info"] = tkinter.StringVar(value="Pack 0, Pick 0")

    def _build_layout(self):
        self.main_container = ttk.Frame(self.root, padding=15)
        self.main_container.pack(fill="both", expand=True)

        self._build_header()
        self._build_controls()

        self.frame_tables = ttk.Frame(self.main_container)
        self.frame_tables.pack(fill="both", expand=True, pady=(10, 0))

        self._build_footer()

    def _build_header(self):
        header_frame = ttk.Frame(self.main_container)
        header_frame.pack(fill="x", pady=(0, 10))

        info_frame = ttk.Frame(header_frame)
        info_frame.pack(side="left")

        ttk.Label(info_frame, text="Current Draft", style="Header.TLabel").pack(
            anchor="w"
        )
        self.lbl_draft_event = ttk.Label(
            info_frame, text="None", style="SubHeader.TLabel", foreground=Theme.ACCENT
        )
        self.lbl_draft_event.pack(anchor="w")

        status_frame = ttk.Frame(header_frame)
        status_frame.pack(side="right", anchor="ne")

        self.status_dot = ttk.Label(
            status_frame, text="●", foreground=Theme.ERROR, font=("Arial", 16)
        )
        self.status_dot.pack(side="right", padx=5)

        ttk.Label(
            status_frame, textvariable=self.vars["pack_info"], style="SubHeader.TLabel"
        ).pack(side="right", padx=10)

    def _build_controls(self):
        control_card = ttk.Frame(self.main_container, style="Card.TFrame", padding=10)
        control_card.pack(fill="x")

        control_card.columnconfigure(1, weight=1)
        control_card.columnconfigure(3, weight=1)

        ttk.Label(control_card, text="Data Source:").grid(row=0, column=0, sticky="w")
        self.om_data_source = ttk.OptionMenu(
            control_card,
            self.vars["data_source"],
            "None",
            style="TMenubutton",
            command=self._on_source_change,
        )
        self.om_data_source.grid(row=0, column=1, sticky="ew", padx=(5, 15))

        ttk.Label(control_card, text="Deck Filter:").grid(row=0, column=2, sticky="w")
        self.om_deck_filter = ttk.OptionMenu(
            control_card,
            self.vars["deck_filter"],
            constants.DECK_FILTER_DEFAULT,
            *constants.DECK_FILTERS,
            style="TMenubutton",
            command=self._on_filter_change,
        )
        self.om_deck_filter.grid(row=0, column=3, sticky="ew", padx=(5, 0))

        btn_frame = ttk.Frame(control_card)
        btn_frame.grid(row=1, column=0, columnspan=4, pady=(10, 0))

        ttk.Button(
            btn_frame,
            text="Refresh Log",
            command=lambda: self._manual_refresh(use_ocr=True),
        ).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Taken Cards", command=self._open_taken_cards).pack(
            side="left", padx=5
        )
        ttk.Button(btn_frame, text="Compare", command=self._open_compare).pack(
            side="left", padx=5
        )
        ttk.Button(
            btn_frame,
            text="Suggest Deck",
            style="Accent.TButton",
            command=self._open_suggest_deck,
        ).pack(side="left", padx=5)

    def _build_footer(self):
        footer = ttk.Frame(self.main_container)
        footer.pack(fill="x", side="bottom", pady=(10, 0))

        ttk.Label(footer, text="Not endorsed by 17Lands", style="Muted.TLabel").pack(
            side="right"
        )
        link = ttk.Label(footer, text="GitHub", style="Muted.TLabel", cursor="hand2")
        link.pack(side="left")
        link.bind(
            "<Button-1>",
            lambda e: webbrowser.open(
                "https://github.com/unrealities/MTGA_Draft_17Lands"
            ),
        )

    def _setup_menu(self):
        menubar = tkinter.Menu(self.root)

        file_menu = tkinter.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Read Draft Log", command=self._read_draft_log)
        file_menu.add_command(label="Read Player.log", command=self._read_player_log)
        file_menu.add_separator()
        file_menu.add_command(label="Export Draft (CSV)", command=self._export_csv)
        file_menu.add_command(label="Export Draft (JSON)", command=self._export_json)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_close)
        menubar.add_cascade(label="File", menu=file_menu)

        data_menu = tkinter.Menu(menubar, tearoff=0)
        data_menu.add_command(
            label="Download Dataset", command=self._open_download_window
        )
        data_menu.add_command(
            label="Download Tier List", command=self._open_tier_window
        )
        menubar.add_cascade(label="Data", menu=data_menu)

        cards_menu = tkinter.Menu(menubar, tearoff=0)
        cards_menu.add_command(label="Taken Cards", command=self._open_taken_cards)
        cards_menu.add_command(label="Suggest Decks", command=self._open_suggest_deck)
        cards_menu.add_command(label="Compare Cards", command=self._open_compare)
        menubar.add_cascade(label="Cards", menu=cards_menu)

        settings_menu = tkinter.Menu(menubar, tearoff=0)
        settings_menu.add_command(label="Preferences...", command=self._open_settings)
        menubar.add_cascade(label="Settings", menu=settings_menu)

        help_menu = tkinter.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self._open_about)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.root.config(menu=menubar)

    def _rebuild_tables(self):
        for widget in self.frame_tables.winfo_children():
            widget.destroy()

        # Pack Table
        ttk.Label(
            self.frame_tables, text="Current Pack", style="SubHeader.TLabel"
        ).pack(anchor="w", pady=(0, 5))

        cols = ["Card"]
        headers_config = {"Card": {"width": 200, "anchor": tkinter.W}}
        self.active_fields = [constants.DATA_FIELD_NAME]

        settings = self.configuration.settings
        col_settings = [
            settings.column_2,
            settings.column_3,
            settings.column_4,
            settings.column_5,
            settings.column_6,
            settings.column_7,
        ]

        key_to_label = {v: k for k, v in constants.COLUMNS_OPTIONS_EXTRA_DICT.items()}

        for col_val in col_settings:
            if col_val != constants.DATA_FIELD_DISABLED:
                full_label = key_to_label.get(col_val, col_val.upper())
                short_label = full_label.split(":")[0].strip()
                cols.append(short_label)
                headers_config[short_label] = {"width": 60, "anchor": tkinter.CENTER}
                self.active_fields.append(col_val)

        self.table_pack = ModernTreeview(
            self.frame_tables, columns=cols, headers_config=headers_config, height=8
        )
        self.table_pack.pack(fill="x", expand=False, pady=(0, 15))
        self.table_pack.bind(
            "<<TreeviewSelect>>",
            lambda e: self._on_table_select(e, self.table_pack, "pack"),
        )

        # Missing Cards
        if self.configuration.settings.missing_enabled:
            ttk.Label(
                self.frame_tables, text="Missing Cards", style="SubHeader.TLabel"
            ).pack(anchor="w", pady=(0, 5))
            self.table_missing = ModernTreeview(
                self.frame_tables, columns=cols, headers_config=headers_config, height=6
            )
            self.table_missing.pack(fill="x", expand=False, pady=(0, 15))
            self.table_missing.bind(
                "<<TreeviewSelect>>",
                lambda e: self._on_table_select(e, self.table_missing, "missing"),
            )

        # Signals
        if self.configuration.settings.signals_enabled:
            ttk.Label(
                self.frame_tables, text="Signals (Pack 1 & 3)", style="SubHeader.TLabel"
            ).pack(anchor="w", pady=(0, 5))
            sig_cols = ["Color", "Score"]
            sig_headers = {
                "Color": {"width": 100, "anchor": tkinter.W},
                "Score": {"width": 100, "anchor": tkinter.CENTER},
            }
            self.table_signals = ModernTreeview(
                self.frame_tables,
                columns=sig_cols,
                headers_config=sig_headers,
                height=5,
                stretch_all=True,
            )
            self.table_signals.pack(fill="x", expand=False)

        self._refresh_ui_data()

    def _update_deck_filter_options(self):
        rate_map = self.scanner.retrieve_color_win_rate(
            self.configuration.settings.filter_format
        )
        self.deck_filter_map = rate_map
        key_to_label = {v: k for k, v in rate_map.items()}

        menu = self.om_deck_filter["menu"]
        menu.delete(0, "end")

        options = list(rate_map.keys())
        for label in options:
            menu.add_command(
                label=label, command=lambda v=label: self._on_filter_change(v)
            )

        current_internal = self.configuration.settings.deck_filter
        if current_internal in key_to_label:
            self.vars["deck_filter"].set(key_to_label[current_internal])
        else:
            self.vars["deck_filter"].set(current_internal)

    def _on_filter_change(self, value):
        internal_key = self.deck_filter_map.get(value, value)
        self.vars["deck_filter"].set(value)
        self.configuration.settings.deck_filter = internal_key
        write_configuration(self.configuration)
        self._refresh_ui_data()

    def _update_loop(self):
        update_ui = False
        if self.scanner.draft_start_search():
            update_ui = True
            self._update_data_sources()
            self._update_deck_filter_options()
            _, event_type = self.scanner.retrieve_current_limited_event()
            if "Sealed" in event_type:
                self._open_taken_cards()

        if self.scanner.draft_data_search(
            use_ocr=False,
            save_screenshot=self.configuration.settings.save_screenshot_enabled,
        ):
            update_ui = True

        if update_ui:
            self._refresh_ui_data()

        self.root.after(1000, self._update_loop)

    def _start_log_check(self):
        try:
            current_timestamp = os.stat(self.scanner.arena_file).st_mtime
            if current_timestamp != self.previous_timestamp:
                self.previous_timestamp = current_timestamp
                self.status_dot.config(foreground=Theme.SUCCESS)
        except Exception:
            self.status_dot.config(foreground=Theme.ERROR)

        self.root.after(1000, self._start_log_check)

    def _manual_refresh(self, use_ocr=False):
        if self.scanner.draft_data_search(
            use_ocr=use_ocr,
            save_screenshot=self.configuration.settings.save_screenshot_enabled,
        ):
            self._refresh_ui_data()

    def _refresh_ui_data(self):
        event_set, event_type = self.scanner.retrieve_current_limited_event()
        pack, pick = self.scanner.retrieve_current_pack_and_pick()

        self.lbl_draft_event.config(
            text=f"{event_set} {event_type}" if event_set else "Waiting for draft..."
        )
        self.vars["pack_info"].set(f"Pack {pack}, Pick {pick}")

        current_internal = self.configuration.settings.deck_filter
        filter_colors = [current_internal]

        if current_internal == constants.FILTER_OPTION_AUTO:
            taken_cards = self.scanner.retrieve_taken_cards()
            metrics = self.scanner.retrieve_set_metrics()
            filter_colors = filter_options(
                taken_cards, current_internal, metrics, self.configuration
            )

        metrics = self.scanner.retrieve_set_metrics()
        tier_data = self.scanner.retrieve_tier_data()

        pack_cards = self.scanner.retrieve_current_pack_cards()
        self._populate_table(
            self.table_pack, pack_cards, filter_colors, metrics, tier_data
        )
        self.current_pack_data = pack_cards

        if self.configuration.settings.missing_enabled and hasattr(
            self, "table_missing"
        ):
            missing_cards = self.scanner.retrieve_current_missing_cards()
            self._populate_table(
                self.table_missing,
                missing_cards,
                filter_colors,
                metrics,
                tier_data,
                mark_picked=True,
            )
            self.current_missing_data = missing_cards

        if self.configuration.settings.signals_enabled and hasattr(
            self, "table_signals"
        ):
            self._update_signals()

    def _populate_table(
        self, table, cards, colors, metrics, tier_data, mark_picked=False
    ):
        for item in table.get_children():
            table.delete(item)

        if not cards:
            return

        processor = CardResult(
            metrics, tier_data, self.configuration, self.scanner.current_pick
        )
        results = processor.return_results(cards, colors, self.active_fields)

        if mark_picked:
            picked_cards = self.scanner.retrieve_current_picked_cards()
            picked_names = [c[constants.DATA_FIELD_NAME] for c in picked_cards]
            for res in results:
                if res["results"][0] in picked_names:
                    res["results"][0] = f"*{res['results'][0]}"

        sort_idx = 1 if len(self.active_fields) > 1 else 0
        results.sort(
            key=lambda x: field_process_sort(x["results"][sort_idx]), reverse=True
        )

        from src.card_logic import row_color_tag

        for idx, item in enumerate(results):
            tag = ""
            if self.configuration.settings.card_colors_enabled:
                c_colors = item.get(constants.DATA_FIELD_MANA_COST, "")
                if constants.CARD_TYPE_LAND in item.get(constants.DATA_FIELD_TYPES, []):
                    c_colors = item.get(constants.DATA_FIELD_COLORS, [])
                tag = row_color_tag(
                    list(c_colors) if isinstance(c_colors, str) else c_colors
                )
            else:
                tag = "bw_odd" if idx % 2 != 0 else "bw_even"

            table.insert("", "end", iid=idx, values=item["results"], tags=(tag,))

    def _update_signals(self):
        from src.signals import SignalCalculator

        metrics = self.scanner.retrieve_set_metrics()
        history = self.scanner.retrieve_draft_history()

        if not history or not metrics:
            return

        calc = SignalCalculator(metrics)
        scores = {c: 0.0 for c in constants.CARD_COLORS}

        for entry in history:
            if entry["Pack"] == 2:
                continue
            pack_cards = self.scanner.set_data.get_data_by_id(entry["Cards"])
            s = calc.calculate_pack_signals(pack_cards, entry["Pick"])
            for c, val in s.items():
                scores[c] += val

        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        for item in self.table_signals.get_children():
            self.table_signals.delete(item)

        from src.card_logic import row_color_tag

        for idx, (color, score) in enumerate(sorted_scores):
            tag = (
                row_color_tag([color])
                if self.configuration.settings.card_colors_enabled
                else ("bw_odd" if idx % 2 else "bw_even")
            )
            name = constants.COLOR_NAMES_DICT.get(color, color)
            self.table_signals.insert(
                "", "end", values=(name, f"{score:.1f}"), tags=(tag,)
            )

    def _on_table_select(self, event, table, source_type):
        selection = table.selection()
        if not selection:
            return
        idx = int(selection[0])
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
            current_internal = self.configuration.settings.deck_filter
            show_colors = (
                [current_internal]
                if current_internal != constants.FILTER_OPTION_AUTO
                else None
            )

            CardToolTip(
                table,
                card_name,
                stats,
                images,
                self.configuration.features.images_enabled,
                1.0,
                None,
                archetypes,
                show_colors=show_colors,
            )

    def _open_settings(self):
        if (
            "settings" not in self.windows
            or not self.windows["settings"].winfo_exists()
        ):
            self.windows["settings"] = SettingsWindow(
                self.root, self.configuration, self._rebuild_tables
            )

    def _open_taken_cards(self):
        if "taken" not in self.windows or not self.windows["taken"].winfo_exists():
            self.windows["taken"] = TakenCardsWindow(
                self.root, self.scanner, self.configuration
            )

    def _open_suggest_deck(self):
        if "suggest" not in self.windows or not self.windows["suggest"].winfo_exists():
            self.windows["suggest"] = SuggestDeckWindow(
                self.root, self.scanner, self.configuration
            )

    def _open_compare(self):
        if "compare" not in self.windows or not self.windows["compare"].winfo_exists():
            self.windows["compare"] = CompareWindow(
                self.root, self.scanner, self.configuration
            )

    def _open_download_window(self):
        self.download_window.deiconify()
        self.download_window.lift()

    def _open_tier_window(self):
        TierListWindow(self.root, self._on_dataset_update)

    def _open_about(self):
        messagebox.showinfo(
            "About",
            f"MTGA Draft Tool v{constants.APPLICATION_VERSION}\n\nNot endorsed by 17Lands.\nCreated by u/bstaple1 & maintained by unrealities.",
        )

    def _update_data_sources(self):
        sources = self.scanner.retrieve_data_sources()
        menu = self.om_data_source["menu"]
        menu.delete(0, "end")
        for key in sources:
            menu.add_command(label=key, command=lambda v=key: self._on_source_change(v))
        if self.vars["data_source"].get() not in sources:
            first = next(iter(sources)) if sources else "None"
            self.vars["data_source"].set(first)
            self.scanner.retrieve_set_data(sources.get(first, ""))

    def _on_source_change(self, value):
        self.vars["data_source"].set(value)
        sources = self.scanner.retrieve_data_sources()
        if value in sources:
            self.scanner.retrieve_set_data(sources[value])
            self.notifications.update_latest_dataset(sources[value])
            self._update_deck_filter_options()
            self._refresh_ui_data()

    def _on_dataset_update(self):
        self._update_data_sources()
        self._update_deck_filter_options()
        self._refresh_ui_data()

    def _read_draft_log(self):
        filename = filedialog.askopenfilename(
            filetypes=(("Log Files", "*.log"), ("All files", "*.*"))
        )
        if filename:
            self.scanner.set_arena_file(filename)
            self._manual_refresh()

    def _read_player_log(self):
        from src.file_extractor import search_arena_log_locations

        loc = search_arena_log_locations([])
        if loc:
            self.scanner.set_arena_file(loc)
            self.configuration.settings.arena_log_location = loc
            write_configuration(self.configuration)
            self._manual_refresh()

    def _export_csv(self):
        history = self.scanner.retrieve_draft_history()
        if history:
            from src.card_logic import export_draft_to_csv

            data = export_draft_to_csv(
                history, self.scanner.set_data, self.scanner.picked_cards
            )
            f = filedialog.asksaveasfile(mode="w", defaultextension=".csv")
            if f:
                f.write(data)
                f.close()

    def _export_json(self):
        history = self.scanner.retrieve_draft_history()
        if history:
            from src.card_logic import export_draft_to_json

            data = export_draft_to_json(
                history, self.scanner.set_data, self.scanner.picked_cards
            )
            f = filedialog.asksaveasfile(mode="w", defaultextension=".json")
            if f:
                f.write(data)
                f.close()

    def _on_close(self):
        self.root.destroy()

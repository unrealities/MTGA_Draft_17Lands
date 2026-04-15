"""
src/ui/windows/overlay.py
Compact Mini Mode Window for in-game drafting.
"""

import tkinter
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from src import constants
from src.card_logic import row_color_tag, stack_cards, get_deck_metrics
from src.ui.styles import Theme
from src.ui.components import (
    DynamicTreeviewManager,
    CardToolTip,
    SignalMeter,
    ManaCurvePlot,
    TypePieChart,
)
from src.ui.advisor_view import AdvisorPanel
from src.configuration import write_configuration
from src.card_logic import format_win_rate


class CompactOverlay(tb.Toplevel):
    def __init__(self, parent, app_context, configuration, on_restore):
        super().__init__(title="Mini Mode", topmost=True)
        self.app_context = app_context
        self.orchestrator = app_context.orchestrator
        self.configuration = configuration
        self.on_restore = on_restore

        self.current_pack_cards = []
        self.current_pool_cards = []

        if "overlay_pool_table" not in self.configuration.settings.column_configs:
            self.configuration.settings.column_configs["overlay_pool_table"] = [
                "name",
                "count",
                "gihwr",
            ]

        self.overrideredirect(True)
        geom = getattr(
            self.configuration.settings,
            "overlay_geometry",
            f"{Theme.scaled_val(380)}x{Theme.scaled_val(600)}+50+50",
        )
        self.geometry(geom)

        try:
            self.attributes("-alpha", 0.92)
        except Exception:
            pass

        self._build_ui()

    def _start_move(self, event):
        self.x = event.x
        self.y = event.y

    def _stop_move(self, event):
        self.x = None
        self.y = None
        self._save_geometry()

    def _do_move(self, event):
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.winfo_x() + deltax
        y = self.winfo_y() + deltay
        self.geometry(f"+{x}+{y}")

    def _start_resize(self, event):
        self._start_w = self.winfo_width()
        self._start_h = self.winfo_height()
        self._start_x = event.x_root
        self._start_y = event.y_root

    def _do_resize(self, event):
        new_w = max(
            Theme.scaled_val(250), self._start_w + (event.x_root - self._start_x)
        )
        new_h = max(
            Theme.scaled_val(200), self._start_h + (event.y_root - self._start_y)
        )
        self.geometry(f"{new_w}x{new_h}")

    def _stop_resize(self, event):
        self._save_geometry()

    def _save_geometry(self):
        self.configuration.settings.overlay_geometry = self.geometry()
        write_configuration(self.configuration)

    def _close_overlay(self):
        self._save_geometry()
        self.on_restore()

    def _build_ui(self):
        # --- HEADER (Draggable) ---
        header = tb.Frame(self, bootstyle="secondary")
        header.pack(fill=X, ipady=Theme.scaled_val(5))

        header.bind("<ButtonPress-1>", self._start_move)
        header.bind("<ButtonRelease-1>", self._stop_move)
        header.bind("<B1-Motion>", self._do_move)

        self.btn_scan = tb.Button(
            header,
            text="SCAN P1P1",
            bootstyle="success-outline",
            command=self._manual_scan,
        )

        # Dynamic Info Label (Format | Group | Filter)
        self.lbl_info = tb.Label(
            header, text="", font=Theme.scaled_font(9), bootstyle="inverse-secondary"
        )
        self.lbl_info.pack(side=LEFT, padx=Theme.scaled_val((8, 0)))

        # Action Buttons
        tb.Button(header, text="⤢", bootstyle="link", command=self._close_overlay).pack(
            side=RIGHT, padx=Theme.scaled_val((0, 5))
        )
        self.btn_settings = tb.Button(
            header, text="⚙", bootstyle="link", command=self._show_settings_menu
        )
        self.btn_settings.pack(side=RIGHT, padx=Theme.scaled_val(2))

        self.lbl_status = tb.Label(
            header,
            text="Waiting...",
            font=Theme.scaled_font(10, "bold"),
            bootstyle="inverse-secondary",
        )
        self.lbl_status.pack(side=RIGHT, padx=Theme.scaled_val(5))

        # --- FOOTER (Resize Grip) ---
        footer = tb.Frame(self, bootstyle="secondary")
        footer.pack(fill=X, side=BOTTOM)

        grip = tb.Label(
            footer,
            text=" ⇲ ",
            cursor="hand2",
            bootstyle="inverse-secondary",
            font=Theme.scaled_font(12),
        )
        grip.pack(side=RIGHT, padx=Theme.scaled_val(2))
        grip.bind("<ButtonPress-1>", self._start_resize)
        grip.bind("<B1-Motion>", self._do_resize)
        grip.bind("<ButtonRelease-1>", self._stop_resize)

        # --- TABBED CONTENT ---
        self.notebook = tb.Notebook(self)
        self.notebook.pack(
            fill=BOTH,
            expand=True,
            padx=Theme.scaled_val(2),
            pady=Theme.scaled_val(2),
            side=TOP,
        )

        self.tab_pack = tb.Frame(self.notebook, padding=Theme.scaled_val(2))
        self.tab_advisor = tb.Frame(self.notebook, padding=Theme.scaled_val(10))
        self.tab_stats = tb.Frame(self.notebook, padding=Theme.scaled_val(10))
        self.tab_pool = tb.Frame(self.notebook, padding=Theme.scaled_val(2))

        self.notebook.add(self.tab_pack, text=" Pack ")
        self.notebook.add(self.tab_advisor, text=" Advisor ")
        self.notebook.add(self.tab_stats, text=" Stats ")
        self.notebook.add(self.tab_pool, text=" Pool ")

        # 1. Pack Tab (Dynamic Grid)
        self.tab_pack.columnconfigure(0, weight=1)
        self.tab_pack.rowconfigure(0, weight=1)

        # Pack Table
        self.pack_frame = tb.Frame(self.tab_pack)
        self.pack_frame.grid(row=0, column=0, sticky="nsew")
        self.table_manager = DynamicTreeviewManager(
            self.pack_frame,
            view_id="overlay_table",
            configuration=self.configuration,
            on_update_callback=self._trigger_refresh,
            height=1,
        )
        self.table_manager.pack(fill=BOTH, expand=True)

        # Missing Table (Hidden initially)
        self.missing_frame = tb.Frame(self.tab_pack)
        tb.Label(
            self.missing_frame,
            text="SEEN CARDS (WHEEL)",
            foreground=None,
            bootstyle="primary",
        ).pack(anchor="w", pady=Theme.scaled_val((4, 2)), padx=Theme.scaled_val(2))
        self.missing_manager = DynamicTreeviewManager(
            self.missing_frame,
            view_id="missing_table",
            configuration=self.configuration,
            on_update_callback=self._trigger_refresh,
            height=1,
        )
        self.missing_manager.pack(fill=BOTH, expand=True)
        self.missing_frame.grid_remove()

        # 2. Pool Table
        self.pool_manager = DynamicTreeviewManager(
            self.tab_pool,
            view_id="overlay_pool_table",
            configuration=self.configuration,
            on_update_callback=self._trigger_refresh,
            height=1,
        )
        self.pool_manager.pack(fill=BOTH, expand=True)

        # 3. Advisor Tab
        self.advisor_panel = AdvisorPanel(
            self.tab_advisor,
            self.configuration,
            collapsible=False,
            mini_mode=True,
            on_click_callback=self.app_context._show_tooltip_from_advisor,
        )
        self.advisor_panel.pack(fill=BOTH, expand=True, anchor="n", side="top")

        # 4. Stats Tab
        tb.Label(
            self.tab_stats,
            text="OPEN LANES",
            font=Theme.scaled_font(10, "bold"),
            bootstyle="primary",
        ).pack(anchor="w", pady=(0, Theme.scaled_val(5)))
        self.signal_meter = SignalMeter(self.tab_stats)
        self.signal_meter.pack(fill=X, pady=(0, Theme.scaled_val(15)))

        tb.Label(
            self.tab_stats,
            text="MANA CURVE",
            font=Theme.scaled_font(10, "bold"),
            bootstyle="primary",
        ).pack(anchor="w", pady=(0, Theme.scaled_val(5)))
        self.curve_plot = ManaCurvePlot(
            self.tab_stats,
            ideal_distribution=self.configuration.card_logic.deck_mid.distribution,
        )
        self.curve_plot.pack(fill=X, pady=(0, Theme.scaled_val(15)))

        tb.Label(
            self.tab_stats,
            text="POOL BALANCE",
            font=Theme.scaled_font(10, "bold"),
            bootstyle="primary",
        ).pack(anchor="w", pady=(0, Theme.scaled_val(5)))
        self.type_chart = TypePieChart(self.tab_stats)
        self.type_chart.pack(fill=X, pady=(0, Theme.scaled_val(15)))

        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

    def _on_tab_changed(self, event):
        """Forces Tkinter to redraw the contents of the newly selected tab."""
        self.update_idletasks()
        if hasattr(self, "signal_meter"):
            self.signal_meter.redraw()
        if hasattr(self, "curve_plot"):
            self.curve_plot.redraw()
        if hasattr(self, "type_chart"):
            self.type_chart.redraw()

    def _force_stats_redraw(self):
        """Deep redraw to ensure canvases appear even if the tab was hidden."""
        self.update_idletasks()
        if hasattr(self, "signal_meter"):
            self.signal_meter.redraw()
        if hasattr(self, "curve_plot"):
            self.curve_plot.redraw()
        if hasattr(self, "type_chart"):
            self.type_chart.redraw()

    def _show_settings_menu(self):
        menu = tkinter.Menu(self, tearoff=0)
        filter_menu = tkinter.Menu(menu, tearoff=0)
        for label in self.app_context.deck_filter_map.keys():
            filter_menu.add_command(
                label=label,
                command=lambda l=label: self.app_context.vars["deck_filter"].set(l),
            )
        menu.add_cascade(label="Colors (Filter)", menu=filter_menu)

        event_menu = tkinter.Menu(menu, tearoff=0)
        for e in self.app_context.current_set_data_map.keys():
            event_menu.add_command(
                label=e,
                command=lambda ev=e: self.app_context.vars["selected_event"].set(ev),
            )
        menu.add_cascade(label="Event Type", menu=event_menu)

        group_menu = tkinter.Menu(menu, tearoff=0)
        evt = self.app_context.vars["selected_event"].get()
        if evt in self.app_context.current_set_data_map:
            for grp in self.app_context.current_set_data_map[evt].keys():
                group_menu.add_command(
                    label=grp,
                    command=lambda g=grp: self.app_context.vars["selected_group"].set(
                        g
                    ),
                )
        menu.add_cascade(label="User Group", menu=group_menu)
        menu.add_separator()
        menu.add_command(
            label="Preferences...", command=self.app_context._open_settings
        )

        menu.post(
            self.btn_settings.winfo_rootx(),
            self.btn_settings.winfo_rooty() + self.btn_settings.winfo_height(),
        )

    def _trigger_refresh(self):
        if hasattr(self.orchestrator, "refresh_callback"):
            self.orchestrator.refresh_callback()

    def _manual_scan(self):
        # Offload to async thread in the main app to prevent UI freezing
        self.app_context._manual_refresh(use_ocr=True)

    def update_data(
        self,
        pack_cards,
        colors,
        metrics,
        tier_data,
        current_pick,
        recommendations=None,
        picked_cards=None,
    ):
        evt = self.app_context.vars["selected_event"].get()
        grp = self.app_context.vars["selected_group"].get()
        filt = self.app_context.vars["deck_filter"].get()

        if filt == constants.FILTER_OPTION_AUTO:
            active_color = colors[0] if colors else "All Decks"
            if active_color != "All Decks":
                color_ratings = (
                    self.app_context.orchestrator.scanner.set_data.get_color_ratings()
                )
                wr_str = (
                    f" {color_ratings[active_color]}%"
                    if active_color in color_ratings
                    else ""
                )
                display_name = active_color
                if (
                    self.configuration.settings.filter_format
                    == constants.DECK_FILTER_FORMAT_NAMES
                    and active_color in constants.COLOR_NAMES_DICT
                ):
                    display_name = constants.COLOR_NAMES_DICT[active_color]
                filt = f"Auto ({display_name}{wr_str})"

        # Graceful fallback if no data is loaded
        if not evt:
            _, evt = (
                self.app_context.orchestrator.scanner.retrieve_current_limited_event()
            )
            grp = "No Data"

        self.lbl_info.config(text=f"{evt} ({grp}) | {filt}")

        self.current_pack_cards = pack_cards or []
        taken_cards = self.orchestrator.scanner.retrieve_taken_cards()
        self.current_pool_cards = stack_cards(taken_cards) if taken_cards else []
        missing_cards = self.orchestrator.scanner.retrieve_current_missing_cards()
        self.current_missing_cards = missing_cards

        pk, pi = self.orchestrator.scanner.retrieve_current_pack_and_pick()
        self.lbl_status.config(text=f"P{pk} / P{pi}")

        if pk <= 1 and pi <= 1:
            self.btn_scan.pack(
                side=LEFT, padx=Theme.scaled_val(5), before=self.lbl_info
            )
        else:
            self.btn_scan.pack_forget()

        self.advisor_panel.update_recommendations(recommendations)
        self.signal_meter.update_values(self.app_context._calculate_signals(metrics))

        if taken_cards:
            deck_metrics = get_deck_metrics(taken_cards)
            self.curve_plot.update_curve(deck_metrics.distribution_all)

            type_counts = {
                "Creature": 0,
                "Planeswalker": 0,
                "Battle": 0,
                "Instant": 0,
                "Sorcery": 0,
                "Enchantment": 0,
                "Artifact": 0,
                "Land": 0,
            }
            for card in taken_cards:
                name = card.get("name", "")
                types = card.get("types", [])

                # EXCLUDE BASIC LANDS
                if "Basic" in types or name in constants.BASIC_LANDS:
                    continue

                if "Creature" in types:
                    type_counts["Creature"] += 1
                elif "Planeswalker" in types:
                    type_counts["Planeswalker"] += 1
                elif "Battle" in types:
                    type_counts["Battle"] += 1
                elif "Instant" in types:
                    type_counts["Instant"] += 1
                elif "Sorcery" in types:
                    type_counts["Sorcery"] += 1
                elif "Enchantment" in types:
                    type_counts["Enchantment"] += 1
                elif "Artifact" in types:
                    type_counts["Artifact"] += 1
                elif "Land" in types:
                    type_counts["Land"] += 1
            self.type_chart.update_counts(type_counts)
        else:
            self.curve_plot.update_curve([0] * 8)
            self.type_chart.update_counts({})

        self._force_stats_redraw()

        # Dynamic Grid Weights for Pack Tab (Wheel Tracker Logic)
        if not missing_cards:
            self.missing_frame.grid_remove()
            self.tab_pack.rowconfigure(0, weight=1)
            self.tab_pack.rowconfigure(1, weight=0)
        else:
            self.missing_frame.grid(row=1, column=0, sticky="nsew")
            pack_w = max(1, len(self.current_pack_cards))
            miss_w = max(1, len(missing_cards))
            self.tab_pack.rowconfigure(0, weight=pack_w)
            self.tab_pack.rowconfigure(1, weight=miss_w)
            self.tab_pack.update_idletasks()

        # Update Tables
        active_filter = colors[0] if colors else "All Decks"
        rec_map = {r.card_name: r for r in (recommendations or [])}

        def _populate_tree(
            tree, manager, card_list, show_recs=False, is_pool=False, picked_cards=None
        ):
            for item in tree.get_children():
                tree.delete(item)
            if not card_list:
                return

            processed_rows = []
            for idx, card in enumerate(card_list):
                name = card.get(constants.DATA_FIELD_NAME, "Unknown")
                stats = card.get("deck_colors", {}).get(active_filter, {})
                rec = rec_map.get(name) if show_recs else None

                row_tag = "bw_odd" if idx % 2 == 0 else "bw_even"
                if self.configuration.settings.card_colors_enabled:
                    row_tag = row_color_tag(
                        card.get(constants.DATA_FIELD_MANA_COST, "")
                    )

                is_picked = False
                if picked_cards and show_recs:
                    if any(
                        c.get(constants.DATA_FIELD_NAME) == name for c in picked_cards
                    ):
                        is_picked = True

                display_name = name
                if rec:
                    if rec.is_elite:
                        display_name = f"⭐ {name}"
                        if not self.configuration.settings.card_colors_enabled:
                            row_tag = "elite_bomb"
                    elif rec.archetype_fit == "High":
                        display_name = f"[+] {name}"
                        if not self.configuration.settings.card_colors_enabled:
                            row_tag = "high_fit"

                if is_picked:
                    row_tag = "picked"

                row_values = []
                for field in manager.active_fields:
                    if field == "name":
                        short_name = (
                            display_name
                            if len(display_name) <= 22
                            else display_name[:20] + ".."
                        )
                        row_values.append(short_name)
                    elif field == "count":
                        row_values.append(str(card.get("count", 1) if is_pool else "-"))
                    elif field == "value":
                        if rec:
                            row_values.append(f"{rec.contextual_score:.0f}")
                        else:
                            row_values.append("-")
                    elif field == "colors":
                        row_values.append("".join(card.get("colors", [])))
                    elif field == "tags":
                        raw_tags = card.get("tags", [])
                        if raw_tags:
                            icons = [
                                constants.TAG_VISUALS.get(t, t).split(" ")[0]
                                for t in raw_tags
                            ]
                            row_values.append(" ".join(icons))
                        else:
                            row_values.append("-")
                    elif field == "wheel":
                        row_values.append(
                            f"{rec.wheel_chance:.0f}%"
                            if rec and rec.wheel_chance > 0
                            else "-"
                        )
                    elif "TIER" in field:
                        tier_obj = tier_data.get(field) if tier_data else None
                        if tier_obj and name in tier_obj.ratings:
                            row_values.append(tier_obj.ratings[name].rating)
                        else:
                            row_values.append("NA")
                    else:
                        val = stats.get(field, 0.0)
                        row_values.append(
                            format_win_rate(
                                val,
                                active_filter,
                                field,
                                metrics,
                                self.configuration.settings.result_format,
                            )
                        )

                sort_val = rec.contextual_score if rec else stats.get("gihwr", 0.0)
                processed_rows.append(
                    {"vals": row_values, "tag": row_tag, "sort_key": sort_val}
                )

            if not is_pool:
                processed_rows.sort(key=lambda x: x["sort_key"], reverse=True)

            for i, row in enumerate(processed_rows):
                if (
                    not self.configuration.settings.card_colors_enabled
                    and "elite" not in row["tag"]
                    and "high" not in row["tag"]
                ):
                    row["tag"] = "bw_odd" if i % 2 == 0 else "bw_even"
                tree.insert("", "end", values=row["vals"], tags=(row["tag"],))

            if hasattr(tree, "reapply_sort"):
                tree.reapply_sort()

        self.tree = self.table_manager.tree
        if not getattr(self.tree, "_selection_bound", False):
            self.tree.bind(
                "<ButtonRelease-1>",
                lambda e: self._on_card_select(e, self.current_pack_cards),
                add="+",
            )
            self.tree._selection_bound = True

        _populate_tree(
            self.tree,
            self.table_manager,
            self.current_pack_cards,
            show_recs=True,
            is_pool=False,
            picked_cards=picked_cards,
        )

        self.missing_tree = self.missing_manager.tree
        if not getattr(self.missing_tree, "_selection_bound", False):
            self.missing_tree.bind(
                "<ButtonRelease-1>",
                lambda e: self._on_card_select(e, self.current_missing_cards),
                add="+",
            )
            self.missing_tree._selection_bound = True

        _populate_tree(
            self.missing_tree,
            self.missing_manager,
            missing_cards,
            show_recs=False,
            is_pool=False,
        )

        self.pool_tree = self.pool_manager.tree
        if not getattr(self.pool_tree, "_selection_bound", False):
            self.pool_tree.bind(
                "<ButtonRelease-1>",
                lambda e: self._on_card_select(e, self.current_pool_cards),
                add="+",
            )
            self.pool_tree._selection_bound = True

        _populate_tree(
            self.pool_tree,
            self.pool_manager,
            self.current_pool_cards,
            show_recs=False,
            is_pool=True,
        )

    def _on_card_select(self, event, source_list):
        tree = event.widget
        if hasattr(event, "x") and hasattr(event, "y"):
            region = tree.identify_region(event.x, event.y)
            if region not in ("tree", "cell"):
                return

        selection = tree.selection()
        if not selection:
            return

        item_vals = tree.item(selection[0])["values"]
        try:
            name_idx = getattr(
                tree, "active_fields", self.table_manager.active_fields
            ).index("name")
            card_name = (
                str(item_vals[name_idx])
                .replace("⭐ ", "")
                .replace("[+] ", "")
                .replace("..", "")
                .strip()
            )
        except (ValueError, AttributeError, IndexError):
            return

        card = next((c for c in source_list if c.get("name") == card_name), None)
        if card:
            CardToolTip.create(
                tree,
                card,
                self.configuration.features.images_enabled,
                Theme.current_scale,
            )

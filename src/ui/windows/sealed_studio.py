"""
src/ui/windows/sealed_studio.py
"""

import tkinter
from tkinter import ttk, messagebox, simpledialog
import ttkbootstrap as tb
import requests
import json
from typing import List, Dict

from src import constants
from src.configuration import Configuration
from src.ui.styles import Theme
from src.ui.components import (
    DynamicTreeviewManager,
    ManaCurvePlot,
    TypePieChart,
    CardToolTip,
)
from src.card_logic import copy_deck, get_deck_metrics
from src.sealed_logic import SealedSession, generate_sealed_shells
from src.utils import open_file


class SealedStudioWindow(tb.Toplevel):
    def __init__(
        self,
        parent,
        app_context,
        configuration: Configuration,
        raw_pool: List[Dict],
        metrics,
    ):
        super().__init__(parent)
        self.app_context = app_context
        self.configuration = configuration
        self.metrics = metrics

        self.title("Epic Sealed Studio - MTGA Draft Tool")

        width = Theme.scaled_val(1400)
        height = Theme.scaled_val(900)
        self.geometry(f"{width}x{height}")
        self.minsize(Theme.scaled_val(1000), Theme.scaled_val(700))

        draft_id = app_context.orchestrator.scanner.current_draft_id or "local_sealed"

        # Load or create session
        self.session = SealedSession.load_session(draft_id, raw_pool)
        if not self.session:
            self.session = SealedSession(draft_id)
            self.session.load_pool(raw_pool)

        self.filter_vars = {
            "creatures": tkinter.IntVar(value=1),
            "spells": tkinter.IntVar(value=1),
            "lands": tkinter.IntVar(value=1),
        }

        if "sealed_pool_table" not in self.configuration.settings.column_configs:
            self.configuration.settings.column_configs["sealed_pool_table"] = [
                "name",
                "count",
                "cmc",
                "types",
                "colors",
                "gihwr",
            ]
        if "sealed_deck_table" not in self.configuration.settings.column_configs:
            self.configuration.settings.column_configs["sealed_deck_table"] = [
                "name",
                "count",
                "cmc",
                "types",
                "colors",
                "gihwr",
            ]

        self._build_ui()
        self._refresh_tabs()
        self._refresh_data()
        self.update_idletasks()
        self.focus_force()

        # Handle window close to save state
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        header = tb.Frame(self, style="Card.TFrame", padding=Theme.scaled_val(10))
        header.pack(fill="x", side="top")

        tb.Label(
            header,
            text="EPIC SEALED STUDIO",
            font=Theme.scaled_font(18, "bold"),
            bootstyle="primary",
        ).pack(side="left")

        tb.Button(
            header,
            text="🤖 Auto-Generate Shells",
            bootstyle="success",
            command=self._on_auto_generate,
        ).pack(side="left", padx=Theme.scaled_val(20))

        tb.Button(
            header,
            text="🌐 Export to Sealeddeck.tech",
            bootstyle="warning-outline",
            command=self._export_to_sealeddeck_tech,
        ).pack(side="right", padx=Theme.scaled_val(5))
        tb.Button(
            header,
            text="📋 Copy MTGA Format",
            bootstyle="info-outline",
            command=self._export_active_deck,
        ).pack(side="right", padx=Theme.scaled_val(5))

        self.splitter = tb.PanedWindow(self, orient=tkinter.HORIZONTAL)
        self.splitter.pack(
            fill="both",
            expand=True,
            padx=Theme.scaled_val(10),
            pady=Theme.scaled_val(10),
        )

        # LEFT PANE: MASTER POOL
        self.left_pane = tb.Frame(self.splitter)
        self.splitter.add(self.left_pane, weight=1)

        pool_header = tb.Frame(self.left_pane)
        pool_header.pack(fill="x", pady=Theme.scaled_val((0, 5)))

        self.lbl_pool_title = tb.Label(
            pool_header, text="MASTER POOL (0)", font=Theme.scaled_font(12, "bold")
        )
        self.lbl_pool_title.pack(side="left")

        filter_frame = tb.Frame(pool_header)
        filter_frame.pack(side="right")
        tb.Checkbutton(
            filter_frame,
            text="Creatures",
            variable=self.filter_vars["creatures"],
            command=self._refresh_data,
        ).pack(side="left", padx=2)
        tb.Checkbutton(
            filter_frame,
            text="Spells",
            variable=self.filter_vars["spells"],
            command=self._refresh_data,
        ).pack(side="left", padx=2)
        tb.Checkbutton(
            filter_frame,
            text="Lands",
            variable=self.filter_vars["lands"],
            command=self._refresh_data,
        ).pack(side="left", padx=2)

        self.pool_manager = DynamicTreeviewManager(
            self.left_pane,
            view_id="sealed_pool_table",
            configuration=self.configuration,
            on_update_callback=self._refresh_data,
        )
        self.pool_manager.pack(fill="both", expand=True)

        # RIGHT PANE: WORKBENCH
        self.right_pane = tb.Frame(self.splitter)
        self.splitter.add(self.right_pane, weight=1)

        tab_header = tb.Frame(self.right_pane)
        tab_header.pack(fill="x")

        self.notebook = tb.Notebook(tab_header)
        self.notebook.pack(side="left", fill="x", expand=True)
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        # Quick tab controls
        tb.Button(
            tab_header,
            text="➕",
            width=3,
            command=self._create_new_tab,
            bootstyle="secondary-outline",
        ).pack(side="right", padx=2, pady=2)
        tb.Button(
            tab_header,
            text="✏️",
            width=3,
            command=self._rename_tab,
            bootstyle="secondary-outline",
        ).pack(side="right", padx=2, pady=2)
        tb.Button(
            tab_header,
            text="🗑️",
            width=3,
            command=self._delete_tab,
            bootstyle="danger-outline",
        ).pack(side="right", padx=2, pady=2)

        deck_controls = tb.Frame(
            self.right_pane, style="Card.TFrame", padding=Theme.scaled_val(5)
        )
        deck_controls.pack(fill="x", pady=Theme.scaled_val((0, 5)))

        self.lbl_deck_title = tb.Label(
            deck_controls,
            text="ACTIVE DECK (0)",
            font=Theme.scaled_font(12, "bold"),
            bootstyle="success",
        )
        self.lbl_deck_title.pack(side="left", padx=Theme.scaled_val(5))

        tb.Button(
            deck_controls,
            text="Auto-Lands",
            bootstyle="warning",
            command=self._apply_auto_lands,
        ).pack(side="left", padx=Theme.scaled_val(10))

        self.basics_frame = tb.Frame(deck_controls)
        self.basics_frame.pack(side="right")
        self.basic_buttons = {}
        for sym, name, style in [
            ("W", "Plains", "light"),
            ("U", "Island", "info"),
            ("B", "Swamp", "dark"),
            ("R", "Mountain", "danger"),
            ("G", "Forest", "success"),
        ]:
            btn = tb.Button(
                self.basics_frame,
                text=f"{sym}: 0",
                bootstyle=style,
                width=5,
                padding=Theme.scaled_val(3),
            )
            btn.bind("<ButtonRelease-1>", lambda e, n=name: self._add_basic(n))
            btn.bind("<Button-3>", lambda e, n=name: self._remove_basic(n))
            btn.pack(side="left", padx=1)
            self.basic_buttons[name] = btn

        self.deck_manager = DynamicTreeviewManager(
            self.right_pane,
            view_id="sealed_deck_table",
            configuration=self.configuration,
            on_update_callback=self._refresh_data,
        )
        self.deck_manager.pack(fill="both", expand=True)

        # HUD Analytics
        self.hud_frame = tb.Labelframe(
            self.right_pane, text=" DECK ANALYTICS ", padding=Theme.scaled_val(10)
        )
        self.hud_frame.pack(fill="x", side="bottom", pady=Theme.scaled_val((10, 0)))
        self.hud_frame.columnconfigure(0, weight=1)
        self.hud_frame.columnconfigure(1, weight=1)
        self.hud_frame.columnconfigure(2, weight=1)

        comp_frame = tb.Frame(self.hud_frame)
        comp_frame.grid(row=0, column=0, sticky="nw")
        tb.Label(
            comp_frame,
            text="COMPOSITION",
            font=Theme.scaled_font(10, "bold"),
            bootstyle="primary",
        ).pack(anchor="w")
        self.lbl_comp_stats = tb.Label(
            comp_frame,
            text="Creatures: 0\nSpells: 0\nLands: 0",
            font=Theme.scaled_font(9),
        )
        self.lbl_comp_stats.pack(anchor="w", pady=Theme.scaled_val(5))

        curve_frame = tb.Frame(self.hud_frame)
        curve_frame.grid(row=0, column=1, sticky="nsew")
        tb.Label(
            curve_frame,
            text="MANA CURVE",
            font=Theme.scaled_font(10, "bold"),
            bootstyle="primary",
        ).pack(anchor="w")
        self.curve_plot = ManaCurvePlot(
            curve_frame,
            ideal_distribution=self.configuration.card_logic.deck_mid.distribution,
        )
        self.curve_plot.pack(fill="both", expand=True)

        color_frame = tb.Frame(self.hud_frame)
        color_frame.grid(row=0, column=2, sticky="nsew")
        tb.Label(
            color_frame,
            text="BALANCE",
            font=Theme.scaled_font(10, "bold"),
            bootstyle="primary",
        ).pack(anchor="w")
        self.type_chart = TypePieChart(color_frame)
        self.type_chart.pack(fill="both", expand=True)

        self._bind_dnd(self.pool_manager.tree, is_pool=True)
        self._bind_dnd(self.deck_manager.tree, is_pool=False)

    def _on_close(self):
        """Save session state when closing the studio."""
        self.session.save_session()
        self.destroy()

    def _create_new_tab(self):
        name = simpledialog.askstring(
            "New Deck", "Enter a name for the new deck variant:", parent=self
        )
        if name:
            self.session.create_variant(name)
            self._refresh_tabs()

    def _rename_tab(self):
        if self.session.active_variant_name:
            new_name = simpledialog.askstring(
                "Rename Deck",
                "Enter new name:",
                initialvalue=self.session.active_variant_name,
                parent=self,
            )
            if new_name and self.session.rename_variant(
                self.session.active_variant_name, new_name
            ):
                self._refresh_tabs()

    def _delete_tab(self):
        if len(self.session.variants) > 1:
            if messagebox.askyesno(
                "Delete",
                f"Are you sure you want to delete '{self.session.active_variant_name}'?",
                parent=self,
            ):
                self.session.delete_variant(self.session.active_variant_name)
                self._refresh_tabs()
        else:
            messagebox.showwarning(
                "Cannot Delete", "You must have at least one deck variant.", parent=self
            )

    def _refresh_tabs(self):
        for tab in self.notebook.tabs():
            self.notebook.forget(tab)

        for variant_name in self.session.variants.keys():
            f = tb.Frame(self.notebook)
            self.notebook.add(f, text=f" {variant_name} ")
            if variant_name == self.session.active_variant_name:
                self.notebook.select(f)

    def _on_tab_changed(self, event):
        try:
            current_tab_idx = self.notebook.index(self.notebook.select())
            tab_name = self.notebook.tab(current_tab_idx, "text").strip()
            if tab_name in self.session.variants:
                self.session.active_variant_name = tab_name
                self._refresh_data()
        except:
            pass

    def _on_auto_generate(self):
        self.lbl_deck_title.config(text="GENERATING SHELLS...", bootstyle="warning")
        self.update_idletasks()

        tier_data = self.app_context.orchestrator.scanner.retrieve_tier_data()
        generate_sealed_shells(self.session, self.metrics, tier_data)

        self._refresh_tabs()
        self._refresh_data()

    def _refresh_data(self):
        main_deck, sideboard = self.session.get_active_deck_lists()

        pool_count = sum(c.get("count", 1) for c in sideboard)
        deck_count = sum(c.get("count", 1) for c in main_deck)

        self.lbl_pool_title.config(text=f"MASTER POOL ({pool_count})")
        deck_style = "success" if deck_count == 40 else "warning"
        self.lbl_deck_title.config(
            text=f"ACTIVE DECK ({deck_count})", bootstyle=deck_style
        )

        show_c, show_s, show_l = (
            self.filter_vars["creatures"].get(),
            self.filter_vars["spells"].get(),
            self.filter_vars["lands"].get(),
        )
        filtered_sb = []
        for c in sideboard:
            t = c.get("types", [])
            if "Creature" in t and show_c:
                filtered_sb.append(c)
            elif "Land" in t and show_l:
                filtered_sb.append(c)
            elif "Creature" not in t and "Land" not in t and show_s:
                filtered_sb.append(c)

        self._populate_tree(self.pool_manager, filtered_sb, is_pool=True)
        self._populate_tree(self.deck_manager, main_deck, is_pool=False)

        self._update_hud(main_deck)
        self._update_basics_toolbar(main_deck)

    def _populate_tree(self, manager, card_list, is_pool=False):
        tree = manager.tree
        for item in tree.get_children():
            tree.delete(item)

        card_list.sort(key=lambda x: (x.get("cmc", 0), x.get("name", "")))

        from src.card_logic import format_win_rate, row_color_tag, format_types_for_ui

        active_filter = "All Decks"

        for idx, card in enumerate(card_list):
            row_values = []
            for field in manager.active_fields:
                if field == "name":
                    row_values.append(card.get("name", "Unknown"))
                elif field == "count":
                    row_values.append(str(card.get("count", 1)))
                elif field == "cmc":
                    row_values.append(str(card.get("cmc", 0)))
                elif field == "types":
                    row_values.append(format_types_for_ui(card.get("types", [])))
                elif field == "colors":
                    row_values.append("".join(card.get("colors", [])))
                elif field == "tags":
                    raw_tags = card.get("tags", [])
                    row_values.append(
                        " ".join(
                            [
                                constants.TAG_VISUALS.get(t, t).split(" ")[0]
                                for t in raw_tags
                            ]
                        )
                        if raw_tags
                        else "-"
                    )
                else:
                    stats = card.get("deck_colors", {}).get(active_filter, {})
                    val = stats.get(field, 0.0)
                    row_values.append(
                        format_win_rate(
                            val,
                            active_filter,
                            field,
                            self.metrics,
                            self.configuration.settings.result_format,
                        )
                    )

            tag = (
                row_color_tag(card.get("mana_cost", ""))
                if self.configuration.settings.card_colors_enabled
                else ("bw_odd" if idx % 2 == 0 else "bw_even")
            )
            tree.insert(
                "",
                "end",
                iid=str(idx),
                text=card.get("name", ""),
                values=row_values,
                tags=(tag,),
            )

        if hasattr(tree, "reapply_sort"):
            tree.reapply_sort()

    def _update_hud(self, main_deck):
        metrics = get_deck_metrics(main_deck)
        self.lbl_comp_stats.config(
            text=f"Creatures: {metrics.creature_count}\nSpells: {metrics.noncreature_count}\nLands: {metrics.total_cards - metrics.creature_count - metrics.noncreature_count}\nAvg CMC: {metrics.cmc_average:.2f}"
        )
        self.curve_plot.update_curve(metrics.distribution_all)

        type_counts = {
            "Creature": metrics.creature_count,
            "Instant/Sorcery": 0,
            "Artifact/Enchantment": 0,
            "Land": 0,
        }
        for c in main_deck:
            t, count = c.get("types", []), c.get("count", 1)
            if "Instant" in t or "Sorcery" in t:
                type_counts["Instant/Sorcery"] += count
            elif "Artifact" in t or "Enchantment" in t:
                type_counts["Artifact/Enchantment"] += count
            elif "Land" in t:
                type_counts["Land"] += count
        self.type_chart.update_counts(type_counts)

    def _update_basics_toolbar(self, main_deck):
        counts = {
            n: 0
            for _, n, _ in [
                ("W", "Plains", ""),
                ("U", "Island", ""),
                ("B", "Swamp", ""),
                ("R", "Mountain", ""),
                ("G", "Forest", ""),
            ]
        }
        for c in main_deck:
            if c["name"] in counts:
                counts[c["name"]] += c.get("count", 1)

        symbol_map = {
            "Plains": "W",
            "Island": "U",
            "Swamp": "B",
            "Mountain": "R",
            "Forest": "G",
        }
        for name, btn in self.basic_buttons.items():
            btn.configure(text=f"{symbol_map[name]}: {counts[name]}")

    def _bind_dnd(self, tree, is_pool=True):
        tree._dnd_bound = True
        tree.bind(
            "<ButtonPress-1>", lambda e: self._on_drag_start(e, tree, is_pool), add="+"
        )
        tree.bind("<B1-Motion>", lambda e: self._on_drag_motion(e, tree), add="+")
        tree.bind(
            "<ButtonRelease-1>",
            lambda e: self._on_drag_release(e, tree, is_pool),
            add="+",
        )

        # Right click to show tooltip safely
        tree.bind(
            "<Button-3>", lambda e: self._on_context_menu(e, tree, is_pool), add="+"
        )
        tree.bind(
            "<Control-Button-1>",
            lambda e: self._on_context_menu(e, tree, is_pool),
            add="+",
        )

    def _on_drag_start(self, event, tree, is_pool):
        self._drag_data = None
        row_id = tree.identify_row(event.y)
        if not row_id:
            return
        tree.selection_set(row_id)
        card_name = tree.item(row_id).get("text")
        if card_name:
            self._drag_data = {
                "name": card_name,
                "x": event.x_root,
                "y": event.y_root,
                "is_pool": is_pool,
            }

    def _on_drag_motion(self, event, tree):
        if getattr(self, "_drag_data", None):
            tree.configure(cursor="hand2")

    def _on_drag_release(self, event, tree, is_pool):
        tree.configure(cursor="")
        if not getattr(self, "_drag_data", None):
            return

        dx, dy = abs(event.x_root - self._drag_data["x"]), abs(
            event.y_root - self._drag_data["y"]
        )
        card_name = self._drag_data["name"]

        if dx >= 5 or dy >= 5:
            target_widget = self.deck_manager if is_pool else self.pool_manager
            rx, ry = target_widget.winfo_rootx(), target_widget.winfo_rooty()
            rw, rh = target_widget.winfo_width(), target_widget.winfo_height()
            if rx <= event.x_root <= rx + rw and ry <= event.y_root <= ry + rh:
                if is_pool:
                    self.session.move_to_main(card_name)
                else:
                    self.session.move_to_sideboard(card_name)
                self._refresh_data()
        else:
            if is_pool:
                self.session.move_to_main(card_name)
            else:
                self.session.move_to_sideboard(card_name)
            self._refresh_data()

        self._drag_data = None

    def _on_context_menu(self, event, tree, is_pool):
        region = tree.identify_region(event.x, event.y)
        if region == "heading":
            return
        row_id = tree.identify_row(event.y)
        if not row_id:
            return

        tree.selection_set(row_id)
        card_name = tree.item(row_id).get("text")

        if card_name:
            # Find the card data
            card = next(
                (c for c in self.session.master_pool if c.get("name") == card_name),
                None,
            )
            if not card and card_name in constants.BASIC_LANDS:
                card = {"name": card_name, "cmc": 0, "types": ["Land", "Basic"]}

            if card:
                CardToolTip.create(
                    tree,
                    card,
                    self.configuration.features.images_enabled,
                    constants.UI_SIZE_DICT.get(
                        self.configuration.settings.ui_size, 1.0
                    ),
                )

    def _add_basic(self, name):
        self.session.move_to_main(name)
        self._refresh_data()

    def _remove_basic(self, name):
        self.session.move_to_sideboard(name)
        self._refresh_data()

    def _apply_auto_lands(self):
        from src.card_logic import calculate_dynamic_mana_base, get_strict_colors

        main_deck, _ = self.session.get_active_deck_lists()

        for c in main_deck:
            if c["name"] in constants.BASIC_LANDS:
                self.session.move_to_sideboard(c["name"], c.get("count", 1))

        main_deck, _ = self.session.get_active_deck_lists()
        spells = [c for c in main_deck if "Land" not in c.get("types", [])]
        non_basic_lands = [c for c in main_deck if "Land" in c.get("types", [])]

        if not spells:
            return

        colors = get_strict_colors(spells) or ["W", "U", "B", "R", "G"]
        needed = max(0, 40 - len(spells) - len(non_basic_lands))

        basics_to_add = calculate_dynamic_mana_base(
            spells, non_basic_lands, colors, forced_count=needed
        )
        for b in basics_to_add:
            self.session.move_to_main(b["name"], 1)

        self._refresh_data()

    def _export_active_deck(self):
        main_deck, sideboard = self.session.get_active_deck_lists()
        export_text = copy_deck(main_deck, sideboard)
        self.clipboard_clear()
        self.clipboard_append(export_text)
        messagebox.showinfo(
            "Export Successful", "Deck copied to clipboard in MTGA format!", parent=self
        )

    def _export_to_sealeddeck_tech(self):
        """Automatically builds the payload, calls the Sealeddeck.tech API, and opens the returned URL."""
        main_deck, sideboard = self.session.get_active_deck_lists()
        mtga_payload = copy_deck(main_deck, sideboard)

        self.lbl_deck_title.config(text="EXPORTING TO BROWSER...", bootstyle="warning")
        self.update_idletasks()

        import threading

        def _api_call():
            try:
                response = requests.post(
                    "https://sealeddeck.tech/api/pools",
                    json={"pool": mtga_payload},
                    timeout=10,
                )
                if response.status_code == 200:
                    data = response.json()
                    url = data.get("url")
                    if url:
                        open_file(url)
                    else:
                        raise ValueError("No URL returned from API")
                else:
                    raise Exception(f"HTTP {response.status_code}")
            except Exception as e:

                def _err():
                    self.clipboard_clear()
                    self.clipboard_append(mtga_payload)
                    messagebox.showwarning(
                        "API Error",
                        f"Could not reach Sealeddeck.tech automatically.\n\nYour deck has been copied to the clipboard. You can paste it manually at sealeddeck.tech.",
                        parent=self,
                    )

                self.after(0, _err)
            finally:
                self.after(0, self._refresh_data)  # Restores the label

        threading.Thread(target=_api_call, daemon=True).start()

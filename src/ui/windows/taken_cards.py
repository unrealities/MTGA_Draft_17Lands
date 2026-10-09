"""
src/ui/windows/taken_cards.py
Professional Card Pool Viewer.
Supports both List View (Table) and Visual View (Mana Curve Stacks).
"""

import tkinter
from tkinter import ttk
from typing import List, Dict, Any

from src import constants
from src.card_logic import stack_cards, copy_deck, row_color_tag
from src.ui.styles import Theme
from src.ui.components import (
    DynamicTreeviewManager,
    CardToolTip,
    ScrolledFrame,
    CardPile,
)
from src.card_logic import format_win_rate


class TakenCardsPanel(ttk.Frame):
    def __init__(self, parent, draft_manager, configuration):
        super().__init__(parent)
        self.draft = draft_manager
        self.configuration = configuration

        self.current_display_list = []
        self.view_mode = "list"  # "list" or "visual"
        self.active_color = "All Decks"

        # Independent color-pair filter for this tab (separate from the
        # app-wide Deck Filter, which also drives the Live Pack advisor).
        self.pool_filter_key = constants.FILTER_OPTION_AUTO
        self.pool_filter_map = {}
        self.pool_filter_var = tkinter.StringVar(value=constants.FILTER_OPTION_AUTO)

        # UI State for Checkbuttons
        self.vars = {}

        self._build_ui()

    @property
    def table(self) -> ttk.Treeview:
        return self.table_manager.tree if hasattr(self, "table_manager") else None

    def refresh(self):
        self._update_color_filter_options()

        raw_pool = self.draft.retrieve_taken_cards()
        if not raw_pool:
            self.current_display_list = []  # Ensure it's an empty list, not None
            self.active_color = "All Decks"
        else:
            from src.card_logic import filter_options

            metrics = self.draft.retrieve_set_metrics()
            colors = filter_options(
                raw_pool,
                self.pool_filter_key,
                metrics,
                self.configuration,
            )
            self.active_color = colors[0] if colors else "All Decks"

            # 2. Filter
            active_types = []
            if self.vars["creature"].get():
                active_types.append(constants.CARD_TYPE_CREATURE)
            if self.vars["land"].get():
                active_types.append(constants.CARD_TYPE_LAND)
            if self.vars["spell"].get():
                active_types.extend(
                    [constants.CARD_TYPE_INSTANT, constants.CARD_TYPE_SORCERY]
                )
            if self.vars["other"].get():
                active_types.extend(
                    [
                        constants.CARD_TYPE_ARTIFACT,
                        constants.CARD_TYPE_ENCHANTMENT,
                        constants.CARD_TYPE_PLANESWALKER,
                    ]
                )

            filtered = []
            for c in raw_pool:
                types = c.get(constants.DATA_FIELD_TYPES, [])

                if not types and self.vars["other"].get():
                    filtered.append(c)
                    continue

                # Standard filtering
                if any(t in types for t in active_types):
                    filtered.append(c)

            self.current_display_list = stack_cards(filtered)

        self._update_auto_detect_label()

        (
            self._update_table_view()
            if self.view_mode == "list"
            else self._render_visual_view()
        )

    def _build_ui(self):
        # --- Control Bar ---
        self.filter_frame = ttk.Frame(
            self, style="Card.TFrame", padding=Theme.scaled_val(5)
        )
        self.filter_frame.pack(fill="x", pady=Theme.scaled_val((0, 5)))

        type_grp = ttk.Frame(self.filter_frame, style="Card.TFrame")
        type_grp.pack(side="left", padx=Theme.scaled_val(5))

        self.lbl_filter = ttk.Label(
            type_grp,
            text="FILTER:",
            font=Theme.scaled_font(8, "bold"),
            bootstyle="primary",
        )
        self.lbl_filter.pack(side="left", padx=Theme.scaled_val(5))
        self.bind_all("<<ThemeChanged>>", self._on_theme_change, add="+")

        self.vars = {}
        for lbl, key in [
            ("Creatures", "creature"),
            ("Lands", "land"),
            ("Spells", "spell"),
            ("Other", "other"),
        ]:
            var = tkinter.IntVar(value=1)
            self.vars[key] = var
            ttk.Checkbutton(
                type_grp, text=lbl, variable=var, command=self.refresh
            ).pack(side="left", padx=Theme.scaled_val(3))

        # Color-pair stats filter (independent of the app-wide Deck Filter)
        color_grp = ttk.Frame(self.filter_frame, style="Card.TFrame")
        color_grp.pack(side="left", padx=Theme.scaled_val(10))

        ttk.Label(
            color_grp,
            text="COLORS:",
            font=Theme.scaled_font(8, "bold"),
            bootstyle="primary",
        ).pack(side="left", padx=Theme.scaled_val(5))

        self.om_pool_filter = ttk.OptionMenu(
            color_grp,
            self.pool_filter_var,
            constants.FILTER_OPTION_AUTO,
            style="TMenubutton",
        )
        self.om_pool_filter.pack(side="left")

        self.lbl_pool_auto_detect = ttk.Label(
            color_grp,
            text="",
            font=Theme.scaled_font(9, "italic"),
            bootstyle="info",
        )
        self.lbl_pool_auto_detect.pack(side="left", padx=Theme.scaled_val(5))

        # View Toggle & Export
        btn_frame = ttk.Frame(self.filter_frame, style="Card.TFrame")
        btn_frame.pack(side="right")

        self.btn_view = ttk.Button(
            btn_frame,
            text="Switch to Visual View",
            command=self._toggle_view,
            bootstyle="info-outline",
        )
        self.btn_view.pack(side="left", padx=Theme.scaled_val(5))

        self.btn_export = ttk.Button(
            btn_frame, text="Export Pool", command=self._copy_to_clipboard
        )
        self.btn_export.pack(side="left", padx=Theme.scaled_val(5))

        # --- Content Container ---
        self.content_area = ttk.Frame(self)
        self.content_area.pack(fill="both", expand=True)

        # 1. Table View (Default)
        self.table_manager = DynamicTreeviewManager(
            self.content_area,
            view_id="taken_table",
            configuration=self.configuration,
            on_update_callback=self._update_table_view,
        )
        self.table_manager.pack(fill="both", expand=True)

        # 2. Visual View (Hidden initially)
        self.visual_scroller = ScrolledFrame(self.content_area)
        # We don't pack it yet

    def _on_theme_change(self, event=None):
        pass

    def _update_color_filter_options(self):
        """Populates the tab-local color-pair dropdown from the loaded dataset's
        win rates. Kept independent of the app-wide Deck Filter."""
        try:
            rate_map = self.draft.retrieve_color_win_rate(
                self.configuration.settings.filter_format
            )
        except Exception:
            rate_map = {}

        if not rate_map:
            return

        self.pool_filter_map = rate_map
        menu = self.om_pool_filter["menu"]
        menu.delete(0, "end")
        for label, key in rate_map.items():
            menu.add_command(
                label=label,
                command=lambda l=label: self._on_pool_filter_select(l),
            )

        target_label = next(
            (label for label, key in rate_map.items() if key == self.pool_filter_key),
            None,
        )
        if target_label is None:
            self.pool_filter_key = constants.FILTER_OPTION_AUTO
            target_label = next(
                (
                    label
                    for label, key in rate_map.items()
                    if key == constants.FILTER_OPTION_AUTO
                ),
                constants.FILTER_OPTION_AUTO,
            )
        self.pool_filter_var.set(target_label)

    def _on_pool_filter_select(self, label):
        self.pool_filter_key = self.pool_filter_map.get(
            label, constants.FILTER_OPTION_AUTO
        )
        self.pool_filter_var.set(label)
        self.refresh()

    def _update_auto_detect_label(self):
        if self.pool_filter_key != constants.FILTER_OPTION_AUTO:
            self.lbl_pool_auto_detect.config(text="")
            return

        if self.active_color == constants.FILTER_OPTION_ALL_DECKS:
            self.lbl_pool_auto_detect.config(text="(Auto: Detecting...)")
        else:
            display_name = (
                constants.COLOR_NAMES_DICT.get(self.active_color, self.active_color)
                if self.configuration.settings.filter_format
                == constants.DECK_FILTER_FORMAT_NAMES
                else self.active_color
            )
            self.lbl_pool_auto_detect.config(text=f"(Auto: {display_name})")

    def _toggle_view(self):
        if self.view_mode == "list":
            self.view_mode = "visual"
            self.btn_view.config(text="Switch to List View")
            self.table_manager.pack_forget()
            self.visual_scroller.pack(fill="both", expand=True)
            self._render_visual_view()
        else:
            self.view_mode = "list"
            self.btn_view.config(text="Switch to Visual View")
            self.visual_scroller.pack_forget()
            self.table_manager.pack(fill="both", expand=True)
            self._update_table_view()

    def _update_table_view(self):
        t = self.table
        if t is None:
            return

        metrics = self.draft.retrieve_set_metrics()
        tier_data = self.draft.retrieve_tier_data()

        if not getattr(t, "_selection_bound", False):
            t.bind("<ButtonRelease-1>", self._on_selection, add="+")
            t._selection_bound = True

        for item in t.get_children():
            t.delete(item)

        for idx, card in enumerate(self.current_display_list):
            row_values = []
            for field in self.table_manager.active_fields:
                if field == "name":
                    row_values.append(card.get("name", "Unknown"))
                elif field == "count":
                    row_values.append(card.get("count", 1))
                elif field == "colors":
                    row_values.append("".join(card.get("colors", [])))
                elif field == "tags":
                    raw_tags = card.get("tags", [])
                    if raw_tags:
                        icons_only = [
                            constants.TAG_VISUALS.get(t, t).split(" ")[0]
                            for t in raw_tags
                        ]
                        row_values.append(" ".join(icons_only))
                    else:
                        row_values.append("-")
                elif "TIER" in field:
                    if tier_data and field in tier_data:
                        tier_obj = tier_data[field]
                        raw_name = card.get("name", "")
                        if raw_name in tier_obj.ratings:
                            row_values.append(tier_obj.ratings[raw_name].rating)
                        else:
                            row_values.append("NA")
                    else:
                        row_values.append("NA")

                else:
                    val = (
                        card.get("deck_colors", {})
                        .get(self.active_color, {})
                        .get(field, 0.0)
                    )
                    row_values.append(
                        format_win_rate(
                            val,
                            self.active_color,
                            field,
                            metrics,
                            self.configuration.settings.result_format,
                        )
                    )

            tag = "bw_odd" if idx % 2 == 0 else "bw_even"
            if int(self.configuration.settings.card_colors_enabled):
                tag = row_color_tag(card.get(constants.DATA_FIELD_MANA_COST, ""))

            t.insert(
                "", "end", text=card.get("name", ""), values=row_values, tags=(tag,)
            )

        if hasattr(t, "reapply_sort"):
            t.reapply_sort()

    def _render_visual_view(self):
        # Clear existing piles
        for widget in self.visual_scroller.scrollable_frame.winfo_children():
            widget.destroy()

        # Buckets: Lands, 1, 2, 3, 4, 5, 6+
        buckets = {
            "Lands": [],
            "1": [],
            "2": [],
            "3": [],
            "4": [],
            "5": [],
            "6+": [],
            "Unknown": [],  # Bucket for recovered cards with no CMC data
        }

        for card in self.current_display_list:
            if constants.CARD_TYPE_LAND in card.get(constants.DATA_FIELD_TYPES, []):
                buckets["Lands"].append(card)
                continue

            # Handle unknown CMC safely
            try:
                cmc = int(card.get(constants.DATA_FIELD_CMC, 0))
                if cmc == 0 and not card.get(constants.DATA_FIELD_TYPES):
                    buckets["Unknown"].append(card)
                    continue
            except:
                buckets["Unknown"].append(card)
                continue

            if cmc <= 1:
                buckets["1"].append(card)
            elif cmc == 2:
                buckets["2"].append(card)
            elif cmc == 3:
                buckets["3"].append(card)
            elif cmc == 4:
                buckets["4"].append(card)
            elif cmc == 5:
                buckets["5"].append(card)
            else:
                buckets["6+"].append(card)

        # Render Piles
        keys = ["Lands", "1", "2", "3", "4", "5", "6+", "Unknown"]
        for key in keys:
            card_list = buckets.get(key, [])
            if not card_list and key not in ["Lands", "Unknown"]:
                continue  # Skip empty CMC columns to save space
            if not card_list:
                continue

            # Create Column
            pile_frame = ttk.Frame(self.visual_scroller.scrollable_frame)
            pile_frame.pack(
                side="left",
                fill="y",
                padx=Theme.scaled_val(5),
                pady=Theme.scaled_val(5),
                anchor="n",
            )

            # Use the CardPile component
            pile = CardPile(pile_frame, title=f"CMC {key}", app_instance=self)
            pile.pack(fill="both", expand=True)

            # Sort by Color then Name
            card_list.sort(key=lambda x: (x.get("colors", []), x.get("name", "")))

            for card in card_list:
                pile.add_card(card)

    def _copy_to_clipboard(self):
        self.clipboard_clear()
        self.clipboard_append(copy_deck(self.current_display_list, None))

        self.btn_export.config(text="Copied! ✔", bootstyle="success")
        self.after(
            2000,
            lambda: self.btn_export.config(text="Export Pool", bootstyle="primary"),
        )

    def _on_selection(self, event):
        if hasattr(event, "x") and hasattr(event, "y"):
            region = self.table.identify_region(event.x, event.y)
            if region not in ("tree", "cell"):
                return

        sel = self.table.selection()
        if not sel:
            return

        item = self.table.item(sel[0])
        card_name = item.get("text")

        if not card_name:
            item_vals = item["values"]
            try:
                name_idx = self.table_manager.active_fields.index("name")
                card_name = (
                    str(item_vals[name_idx])
                    .replace("⭐ ", "")
                    .replace("[+] ", "")
                    .replace("*", "")
                    .strip()
                )
            except ValueError:
                return

        card = next(
            (c for c in self.current_display_list if c.get("name") == card_name), None
        )
        if card:
            CardToolTip.create(
                self.table,
                card,
                self.configuration.features.images_enabled,
                Theme.current_scale,
            )

"""
src/ui/windows/overlay.py
Compact Overlay Window for in-game drafting.
"""

import tkinter
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from src import constants
from src.card_logic import row_color_tag
from src.ui.styles import Theme
from src.ui.components import DynamicTreeviewManager, CardToolTip
from src.configuration import write_configuration


class CompactOverlay(tb.Toplevel):
    def __init__(self, parent, orchestrator, configuration, on_restore):
        super().__init__(title="Draft Overlay", topmost=True)
        self.orchestrator = orchestrator
        self.configuration = configuration
        self.on_restore = on_restore
        self.current_pack_cards = []

        self.overrideredirect(True)  # Frameless window

        # Load persisted geometry
        geom = getattr(self.configuration.settings, "overlay_geometry", "380x600+50+50")
        self.geometry(geom)
        self.configure(bg=Theme.BG_PRIMARY)

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
        new_w = max(250, self._start_w + (event.x_root - self._start_x))
        new_h = max(200, self._start_h + (event.y_root - self._start_y))
        self.geometry(f"{new_w}x{new_h}")

    def _stop_resize(self, event):
        self._save_geometry()

    def _save_geometry(self):
        """Persists size and coordinates to the config file."""
        self.configuration.settings.overlay_geometry = self.geometry()
        write_configuration(self.configuration)

    def _close_overlay(self):
        """Saves before returning to the main app."""
        self._save_geometry()
        self.on_restore()

    def _build_ui(self):
        # --- HEADER (Draggable) ---
        header = tb.Frame(self, bootstyle="secondary")
        header.pack(fill=X, ipady=5)

        header.bind("<ButtonPress-1>", self._start_move)
        header.bind("<ButtonRelease-1>", self._stop_move)
        header.bind("<B1-Motion>", self._do_move)

        self.btn_scan = tb.Button(
            header,
            text="SCAN P1P1",
            bootstyle="success-outline",
            command=self._manual_scan,
        )

        tb.Button(header, text="⤢", bootstyle="link", command=self._close_overlay).pack(
            side=RIGHT, padx=5
        )

        self.lbl_status = tb.Label(
            header,
            text="Waiting...",
            font=(Theme.FONT_FAMILY, 10, "bold"),
            bootstyle="inverse-secondary",
        )
        self.lbl_status.pack(side=RIGHT, padx=5)

        # --- FOOTER (Resize Grip) ---
        footer = tb.Frame(self, bootstyle="secondary")
        footer.pack(fill=X, side=BOTTOM)

        # Custom visual grip indicator
        grip = tb.Label(
            footer,
            text=" ⇲ ",
            cursor="hand2",
            bootstyle="inverse-secondary",
            font=(Theme.FONT_FAMILY, 12),
        )
        grip.pack(side=RIGHT, padx=2)

        grip.bind("<ButtonPress-1>", self._start_resize)
        grip.bind("<B1-Motion>", self._do_resize)
        grip.bind("<ButtonRelease-1>", self._stop_resize)

        # --- DYNAMIC CARD LIST ---
        self.table_manager = DynamicTreeviewManager(
            self,
            view_id="overlay_table",
            configuration=self.configuration,
            on_update_callback=self._trigger_refresh,
        )
        self.table_manager.pack(fill=BOTH, expand=True, padx=2, pady=2, side=TOP)

        self.tree = self.table_manager.tree
        self.tree.bind("<<TreeviewSelect>>", self._on_card_select)

    def _trigger_refresh(self):
        if hasattr(self.orchestrator, "refresh_callback"):
            self.orchestrator.refresh_callback()

    def _manual_scan(self):
        save_img = self.configuration.settings.save_screenshot_enabled
        data_found = self.orchestrator.scanner.draft_data_search(True, save_img)
        if data_found and hasattr(self.orchestrator, "refresh_callback"):
            self.orchestrator.refresh_callback()

    def update_data(
        self, pack_cards, colors, metrics, tier_data, current_pick, recommendations=None
    ):
        self.current_pack_cards = pack_cards or []
        pk, pi = self.orchestrator.scanner.retrieve_current_pack_and_pick()
        self.lbl_status.config(text=f"P{pk} / P{pi}")

        if pk <= 1 and pi <= 1:
            self.btn_scan.pack(side=LEFT, padx=5, before=self.lbl_status)
        else:
            self.btn_scan.pack_forget()

        self.tree = self.table_manager.tree
        self.tree.bind("<<TreeviewSelect>>", self._on_card_select)

        for item in self.tree.get_children():
            self.tree.delete(item)

        if not pack_cards:
            return

        rec_map = {r.card_name: r for r in (recommendations or [])}
        active_filter = colors[0] if colors else "All Decks"
        processed_rows = []

        for card in pack_cards:
            name = card.get(constants.DATA_FIELD_NAME, "Unknown")
            stats = card.get("deck_colors", {}).get(active_filter, {})
            rec = rec_map.get(name)

            row_tag = "bw_odd" if len(processed_rows) % 2 == 0 else "bw_even"
            if self.configuration.settings.card_colors_enabled:
                row_tag = row_color_tag(card.get(constants.DATA_FIELD_MANA_COST, ""))

            display_name = name
            if rec:
                if rec.is_elite:
                    display_name = f"⭐ {name}"
                    row_tag = (
                        "elite_bomb"
                        if not self.configuration.settings.card_colors_enabled
                        else row_tag
                    )
                elif rec.archetype_fit == "High":
                    display_name = f"[+] {name}"
                    row_tag = (
                        "high_fit"
                        if not self.configuration.settings.card_colors_enabled
                        else row_tag
                    )

            row_values = []
            for field in self.table_manager.active_fields:
                if field == "name":
                    short_name = (
                        display_name
                        if len(display_name) <= 22
                        else display_name[:20] + ".."
                    )
                    row_values.append(short_name)
                elif field == "value":
                    if rec:
                        row_values.append(f"{rec.contextual_score:.0f}")
                    else:
                        val = stats.get("gihwr", 0.0)
                        row_values.append(f"{val:.0f}" if val != 0.0 else "-")
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
                elif field == "count":
                    row_values.append(str(card.get("count", "-")))
                elif field == "wheel":
                    if rec and rec.wheel_chance > 0:
                        row_values.append(f"{rec.wheel_chance:.0f}%")
                    else:
                        row_values.append("-")
                elif "TIER" in field:
                    if tier_data and field in tier_data:
                        tier_obj = tier_data[field]
                        raw_name = card.get(constants.DATA_FIELD_NAME, "")
                        if raw_name in tier_obj.ratings:
                            row_values.append(tier_obj.ratings[raw_name].rating)
                        else:
                            row_values.append("NA")
                    else:
                        row_values.append("NA")
                else:
                    val = stats.get(field, 0.0)
                    if val == 0.0:
                        row_values.append("-")
                    else:
                        row_values.append(
                            f"{val:.1f}"
                            if field
                            in ["gihwr", "ohwr", "gpwr", "gnswr", "gdwr", "iwd"]
                            else str(val)
                        )

            sort_val = rec.contextual_score if rec else stats.get("gihwr", 0.0)
            processed_rows.append(
                {"vals": row_values, "tag": row_tag, "sort_key": sort_val}
            )

        processed_rows.sort(key=lambda x: x["sort_key"], reverse=True)
        for row in processed_rows:
            self.tree.insert("", "end", values=row["vals"], tags=(row["tag"],))

    def _on_card_select(self, event):
        selection = self.tree.selection()
        if not selection:
            return

        item_vals = self.tree.item(selection[0])["values"]
        card_name = (
            str(item_vals[0])
            .replace("⭐ ", "")
            .replace("[+] ", "")
            .replace("..", "")
            .strip()
        )

        found = next(
            (
                c
                for c in self.current_pack_cards
                if card_name in c.get(constants.DATA_FIELD_NAME, "")
            ),
            None,
        )

        if found:
            CardToolTip(
                self.tree,
                found,
                self.configuration.features.images_enabled,
                constants.UI_SIZE_DICT.get(self.configuration.settings.ui_size, 1.0),
            )

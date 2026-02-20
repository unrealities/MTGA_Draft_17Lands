"""
src/ui/windows/overlay.py
Compact Overlay Window for in-game drafting.
"""

import tkinter
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from src import constants
from src.card_logic import field_process_sort, row_color_tag, CardResult
from src.ui.styles import Theme


class CompactOverlay(tb.Toplevel):
    def __init__(self, parent, orchestrator, configuration, on_restore):
        super().__init__(title="Draft Overlay", topmost=True)
        self.orchestrator = orchestrator
        self.configuration = configuration
        self.on_restore = on_restore

        # Window Setup
        self.overrideredirect(True)  # Remove OS Title Bar
        self.geometry("250x600+50+50")  # Default size, user should drag/resize
        self.configure(bg=Theme.BG_PRIMARY)

        # Allow moving the window by dragging the background
        self._bind_drag_events()

        self._build_ui()

    def _bind_drag_events(self):
        self.bind("<ButtonPress-1>", self._start_move)
        self.bind("<ButtonRelease-1>", self._stop_move)
        self.bind("<B1-Motion>", self._do_move)

    def _start_move(self, event):
        self.x = event.x
        self.y = event.y

    def _stop_move(self, event):
        self.x = None
        self.y = None

    def _do_move(self, event):
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.winfo_x() + deltax
        y = self.winfo_y() + deltay
        self.geometry(f"+{x}+{y}")

    def _build_ui(self):
        # --- HEADER (Draggable) ---
        header = tb.Frame(self, bootstyle="secondary")
        header.pack(fill=X, ipady=5)

        # Scan / Refresh Button (Prominent for P1P1)
        self.btn_scan = tb.Button(
            header,
            text="SCAN P1P1",
            bootstyle="success-outline",
            command=self._manual_scan,
        )
        self.btn_scan.pack(side=LEFT, padx=5)

        # Restore Button (Return to Main App)
        tb.Button(header, text="⤢", bootstyle="link", command=self.on_restore).pack(
            side=RIGHT, padx=5
        )

        # Status Label (Pack 1 Pick 1)
        self.lbl_status = tb.Label(
            header,
            text="Waiting...",
            font=("Segoe UI", 9, "bold"),
            bootstyle="inverse-secondary",
        )
        self.lbl_status.pack(side=RIGHT, padx=5)

        # --- CARD LIST ---
        # A simplified treeview showing only Name, GIHWR, and ALSA
        cols = ["Card", "GIHWR", "ALSA"]
        self.tree = tb.Treeview(
            self,
            columns=cols,
            show="headings",
            bootstyle="primary",
            selectmode="browse",
            height=20,
        )

        self.tree.column("Card", width=120, anchor=W)
        self.tree.column("GIHWR", width=50, anchor=CENTER)
        self.tree.column("ALSA", width=40, anchor=CENTER)

        self.tree.heading("Card", text="Card")
        self.tree.heading("GIHWR", text="GIH%")
        self.tree.heading("ALSA", text="ALSA")

        self.tree.pack(fill=BOTH, expand=True, padx=2, pady=2)

        # Tags for colors
        self.tree.tag_configure(
            "white_card", background="#FFF8E1", foreground="black"
        )  # Light Yellow/White
        self.tree.tag_configure(
            "blue_card", background="#E3F2FD", foreground="black"
        )  # Light Blue
        self.tree.tag_configure(
            "black_card", background="#E0E0E0", foreground="black"
        )  # Light Grey
        self.tree.tag_configure(
            "red_card", background="#FFEBEE", foreground="black"
        )  # Light Red
        self.tree.tag_configure(
            "green_card", background="#E8F5E9", foreground="black"
        )  # Light Green
        self.tree.tag_configure(
            "gold_card", background="#FFF3E0", foreground="black"
        )  # Light Orange
        self.tree.tag_configure(
            "colorless_card", background="#F5F5F5", foreground="black"
        )

    def _manual_scan(self):
        """
        Manually triggers a P1P1 scan via the Orchestrator.
        If data is found, explicitly triggers the full UI refresh callback to
        ensure this overlay window gets updated with the new data.
        """
        save_img = self.configuration.settings.save_screenshot_enabled
        data_found = self.orchestrator.scanner.draft_data_search(True, save_img)

    def update_data(self, pack_cards, colors, metrics, tier_data, current_pick):
        # Update Header
        pk, pi = self.orchestrator.scanner.retrieve_current_pack_and_pick()
        self.lbl_status.config(text=f"P{pk} / P{pi}")

        # Clear Table
        for item in self.tree.get_children():
            self.tree.delete(item)

        if not pack_cards:
            return

        # Process Data (Using existing logic)
        processor = CardResult(metrics, tier_data, self.configuration, current_pick)
        # We enforce specific columns for the overlay (Compactness > Customization)
        fields = [
            constants.DATA_FIELD_NAME,
            constants.DATA_FIELD_GIHWR,
            constants.DATA_FIELD_ALSA,
        ]
        results = processor.return_results(pack_cards, colors, fields)

        # Sort by GIHWR (Index 1)
        results.sort(key=lambda x: field_process_sort(x["results"][1]), reverse=True)

        for item in results:
            # Map Row Color
            tag = row_color_tag(item.get(constants.DATA_FIELD_MANA_COST, ""))

            vals = item["results"]
            # Shorten names if too long
            name = vals[0]
            if len(name) > 18:
                name = name[:16] + ".."

            self.tree.insert("", "end", values=(name, vals[1], vals[2]), tags=(tag,))

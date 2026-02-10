"""
src/ui/windows/tier_list.py
Integrated Tier List Management Panel.
Handles API-based imports from 17Lands and manages local tier list history.
"""

import tkinter
from tkinter import ttk, messagebox
import os
from datetime import datetime
from typing import Callable

from src.tier_list import TierList, TIER_FOLDER, TIER_FILE_PREFIX, TIER_URL_17LANDS
from src.ui.styles import Theme
from src.ui.components import ModernTreeview


class TierListWindow(ttk.Frame):
    def __init__(self, parent, on_update_callback: Callable):
        super().__init__(parent)
        self.on_update_callback = on_update_callback
        self.vars = {}

        self._build_ui()
        self.refresh()

    def refresh(self):
        """Public refresh method to reload the local history table."""
        self._update_history_table()

    def _build_ui(self):
        container = ttk.Frame(self, padding=10)
        container.pack(fill="both", expand=True)

        # --- 1. History Table ---
        ttk.Label(container, text="IMPORTED TIER LISTS", style="Muted.TLabel").pack(
            anchor="w", pady=(0, 5)
        )

        cols = ["Set", "Label", "Date"]
        headers = {
            "Set": {"width": 80, "anchor": tkinter.W},
            "Label": {"width": 200, "anchor": tkinter.W},
            "Date": {"width": 150, "anchor": tkinter.CENTER},
        }
        self.table = ModernTreeview(
            container, columns=cols, headers_config=headers, height=10
        )
        self.table.pack(fill="both", expand=True, pady=(0, 15))

        # --- 2. Import Form ---
        form_frame = ttk.Frame(container, style="Card.TFrame", padding=15)
        form_frame.pack(fill="x")

        ttk.Label(
            form_frame,
            text="IMPORT NEW TIER LIST",
            style="SubHeader.TLabel",
            background=Theme.BG_SECONDARY,
        ).pack(anchor="w", pady=(0, 10))

        # URL Field
        ttk.Label(
            form_frame,
            text="17LANDS URL:",
            style="Muted.TLabel",
            background=Theme.BG_SECONDARY,
        ).pack(anchor="w")
        self.vars["url"] = tkinter.StringVar()
        self.entry_url = ttk.Entry(form_frame, textvariable=self.vars["url"])
        self.entry_url.pack(fill="x", pady=(2, 10))
        # Default placeholder text for UX
        self.entry_url.insert(0, "https://www.17lands.com/tier_list/...")

        # Label Field
        ttk.Label(
            form_frame,
            text="CUSTOM LABEL (e.g. 'LSV Set Review'):",
            style="Muted.TLabel",
            background=Theme.BG_SECONDARY,
        ).pack(anchor="w")
        self.vars["label"] = tkinter.StringVar()
        self.entry_label = ttk.Entry(form_frame, textvariable=self.vars["label"])
        self.entry_label.pack(fill="x", pady=(2, 15))

        # Action Button
        self.btn_import = ttk.Button(
            form_frame, text="Download & Index Tier List", command=self._start_import
        )
        self.btn_import.pack(fill="x")

        self.vars["status"] = tkinter.StringVar(value="Ready")
        ttk.Label(
            form_frame,
            textvariable=self.vars["status"],
            style="Muted.TLabel",
            background=Theme.BG_SECONDARY,
        ).pack(pady=(5, 0))

    def _update_history_table(self):
        """Clears and repopulates the history table from local disk."""
        for item in self.table.get_children():
            self.table.delete(item)

        files = TierList.retrieve_files()
        # Sort by date descending
        files.sort(key=lambda x: x[2], reverse=True)

        for idx, f in enumerate(files):
            tag = "bw_odd" if idx % 2 == 0 else "bw_even"
            self.table.insert("", "end", values=(f[0], f[1], f[2]), tags=(tag,))

    def _start_import(self):
        """Validates input and invokes the TierList API logic."""
        url = self.vars["url"].get().strip()
        label = self.vars["label"].get().strip()

        if not url.startswith(TIER_URL_17LANDS):
            messagebox.showwarning(
                "Invalid URL",
                f"Please provide a valid 17Lands URL starting with:\n{TIER_URL_17LANDS}",
            )
            return

        if not label or label.startswith(
            "https:"
        ):  # Simple check for pasted URL in label box
            messagebox.showwarning(
                "Missing Label", "Please provide a custom label for this tier list."
            )
            return

        self.btn_import.configure(state="disabled")
        self.vars["status"].set("CONNECTING TO 17LANDS...")
        self.update()

        try:
            new_tier_list = TierList.from_api(url)
            if new_tier_list:
                new_tier_list.meta.label = label
                timestamp = int(datetime.now().timestamp())
                filename = (
                    f"{TIER_FILE_PREFIX}_{new_tier_list.meta.set}_{timestamp}.txt"
                )
                new_tier_list.to_file(os.path.join(TIER_FOLDER, filename))

                self._update_history_table()
                self.vars["url"].set("https://www.17lands.com/tier_list/...")
                self.vars["label"].set("")
                self.vars["status"].set("IMPORT SUCCESSFUL")

                if self.on_update_callback:
                    self.on_update_callback()
            else:
                raise Exception("API returned invalid data.")

        except Exception as e:
            self.vars["status"].set("IMPORT FAILED")
            messagebox.showerror(
                "Import Error", f"Failed to retrieve tier list:\n{str(e)}"
            )
        finally:
            self.btn_import.configure(state="normal")

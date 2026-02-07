"""
src/ui/windows/tier_list.py

This module implements the Tier List download window.
"""

import tkinter
from tkinter import ttk, messagebox
import os
from datetime import datetime
from typing import Callable

from src.tier_list import TierList, TIER_FOLDER, TIER_FILE_PREFIX, TIER_URL_17LANDS
from src.ui.styles import Theme
from src.ui.components import ModernTreeview, identify_safe_coordinates


class TierListWindow(tkinter.Toplevel):
    def __init__(self, parent, on_update_callback: Callable):
        super().__init__(parent)
        self.on_update_callback = on_update_callback

        self.title("Tier Lists")
        self.configure(bg=Theme.BG_PRIMARY)
        self.transient(parent)
        self.resizable(False, True)

        self.vars = {}

        self._build_ui()
        self._update_table()

        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        x, y = identify_safe_coordinates(parent, w, h, 50, 50)
        self.wm_geometry(f"+{x}+{y}")

    def _build_ui(self):
        container = ttk.Frame(self, padding=15)
        container.pack(fill="both", expand=True)

        # List
        cols = ["Set", "Label", "Date", "File"]
        headers = {
            "Set": {"width": 60, "anchor": tkinter.W},
            "Label": {"width": 150, "anchor": tkinter.W},
            "Date": {"width": 120, "anchor": tkinter.CENTER},
            "File": {"width": 150, "anchor": tkinter.W},
        }
        self.table = ModernTreeview(
            container, columns=cols, headers_config=headers, height=8
        )
        self.table.pack(fill="both", expand=True, pady=(0, 15))

        # Form
        form_frame = ttk.Frame(container, style="Card.TFrame", padding=10)
        form_frame.pack(fill="x")

        ttk.Label(form_frame, text="Add New Tier List", style="SubHeader.TLabel").pack(
            anchor="w", pady=(0, 10)
        )

        # URL
        ttk.Label(form_frame, text="17Lands URL:").pack(anchor="w")
        self.vars["url"] = tkinter.StringVar()
        entry_url = ttk.Entry(form_frame, textvariable=self.vars["url"], width=50)
        entry_url.pack(fill="x", pady=(2, 10))
        entry_url.insert(0, "https://www.17lands.com/tier_list/...")

        # Label
        ttk.Label(form_frame, text="Label (e.g. 'Set Review'):").pack(anchor="w")
        self.vars["label"] = tkinter.StringVar()
        entry_label = ttk.Entry(form_frame, textvariable=self.vars["label"], width=50)
        entry_label.pack(fill="x", pady=(2, 15))

        # Button & Status
        self.btn_download = ttk.Button(
            form_frame, text="Download", command=self._download, style="Accent.TButton"
        )
        self.btn_download.pack(fill="x")

        self.vars["status"] = tkinter.StringVar()
        ttk.Label(
            form_frame, textvariable=self.vars["status"], style="Muted.TLabel"
        ).pack(pady=(5, 0))

    def _update_table(self):
        for item in self.table.get_children():
            self.table.delete(item)

        files = TierList.retrieve_files()
        files.sort(key=lambda x: x[2], reverse=True)  # Sort by date

        for idx, row in enumerate(files):
            tag = "bw_odd" if idx % 2 != 0 else "bw_even"
            self.table.insert("", "end", values=row, tags=(tag,))

    def _download(self):
        url = self.vars["url"].get().strip()
        label = self.vars["label"].get().strip()

        if not url.startswith(TIER_URL_17LANDS):
            self.vars["status"].set("Invalid URL")
            return
        if not label:
            self.vars["status"].set("Label required")
            return

        self.btn_download.config(state="disabled")
        self.vars["status"].set("Downloading...")
        self.update()

        try:
            tier_list = TierList.from_api(url)
            if tier_list:
                tier_list.meta.label = label
                filename = f"{TIER_FILE_PREFIX}_{tier_list.meta.set}_{int(datetime.now().timestamp())}.txt"
                tier_list.to_file(os.path.join(TIER_FOLDER, filename))

                self._update_table()
                if self.on_update_callback:
                    self.on_update_callback()

                self.vars["status"].set("Success!")
                self.vars["url"].set("")
                self.vars["label"].set("")
            else:
                self.vars["status"].set("API Error")
        except Exception as e:
            self.vars["status"].set(f"Error: {e}")
        finally:
            self.btn_download.config(state="normal")

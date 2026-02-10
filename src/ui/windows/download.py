"""
src/ui/windows/download.py
Integrated Dataset Manager Panel.
Full restoration: Start/End Dates, Min Games Threshold, and compact high-res Table view.
"""

import tkinter
from tkinter import ttk, messagebox
from datetime import date, datetime
from typing import Callable, Any, Optional, Dict
from dataclasses import dataclass

from src import constants
from src.configuration import Configuration, write_configuration
from src.file_extractor import FileExtractor
from src.utils import retrieve_local_set_list, clean_string
from src.ui.styles import Theme
from src.ui.components import ModernTreeview


@dataclass
class DatasetArgs:
    draft_set: str
    draft: str
    start: str
    end: str
    user_group: str
    game_count: int
    color_ratings: Optional[Dict] = None


class DownloadWindow(ttk.Frame):
    def __init__(self, parent, limited_sets, configuration, on_update_callback):
        super().__init__(parent)
        self.sets_data = limited_sets.data
        self.configuration = configuration
        self.on_update_callback = on_update_callback
        self.vars = {}
        self._build_ui()

    def _build_ui(self):
        container = ttk.Frame(self, padding=10)
        container.pack(fill="both", expand=True)

        # 1. Dataset Table (Restricted height to 6 rows to ensure form visibility)
        cols = ["Set", "Event", "Group", "Start", "End", "Collected", "Games"]
        headers = {
            "Set": {"width": 160},
            "Event": {"width": 100},
            "Group": {"width": 50},
            "Start": {"width": 80},
            "End": {"width": 80},
            "Collected": {"width": 120},
            "Games": {"width": 60},
        }
        self.table = ModernTreeview(
            container, columns=cols, headers_config=headers, height=6
        )
        self.table.pack(fill="both", expand=True, pady=(0, 10))

        # 2. Controls
        form = ttk.Frame(container, style="Card.TFrame", padding=12)
        form.pack(fill="x")
        form.columnconfigure(1, weight=1)
        form.columnconfigure(3, weight=1)

        set_opts = list(self.sets_data.keys())
        self.vars["set"] = tkinter.StringVar(value=set_opts[0])
        ttk.Label(form, text="SET:", background=Theme.BG_SECONDARY).grid(
            row=0, column=0, sticky="e", padx=5
        )
        ttk.OptionMenu(
            form, self.vars["set"], set_opts[0], *set_opts, command=self._on_set_change
        ).grid(row=0, column=1, sticky="ew")

        self.vars["event"] = tkinter.StringVar(value="PremierDraft")
        ttk.Label(form, text="EVENT:", background=Theme.BG_SECONDARY).grid(
            row=0, column=2, sticky="e", padx=5
        )
        self.om_event = ttk.OptionMenu(
            form, self.vars["event"], "PremierDraft", *constants.LIMITED_TYPE_LIST
        ).grid(row=0, column=3, sticky="ew")

        self.vars["group"] = tkinter.StringVar(value="All")
        ttk.Label(form, text="USERS:", background=Theme.BG_SECONDARY).grid(
            row=1, column=0, sticky="e", padx=5
        )
        ttk.OptionMenu(
            form, self.vars["group"], "All", *constants.LIMITED_GROUPS_LIST
        ).grid(row=1, column=1, sticky="ew")

        self.vars["threshold"] = tkinter.StringVar(value="5000")
        ttk.Label(form, text="MIN GAMES:", background=Theme.BG_SECONDARY).grid(
            row=1, column=2, sticky="e", padx=5
        )
        ttk.Entry(form, textvariable=self.vars["threshold"]).grid(
            row=1, column=3, sticky="ew"
        )

        self.vars["start"] = tkinter.StringVar(value="2019-01-01")
        ttk.Label(form, text="START:", background=Theme.BG_SECONDARY).grid(
            row=2, column=0, sticky="e", padx=5
        )
        ttk.Entry(form, textvariable=self.vars["start"]).grid(
            row=2, column=1, sticky="ew"
        )

        self.vars["end"] = tkinter.StringVar(value=str(date.today()))
        ttk.Label(form, text="END:", background=Theme.BG_SECONDARY).grid(
            row=2, column=2, sticky="e", padx=5
        )
        ttk.Entry(form, textvariable=self.vars["end"]).grid(
            row=2, column=3, sticky="ew"
        )

        self.btn_dl = ttk.Button(
            form, text="DOWNLOAD AND INDEX DATASET", command=self._manual_download
        )
        self.btn_dl.grid(row=3, column=0, columnspan=4, pady=(10, 0), sticky="ew")

        self.progress = ttk.Progressbar(container, mode="determinate")
        self.progress.pack(fill="x", pady=5)
        self.vars["status"] = tkinter.StringVar(value="Ready")
        ttk.Label(
            container, textvariable=self.vars["status"], style="Muted.TLabel"
        ).pack()
        self._update_table()

    def check_instance_open(self) -> bool:
        return True

    def enter(self, args: DatasetArgs = None):
        """Called by Notifications to populate the form and trigger a download."""
        if args:
            target_key = next(
                (
                    k
                    for k, v in self.sets_data.items()
                    if v.seventeenlands[0] == args.draft_set
                ),
                None,
            )

            if target_key:
                self.vars["set"].set(target_key)
                s = self.sets_data.get(target_key)
                if s and s.start_date:
                    self.vars["start"].set(s.start_date)

                if hasattr(self, "om_event"):
                    try:
                        menu = self.om_event["menu"]
                        menu.delete(0, "end")
                        for f in s.formats:
                            menu.add_command(
                                label=f, command=lambda v=f: self.vars["event"].set(v)
                            )
                    except:
                        pass

            self.vars["event"].set(args.draft)
            self.vars["group"].set(args.user_group)

            self._start_download(args)

    def _manual_download(self):
        self._start_download()

    def _on_set_change(self, val):
        """Standard UI callback for manual user selection."""
        s = self.sets_data.get(val)
        if s and s.start_date:
            self.vars["start"].set(s.start_date)

        if not s or not hasattr(self, "om_event"):
            return

        try:
            menu = self.om_event["menu"]
            menu.delete(0, "end")
            for f in s.formats:
                menu.add_command(label=f, command=lambda v=f: self.vars["event"].set(v))
            # Default to first format on manual change
            self.vars["event"].set(s.formats[0])
        except:
            pass

    def _update_table(self):
        for i in self.table.get_children():
            self.table.delete(i)
        codes = [v.seventeenlands[0] for v in self.sets_data.values()]
        names = list(self.sets_data.keys())
        files, _ = retrieve_local_set_list(codes, names)
        for row in sorted(files, key=lambda x: x[7], reverse=True):
            self.table.insert(
                "",
                "end",
                values=(row[0], row[1], row[2], row[3], row[4], row[7], row[5]),
            )

    def _start_download(self, args: DatasetArgs = None):
        self.btn_dl.configure(state="disabled")
        try:
            thr = int(self.vars["threshold"].get())
            ex = FileExtractor(
                self.configuration.settings.database_location,
                self.progress,
                self.vars["status"],
                self,
                threshold=thr,
            )
            ex.clear_data()
            ex.select_sets(self.sets_data[self.vars["set"].get()])
            ex.set_draft_type(self.vars["event"].get())
            ex.set_start_date(self.vars["start"].get())
            ex.set_end_date(self.vars["end"].get())
            ex.set_user_group(self.vars["group"].get())
            ex.set_version(3.0)
            suc = True
            if args and args.color_ratings:
                ex.set_game_count(args.game_count)
                ex.set_color_ratings(args.color_ratings)
            else:
                suc, gc = ex.retrieve_17lands_color_ratings()
            if suc:
                s, m, sz = ex.download_card_data(0)
                if s:
                    self.configuration.card_data.latest_dataset = ex.export_card_data()
                    write_configuration(self.configuration)
                    self._update_table()
                    self.on_update_callback() if self.on_update_callback else None
        except Exception as e:
            messagebox.showerror("Error", str(e))
        finally:
            self.btn_dl.configure(state="normal")

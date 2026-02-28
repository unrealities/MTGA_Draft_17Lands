"""
src/ui/windows/download.py
Integrated Dataset Manager Panel.
Handles 17Lands data retrieval with strict input validation and
asynchronous feedback.
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
from src.ui.components import DynamicTreeviewManager


@dataclass
class DatasetArgs:
    """Data transfer object for automated downloads."""

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

    def refresh(self):
        """Refreshes the local sets table from disk."""
        self._update_table()

    def _build_ui(self):
        container = ttk.Frame(self, padding=10)
        container.pack(fill="both", expand=True)

        # --- 1. Local Dataset Table ---
        ttk.Label(container, text="LOCAL DATASETS", style="Muted.TLabel").pack(
            anchor="w", pady=(0, 5)
        )

        cols = ["Set", "Event", "Group", "Start", "End", "Collected", "Games"]
        self.table_manager = DynamicTreeviewManager(
            container,
            view_id="dataset_manager",
            configuration=self.configuration,
            on_update_callback=lambda: None,  # Static table doesn't need callback refresh
            static_columns=[
                "Set",
                "Event",
                "Group",
                "Start",
                "End",
                "Collected",
                "Games",
            ],
            height=4,
        )
        self.table_manager.pack(fill="both", expand=True, pady=(0, 10))
        self.table = self.table_manager.tree

        # --- 2. Download Form ---
        form = ttk.Frame(container, style="Card.TFrame", padding=12)
        form.pack(fill="x")
        form.columnconfigure(1, weight=1)
        form.columnconfigure(3, weight=1)

        set_options = list(self.sets_data.keys())
        self.vars["set"] = tkinter.StringVar(
            value=set_options[0] if set_options else ""
        )
        ttk.Label(form, text="SET:").grid(row=0, column=0, sticky="e", padx=5)
        self.om_set = ttk.OptionMenu(
            form,
            self.vars["set"],
            self.vars["set"].get(),
            *set_options,
            command=self._on_set_change
        )
        self.om_set.grid(row=0, column=1, sticky="ew", pady=2)

        self.vars["event"] = tkinter.StringVar(value="PremierDraft")
        ttk.Label(form, text="EVENT:").grid(row=0, column=2, sticky="e", padx=5)
        self.om_event = ttk.OptionMenu(
            form, self.vars["event"], "PremierDraft", *constants.LIMITED_TYPE_LIST
        )
        self.om_event.grid(row=0, column=3, sticky="ew", pady=2)

        self.vars["group"] = tkinter.StringVar(value="All")
        ttk.Label(form, text="USERS:").grid(row=1, column=0, sticky="e", padx=5)
        ttk.OptionMenu(
            form, self.vars["group"], "All", *constants.LIMITED_GROUPS_LIST
        ).grid(row=1, column=1, sticky="ew", pady=2)

        self.vars["threshold"] = tkinter.StringVar(value="500")
        ttk.Label(form, text="MIN GAMES:").grid(row=1, column=2, sticky="e", padx=5)
        ttk.Entry(form, textvariable=self.vars["threshold"]).grid(
            row=1, column=3, sticky="ew", pady=2
        )

        self.vars["start"] = tkinter.StringVar(value="2019-01-01")
        ttk.Label(form, text="START DATE:").grid(row=2, column=0, sticky="e", padx=5)
        ttk.Entry(form, textvariable=self.vars["start"]).grid(
            row=2, column=1, sticky="ew", pady=2
        )

        self.vars["end"] = tkinter.StringVar(value=str(date.today()))
        ttk.Label(form, text="END DATE:").grid(row=2, column=2, sticky="e", padx=5)
        ttk.Entry(form, textvariable=self.vars["end"]).grid(
            row=2, column=3, sticky="ew", pady=2
        )

        self.btn_dl = ttk.Button(
            form, text="Download Selected Dataset", command=self._manual_download
        )
        self.btn_dl.grid(row=3, column=0, columnspan=4, pady=(10, 0), sticky="ew")

        # --- 3. Progress area ---
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
        """Called by Notifications to pre-populate and trigger a download."""
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
                self._on_set_change(target_key)

            self.vars["event"].set(args.draft)
            self.vars["group"].set(args.user_group)
            self.vars["start"].set(args.start)
            self.vars["end"].set(args.end)
            self._start_download(args)

    def _manual_download(self):
        self._start_download()

    def _on_set_change(self, val):
        s_info = self.sets_data.get(val)
        if s_info:
            if s_info.start_date:
                self.vars["start"].set(s_info.start_date)
            try:
                menu = self.om_event["menu"]
                menu.delete(0, "end")
                for f in s_info.formats:
                    menu.add_command(
                        label=f, command=lambda v=f: self.vars["event"].set(v)
                    )
                if s_info.formats:
                    self.vars["event"].set(s_info.formats[0])
            except:
                pass

    def _update_table(self):
        for i in self.table.get_children():
            self.table.delete(i)
        codes = [v.seventeenlands[0] for v in self.sets_data.values()]
        files, _ = retrieve_local_set_list(codes, list(self.sets_data.keys()))
        for row in sorted(files, key=lambda x: x[7], reverse=True):
            self.table.insert(
                "",
                "end",
                values=(row[0], row[1], row[2], row[3], row[4], row[7], row[5]),
            )

    def _start_download(self, args: DatasetArgs = None):
        """Internal logic for initiating a download. Tests target this method."""
        self.btn_dl.configure(state="disabled")
        try:
            # Input Validation
            try:
                thr = int(self.vars["threshold"].get().strip() or "500")
            except ValueError:
                raise Exception("The 'Min Games' field must contain a numeric value.")

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
                # If FileExtractor returns 2, this will error "not enough values"
                # If FileExtractor returns 3, this works.
                # If code was (success, msg = ...), then 3 values crashes it with "too many values"
                success, msg, size = ex.download_card_data(0)

                if success:
                    self.configuration.card_data.latest_dataset = ex.export_card_data()
                    write_configuration(self.configuration)
                    self._update_table()
                    if self.on_update_callback:
                        self.on_update_callback()

                    # Differentiate between full success and partial success
                    if "Min Games" in msg:
                        self.vars["status"].set("DOWNLOADED (LIMITED DATA)")
                        messagebox.showwarning(
                            "Partial Data",
                            msg
                            + "\n\nTry lowering the Min Games threshold to get color-specific data.",
                        )
                    else:
                        self.vars["status"].set("DOWNLOAD SUCCESSFUL")
                else:
                    raise Exception(msg)
            else:
                raise Exception(
                    "Failed to connect to 17Lands. You may be rate-limited or the dataset doesn't exist."
                )

        except Exception as e:
            self.vars["status"].set("DOWNLOAD FAILED")
            messagebox.showerror("Download Error", str(e))
        finally:
            self.btn_dl.configure(state="normal")
            self.progress["value"] = 0

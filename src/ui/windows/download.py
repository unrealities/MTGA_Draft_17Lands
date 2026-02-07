"""
src/ui/windows/download.py

This module implements the Download Dataset window.
It handles downloading 17Lands data, rate limiting, and integration with
the notification system for automatic updates.
"""

import tkinter
from tkinter import ttk, messagebox
from datetime import date, datetime, timedelta
import time
from typing import Callable, Optional, Any, Dict
from dataclasses import dataclass

from src import constants
from src.configuration import Configuration, write_configuration
from src.file_extractor import FileExtractor
from src.utils import retrieve_local_set_list, clean_string
from src.ui.styles import Theme
from src.ui.components import ModernTreeview, identify_safe_coordinates


@dataclass
class DatasetArgs:
    draft_set: str
    draft: str
    start: str
    end: str
    user_group: str
    game_count: int
    color_ratings: Optional[Dict] = None


class DownloadWindow(tkinter.Toplevel):
    """
    Window to download dataset files.
    Can be triggered manually via menu or automatically via Notifications.
    """

    def __init__(
        self,
        parent: tkinter.Tk,
        limited_sets: Any,
        configuration: Configuration,
        on_update_callback: Callable[[], None],
    ):
        super().__init__(parent)
        self.sets_data = limited_sets.data
        self.configuration = configuration
        self.on_update_callback = on_update_callback

        self.title("Download Dataset")
        self.configure(bg=Theme.BG_PRIMARY)
        self.transient(parent)
        self.resizable(True, True)  # Allow resizing
        self.withdraw()  # Start hidden

        # State variables
        self.vars = {}
        self.is_auto_running = False

        self._build_ui()
        self._update_table()

        # Position window
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        x, y = identify_safe_coordinates(parent, w, h, 50, 50)
        self.wm_geometry(f"+{x}+{y}")

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        container = ttk.Frame(self, padding=15)
        container.pack(fill="both", expand=True)

        # 1. Table
        table_frame = ttk.Frame(container)
        table_frame.pack(fill="both", expand=True, pady=(0, 15))

        # Increased widths and set "Set" to stretch in ModernTreeview component update
        cols = ["Set", "Event", "Group", "Start", "End", "Games"]
        headers = {
            "Set": {"width": 250, "anchor": tkinter.W},
            "Event": {"width": 120, "anchor": tkinter.CENTER},
            "Group": {"width": 80, "anchor": tkinter.CENTER},
            "Start": {"width": 100, "anchor": tkinter.CENTER},
            "End": {"width": 100, "anchor": tkinter.CENTER},
            "Games": {"width": 80, "anchor": tkinter.CENTER},
        }
        self.table = ModernTreeview(
            table_frame, columns=cols, headers_config=headers, height=10
        )
        self.table.pack(fill="both", expand=True)

        # 2. Form Controls
        form_frame = ttk.Frame(container)
        form_frame.pack(fill="x", pady=(0, 15))

        def add_row(parent, label, widget, row, col_offset=0):
            ttk.Label(parent, text=label).grid(
                row=row, column=0 + col_offset, sticky="e", padx=(0, 5), pady=5
            )
            widget.grid(
                row=row, column=1 + col_offset, sticky="ew", pady=5, padx=(0, 15)
            )

        # Row 1: Set & Event
        set_options = list(self.sets_data.keys())
        self.vars["set"] = tkinter.StringVar(value=set_options[0])
        om_set = ttk.OptionMenu(
            form_frame,
            self.vars["set"],
            set_options[0],
            *set_options,
            command=self._on_set_change,
            style="TMenubutton",
        )

        self.vars["event"] = tkinter.StringVar(value=constants.LIMITED_TYPE_LIST[0])
        self.om_event = ttk.OptionMenu(
            form_frame,
            self.vars["event"],
            constants.LIMITED_TYPE_LIST[0],
            *constants.LIMITED_TYPE_LIST,
            style="TMenubutton",
        )

        add_row(form_frame, "Set:", om_set, 0, 0)
        add_row(form_frame, "Event:", self.om_event, 0, 2)

        # Row 2: Dates
        self.vars["start"] = tkinter.StringVar(value=constants.START_DATE_DEFAULT)
        entry_start = ttk.Entry(form_frame, textvariable=self.vars["start"])

        self.vars["end"] = tkinter.StringVar(value=str(date.today()))
        entry_end = ttk.Entry(form_frame, textvariable=self.vars["end"])

        add_row(form_frame, "Start Date:", entry_start, 1, 0)
        add_row(form_frame, "End Date:", entry_end, 1, 2)

        # Row 3: Group & Min Games
        self.vars["group"] = tkinter.StringVar(value=constants.LIMITED_GROUPS_LIST[0])
        om_group = ttk.OptionMenu(
            form_frame,
            self.vars["group"],
            constants.LIMITED_GROUPS_LIST[0],
            *constants.LIMITED_GROUPS_LIST,
            style="TMenubutton",
        )

        self.vars["threshold"] = tkinter.StringVar(
            value=str(constants.COLOR_WIN_RATE_GAME_COUNT_THRESHOLD_DEFAULT)
        )
        entry_thresh = ttk.Entry(form_frame, textvariable=self.vars["threshold"])

        add_row(form_frame, "User Group:", om_group, 2, 0)
        add_row(form_frame, "Min Games:", entry_thresh, 2, 2)

        form_frame.columnconfigure(1, weight=1)
        form_frame.columnconfigure(3, weight=1)

        # 3. Action Area
        action_frame = ttk.Frame(container)
        action_frame.pack(fill="x")

        self.btn_download = ttk.Button(
            action_frame,
            text="Download",
            command=self._manual_download_trigger,
            style="Accent.TButton",
        )
        self.btn_download.pack(fill="x", pady=(0, 10))

        self.progress = ttk.Progressbar(action_frame, mode="determinate")
        self.progress.pack(fill="x", pady=(0, 5))

        self.vars["status"] = tkinter.StringVar(value="Ready")
        ttk.Label(
            action_frame,
            textvariable=self.vars["status"],
            style="Muted.TLabel",
            anchor="center",
        ).pack()

        # Trigger initial set update to populate dates
        self._on_set_change(set_options[0])

    # --- Public Methods for Notifications Interface ---

    def check_instance_open(self) -> bool:
        """Called by Notifications to check if window is visible."""
        return self.state() == "normal"

    def enter(self, dataset_args=None):
        """Called by Notifications to open window and optionally start a download."""
        self.deiconify()
        self.lift()

        if dataset_args:
            set_code_target = dataset_args.draft_set
            target_key = next(
                (
                    k
                    for k, v in self.sets_data.items()
                    if v.seventeenlands[0] == set_code_target
                ),
                None,
            )

            if target_key:
                self.vars["set"].set(target_key)
                self._on_set_change(target_key)

            self.vars["event"].set(dataset_args.draft)
            self.vars["start"].set(dataset_args.start)
            self.vars["end"].set(dataset_args.end)
            self.vars["group"].set(dataset_args.user_group)

            self.is_auto_running = True

            self._start_download(
                enable_rate_limit=False,
                pre_fetched_color_ratings=dataset_args.color_ratings,
                pre_fetched_game_count=dataset_args.game_count,
            )

    # --- Internal Logic ---

    def _on_close(self):
        self.withdraw()

    def _on_set_change(self, value):
        set_data = self.sets_data.get(value)
        if not set_data:
            return

        if set_data.start_date:
            self.vars["start"].set(set_data.start_date)

        if set_data.formats:
            menu = self.om_event["menu"]
            menu.delete(0, "end")
            for fmt in set_data.formats:
                menu.add_command(
                    label=fmt, command=lambda v=fmt: self.vars["event"].set(v)
                )
            self.vars["event"].set(set_data.formats[0])

    def _update_table(self):
        for item in self.table.get_children():
            self.table.delete(item)

        set_codes = [v.seventeenlands[0] for v in self.sets_data.values()]
        set_names = list(self.sets_data.keys())

        file_list, errors = retrieve_local_set_list(set_codes, set_names)
        file_list.sort(key=lambda x: x[4], reverse=True)

        for idx, row in enumerate(file_list):
            display_vals = row[:6]
            tag = "bw_odd" if idx % 2 != 0 else "bw_even"
            self.table.insert("", "end", values=display_vals, tags=(tag,))

    def _manual_download_trigger(self):
        self._start_download(enable_rate_limit=True)

    def _start_download(
        self,
        enable_rate_limit=True,
        pre_fetched_color_ratings=None,
        pre_fetched_game_count=0,
    ):
        self.btn_download.config(state="disabled")
        self.vars["status"].set("Initializing...")
        self.progress["value"] = 0
        self.update()

        try:
            if enable_rate_limit:
                last_check = self.configuration.card_data.last_check
                current_time = datetime.now().timestamp()
                diff = current_time - last_check

                if diff < constants.DATASET_DOWNLOAD_RATE_LIMIT_SEC:
                    wait_time = int(constants.DATASET_DOWNLOAD_RATE_LIMIT_SEC - diff)
                    messagebox.showinfo(
                        "Rate Limit",
                        f"Please wait {wait_time} seconds before downloading again to avoid IP bans from 17Lands.",
                    )
                    self.btn_download.config(state="normal")
                    self.vars["status"].set("Rate limit reached")
                    return

                if not messagebox.askyesno(
                    "Confirm Download", f"Download data for {self.vars['set'].get()}?"
                ):
                    self.btn_download.config(state="normal")
                    self.vars["status"].set("Cancelled")
                    return

            self.configuration.card_data.last_check = datetime.now().timestamp()
            write_configuration(self.configuration)

            set_key = self.vars["set"].get()
            thresh = int(self.vars["threshold"].get())

            extractor = FileExtractor(
                self.configuration.settings.database_location,
                self.progress,
                self.vars["status"],
                self,
                threshold=thresh,
            )

            extractor.clear_data()
            extractor.select_sets(self.sets_data[set_key])
            extractor.set_draft_type(self.vars["event"].get())

            if not extractor.set_start_date(
                self.vars["start"].get()
            ) or not extractor.set_end_date(self.vars["end"].get()):
                raise ValueError("Invalid Date Format")

            extractor.set_user_group(self.vars["group"].get())
            extractor.set_version(constants.DATA_SET_VERSION_3)

            success = False
            game_count = 0

            if pre_fetched_color_ratings:
                self.vars["status"].set("Using pre-fetched colors...")
                extractor.set_game_count(pre_fetched_game_count)
                extractor.set_color_ratings(pre_fetched_color_ratings)
                game_count = pre_fetched_game_count
                success = True
            else:
                self.vars["status"].set("Downloading Color Ratings...")
                success, game_count = extractor.retrieve_17lands_color_ratings()

            if not success:
                raise Exception("Failed to retrieve color ratings")

            should_proceed = True
            set_code = clean_string(self.sets_data[set_key].seventeenlands[0])
            file_list, _ = retrieve_local_set_list([set_code])

            is_up_to_date = False
            for f in file_list:
                if (
                    f[1] == self.vars["event"].get()
                    and f[2] == self.vars["group"].get()
                    and f[3] == self.vars["start"].get()
                    and f[4] >= self.vars["end"].get()
                    and f[5] == game_count
                ):
                    is_up_to_date = True
                    break

            if is_up_to_date:
                if not messagebox.askyesno(
                    "Up to Date",
                    "This dataset appears to be up to date. Download anyway?",
                ):
                    should_proceed = False

            if game_count == 0 and should_proceed:
                if not messagebox.askyesno(
                    "No Games",
                    "17Lands reports 0 games for this selection. Data may be empty. Continue?",
                ):
                    should_proceed = False

            if should_proceed:
                self.vars["status"].set("Downloading Card Data...")
                success, msg, size = extractor.download_card_data(
                    self.configuration.card_data.database_size
                )

                if success:
                    name = extractor.export_card_data()
                    if name:
                        self.configuration.card_data.database_size = size
                        self.configuration.card_data.latest_dataset = name
                        write_configuration(self.configuration)

                        self._update_table()
                        if self.on_update_callback:
                            self.on_update_callback()

                        self.vars["status"].set("Complete!")
                        self.progress["value"] = 100
                    else:
                        raise Exception("Failed to write file")
                else:
                    raise Exception(msg)
            else:
                self.vars["status"].set("Cancelled")

        except Exception as e:
            self.vars["status"].set("Error")
            messagebox.showerror("Download Error", str(e))
            print(e)
        finally:
            self.btn_download.config(state="normal")
            self.is_auto_running = False

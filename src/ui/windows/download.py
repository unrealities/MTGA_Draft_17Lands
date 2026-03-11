import tkinter
import threading
from tkinter import ttk, messagebox
from datetime import date
from typing import Optional
from dataclasses import dataclass

from src import constants
from src.configuration import write_configuration
from src.file_extractor import FileExtractor
from src.utils import retrieve_local_set_list
from src.ui.components import DynamicTreeviewManager


@dataclass
class DatasetArgs:
    draft_set: str
    draft: str
    start: str
    end: str
    user_group: str
    game_count: int
    color_ratings: Optional[dict] = None


class DownloadWindow(ttk.Frame):
    def __init__(self, parent, limited_sets, configuration, on_update_callback):
        super().__init__(parent)
        self.sets_data = limited_sets.data
        self.latest_set_code = limited_sets.latest_set
        self.configuration = configuration
        self.on_update_callback = on_update_callback
        self.vars = {}
        self._download_thread = None
        self._build_ui()

    def refresh(self):
        self._update_table()

    def _build_ui(self):
        container = ttk.Frame(self, padding=10)
        container.pack(fill="both", expand=True)
        self.table_manager = DynamicTreeviewManager(
            container,
            view_id="dataset_manager",
            configuration=self.configuration,
            on_update_callback=lambda: None,
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
        form = ttk.Frame(container, style="Card.TFrame", padding=12)
        form.pack(fill="x")
        form.columnconfigure(1, weight=1)
        form.columnconfigure(3, weight=1)
        set_options = list(self.sets_data.keys())

        # Force the most recent 17Lands set to the top of the dropdown
        latest_key = None
        for k, v in self.sets_data.items():
            if v.set_code == self.latest_set_code:
                latest_key = k
                break

        if latest_key and latest_key in set_options:
            set_options.remove(latest_key)
            set_options.insert(0, latest_key)

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
            form,
            self.vars["event"],
            "PremierDraft",
            *sorted(constants.LIMITED_TYPE_LIST)
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
        self.progress = ttk.Progressbar(container, mode="determinate")
        self.progress.pack(fill="x", pady=5)
        self.vars["status"] = tkinter.StringVar(value="Ready")
        ttk.Label(
            container, textvariable=self.vars["status"], bootstyle="secondary"
        ).pack()
        self._update_table()

        # Trigger an immediate synchronization so the dynamic dropdowns reflect the correct set's formats
        self._on_set_change(self.vars["set"].get())

    def enter(self, args: DatasetArgs = None):
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
            self.update_idletasks()
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

                formats_to_show = (
                    s_info.formats if s_info.formats else constants.LIMITED_TYPE_LIST
                )
                formats_to_show = sorted(formats_to_show)

                for f in formats_to_show:
                    menu.add_command(
                        label=f, command=lambda v=f: self.vars["event"].set(v)
                    )
                if formats_to_show:
                    self.vars["event"].set(formats_to_show[0])
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
        try:
            thr_str = self.vars["threshold"].get().strip() or "500"
            if not thr_str.isdigit():
                raise ValueError("Min Games must be numeric.")
            threshold = int(thr_str)
        except ValueError as e:
            messagebox.showerror("Download Error", str(e))
            return

        # CAPTURE DATA ON MAIN THREAD BEFORE ENTERING WORKER
        ctx = {
            "set_key": self.vars["set"].get(),
            "event": self.vars["event"].get(),
            "start": self.vars["start"].get(),
            "end": self.vars["end"].get(),
            "group": self.vars["group"].get(),
            "db_loc": self.configuration.settings.database_location,
            "threshold": threshold,
        }

        if self._download_thread and self._download_thread.is_alive():
            return
        self.btn_dl.configure(state="disabled")

        self._download_thread = threading.Thread(
            target=self._run_download_process, args=(args, ctx), daemon=True
        )
        self._download_thread.start()

    def _run_download_process(self, args, ctx):
        try:
            ex = FileExtractor(
                ctx["db_loc"],
                self.progress,
                self.vars["status"],
                self,
                threshold=ctx["threshold"],
            )
            ex.clear_data()
            ex.select_sets(self.sets_data[ctx["set_key"]])
            ex.set_draft_type(ctx["event"])
            ex.set_start_date(ctx["start"])
            ex.set_end_date(ctx["end"])
            ex.set_user_group(ctx["group"])
            ex.set_version(3.0)
            suc = True
            if args and args.color_ratings:
                ex.set_game_count(args.game_count)
                ex.set_color_ratings(args.color_ratings)
            else:
                suc, _ = ex.retrieve_17lands_color_ratings()
            if suc:
                success, msg, _ = ex.download_card_data(0)
                if success:
                    self.configuration.card_data.latest_dataset = ex.export_card_data()
                    write_configuration(self.configuration)
                    self._safe_finalize(msg)
                else:
                    self._safe_error(msg)
            else:
                self._safe_error("17Lands Connection Failed")
        except Exception as e:
            self._safe_error(str(e))

    def _safe_finalize(self, msg):
        def callback():
            if hasattr(self, "winfo_exists") and self.winfo_exists():
                self._finalize_download(msg)

        if threading.current_thread() is threading.main_thread():
            callback()
        else:
            try:
                self.after(0, callback)
            except RuntimeError:
                pass  # Safely ignore during headless test execution

    def _safe_error(self, err):
        def callback():
            if hasattr(self, "winfo_exists") and self.winfo_exists():
                self._handle_error(err)

        if threading.current_thread() is threading.main_thread():
            callback()
        else:
            try:
                self.after(0, callback)
            except RuntimeError:
                pass  # Safely ignore during headless test execution

    def _finalize_download(self, msg):
        self.btn_dl.configure(state="normal")
        self.progress["value"] = 0
        self._update_table()

        status_str = (
            "DOWNLOAD SUCCESSFUL"
            if "Min Games" not in msg
            else "DOWNLOADED (LIMITED DATA)"
        )
        self.vars["status"].set(status_str)

        # Force UI to fully redraw and settle BEFORE the blocking messagebox appears
        self.update_idletasks()

        messagebox.showinfo("Dataset Download Complete", msg)

        # Defer the main app UI refresh until after the user dismisses the dialog
        if self.on_update_callback:
            self.after(50, self.on_update_callback)

    def _handle_error(self, err):
        self.btn_dl.configure(state="normal")
        self.progress["value"] = 0
        self.vars["status"].set("DOWNLOAD FAILED")
        messagebox.showerror("Download Error", err)

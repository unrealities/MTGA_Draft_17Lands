import tkinter
import threading
import os
import json
from tkinter import ttk, messagebox
from datetime import date
from typing import Optional
from dataclasses import dataclass

from src import constants
from src.configuration import CONFIG_LOCK, write_configuration
from src.file_extractor import FileExtractor
from src.utils import retrieve_local_set_list, read_local_manifest
from src.ui.components import DynamicTreeviewManager, AutoScrollbar
from src.ui.styles import Theme


@dataclass
class DatasetArgs:
    draft_set: str
    draft: str
    start: str
    end: str
    user_group: str
    game_count: int
    color_ratings: Optional[dict] = None
    time_period: str = constants.TIME_PERIOD_DEFAULT


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
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        canvas = tkinter.Canvas(self, highlightthickness=0)
        scrollbar = AutoScrollbar(self, orient="vertical", command=canvas.yview)

        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        canvas.configure(yscrollcommand=scrollbar.set)

        container = ttk.Frame(canvas, padding=Theme.scaled_val(10))
        canvas_window = canvas.create_window((0, 0), window=container, anchor="nw")

        def _on_content_resize(event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_resize(event):
            canvas.itemconfig(canvas_window, width=event.width)

        container.bind("<Configure>", _on_content_resize)
        canvas.bind("<Configure>", _on_canvas_resize)

        from src.utils import bind_scroll

        bind_scroll(canvas, canvas.yview_scroll)
        bind_scroll(container, canvas.yview_scroll)

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
        self.table_manager.pack(fill="x", pady=Theme.scaled_val((0, 10)))
        self.table = self.table_manager.tree
        self.table.bind("<Double-1>", self._on_set_active)
        self.table.bind("<Button-3>", self._on_context_menu)
        self.table.bind("<Control-Button-1>", self._on_context_menu)

        form = ttk.Frame(container, style="Card.TFrame", padding=Theme.scaled_val(12))
        form.pack(fill="x")
        form.columnconfigure(1, weight=1)
        form.columnconfigure(3, weight=1)

        # --- DYNAMIC SET SORTING & SEPARATOR LOGIC ---
        set_options = list(self.sets_data.keys())
        active_set_codes = []

        active_set_codes = read_local_manifest().get("active_sets", [])

        active_options = []
        inactive_options = []

        for k in set_options:
            s_info = self.sets_data[k]
            is_active = False
            match_index = 999

            # Check if set_code or 17lands codes match the active calendar
            if s_info.set_code in active_set_codes:
                is_active = True
                match_index = min(match_index, active_set_codes.index(s_info.set_code))

            for sl_code in s_info.seventeenlands:
                if sl_code in active_set_codes:
                    is_active = True
                    match_index = min(match_index, active_set_codes.index(sl_code))

            if is_active:
                active_options.append((match_index, k))
            else:
                inactive_options.append(k)

        # Sort active sets in the exact order they appear in the calendar
        active_options.sort(key=lambda x: x[0])
        active_names = [x[1] for x in active_options]
        inactive_names = inactive_options

        # Fallback if no active sets found (e.g., manifest is missing/empty)
        if not active_names:
            latest_key = None
            for k, v in self.sets_data.items():
                if v.set_code == self.latest_set_code:
                    latest_key = k
                    break

            if latest_key and latest_key in inactive_names:
                inactive_names.remove(latest_key)
                active_names.append(latest_key)

        default_val = (
            active_names[0]
            if active_names
            else (inactive_names[0] if inactive_names else "")
        )
        self.vars["set"] = tkinter.StringVar(value=default_val)

        ttk.Label(form, text="SET:").grid(
            row=0, column=0, sticky="e", padx=Theme.scaled_val(5)
        )

        self.om_set = ttk.OptionMenu(form, self.vars["set"], default_val)
        menu = self.om_set["menu"]
        menu.delete(0, "end")

        for opt in active_names:
            menu.add_command(
                label=opt,
                command=tkinter._setit(self.vars["set"], opt, self._on_set_change),
            )

        if active_names and inactive_names:
            menu.add_separator()

        for opt in inactive_names:
            menu.add_command(
                label=opt,
                command=tkinter._setit(self.vars["set"], opt, self._on_set_change),
            )

        self.om_set.grid(row=0, column=1, sticky="ew", pady=Theme.scaled_val(2))
        # --- END DYNAMIC SET SORTING ---

        self.vars["event"] = tkinter.StringVar(value="PremierDraft")
        ttk.Label(form, text="EVENT:").grid(
            row=0, column=2, sticky="e", padx=Theme.scaled_val(5)
        )
        self.om_event = ttk.OptionMenu(
            form,
            self.vars["event"],
            "PremierDraft",
            *sorted(constants.LIMITED_TYPE_LIST),
        )
        self.om_event.grid(row=0, column=3, sticky="ew", pady=Theme.scaled_val(2))

        self.vars["group"] = tkinter.StringVar(value="All")
        ttk.Label(form, text="USERS:").grid(
            row=1, column=0, sticky="e", padx=Theme.scaled_val(5)
        )
        ttk.OptionMenu(
            form, self.vars["group"], "All", *constants.LIMITED_GROUPS_LIST
        ).grid(row=1, column=1, sticky="ew", pady=Theme.scaled_val(2))

        self.vars["threshold"] = tkinter.StringVar(value="500")
        ttk.Label(form, text="MIN GAMES:").grid(
            row=1, column=2, sticky="e", padx=Theme.scaled_val(5)
        )
        ttk.Entry(form, textvariable=self.vars["threshold"]).grid(
            row=1, column=3, sticky="ew", pady=Theme.scaled_val(2)
        )

        # 17Lands replaced custom start/end date ranges with time_period presets.
        # We still track start/end internally (set-start -> today) for the dataset
        # meta and the table, but the user now picks a preset instead.
        self.vars["start"] = tkinter.StringVar(value="2019-01-01")
        self.vars["end"] = tkinter.StringVar(value=str(date.today()))

        self.vars["period"] = tkinter.StringVar(
            value=constants.TIME_PERIOD_DEFAULT_LABEL
        )
        ttk.Label(form, text="TIME PERIOD:").grid(
            row=2, column=0, sticky="e", padx=Theme.scaled_val(5)
        )
        ttk.OptionMenu(
            form,
            self.vars["period"],
            constants.TIME_PERIOD_DEFAULT_LABEL,
            *constants.TIME_PERIOD_LABELS,
        ).grid(row=2, column=1, sticky="ew", pady=Theme.scaled_val(2))

        self.btn_dl = ttk.Button(
            form, text="Download Selected Dataset", command=self._manual_download
        )
        self.btn_dl.grid(
            row=3, column=0, columnspan=4, pady=Theme.scaled_val((10, 0)), sticky="ew"
        )

        self.btn_clear = ttk.Button(
            form,
            text="Clear Inactive Datasets",
            command=self._clear_inactive_datasets,
            bootstyle="secondary",
        )
        self.btn_clear.grid(
            row=4, column=0, columnspan=4, pady=Theme.scaled_val((5, 0)), sticky="ew"
        )

        ttk.Button(
            form,
            text="Reset Dataset Cache",
            command=self._clear_set_history,
            bootstyle="secondary",
        ).grid(
            row=5, column=0, columnspan=4, pady=Theme.scaled_val((5, 0)), sticky="ew"
        )

        ttk.Button(
            form,
            text="Restore Deleted Datasets",
            command=self._restore_deleted_datasets,
            bootstyle="secondary",
        ).grid(
            row=6, column=0, columnspan=4, pady=Theme.scaled_val((5, 0)), sticky="ew"
        )

        self.progress = ttk.Progressbar(container, mode="determinate")
        self.progress.pack(fill="x", pady=Theme.scaled_val(5))

        self.vars["status"] = tkinter.StringVar(value="Ready")
        ttk.Label(
            container, textvariable=self.vars["status"], bootstyle="secondary"
        ).pack()

        self._update_table()

        # Trigger an immediate synchronization so the dynamic dropdowns reflect the correct set's formats
        self._on_set_change(self.vars["set"].get())

    def _on_set_active(self, event=None):
        """Switches the application to use the selected dataset."""
        selection = self.table.selection()
        if not selection:
            return

        filepath = selection[0]
        filename = os.path.basename(filepath)

        if self.configuration.card_data.latest_dataset != filename:
            self.configuration.card_data.latest_dataset = filename
            write_configuration(self.configuration)

            self._update_table()
            if self.on_update_callback:
                self.on_update_callback()

    def _on_context_menu(self, event):
        """Spawns a right-click menu to manage datasets."""
        region = self.table.identify_region(event.x, event.y)
        if region == "heading":
            return

        row_id = self.table.identify_row(event.y)
        if not row_id:
            return

        self.table.selection_set(row_id)

        menu = tkinter.Menu(self, tearoff=0)
        menu.add_command(label="✅ Set as Active Dataset", command=self._on_set_active)
        menu.add_separator()
        menu.add_command(
            label="🗑️ Delete Dataset", command=lambda: self._delete_dataset(row_id)
        )

        menu.post(event.x_root, event.y_root)

    def _delete_dataset(self, filepath):
        """Deletes a dataset and excludes it from future automatic downloads."""
        filename = os.path.basename(filepath)

        if self.configuration.card_data.latest_dataset == filename:
            messagebox.showwarning(
                "Cannot Delete",
                "You cannot delete the currently active dataset. Please double-click a different dataset to switch to it first.",
            )
            return

        if messagebox.askyesno(
            "Confirm Delete",
            f"Delete this dataset? It will stay excluded from automatic downloads "
            f"until you choose Restore Deleted Datasets.\n\n{filename}",
        ):
            try:
                with CONFIG_LOCK:
                    excluded = self.configuration.card_data.excluded_datasets
                    previous = list(excluded)
                    if filename not in excluded:
                        excluded.append(filename)
                    if not write_configuration(self.configuration):
                        self.configuration.card_data.excluded_datasets = previous
                        raise OSError("Could not save the dataset exclusion.")
                    try:
                        os.remove(filepath)
                    except OSError:
                        self.configuration.card_data.excluded_datasets = previous
                        write_configuration(self.configuration)
                        raise
                from src.utils import invalidate_local_set_cache

                invalidate_local_set_cache()
                self._update_table()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete file:\n{e}")

    def _clear_inactive_datasets(self):
        """Remove all local datasets except the active one and remember exclusions."""
        if self._download_thread and self._download_thread.is_alive():
            messagebox.showwarning(
                "Download In Progress", "Wait for the dataset download to finish before clearing data."
            )
            return

        active_filename = self.configuration.card_data.latest_dataset
        try:
            filenames = [
                name
                for name in os.listdir(constants.SETS_FOLDER)
                if name.endswith(constants.SET_FILE_SUFFIX)
                and name != active_filename
                and os.path.isfile(os.path.join(constants.SETS_FOLDER, name))
            ]
        except OSError as error:
            messagebox.showerror("Error", f"Could not read the dataset folder:\n{error}")
            return

        if not filenames:
            messagebox.showinfo("Clear Inactive Datasets", "There are no inactive datasets to clear.")
            return
        if not messagebox.askyesno(
            "Clear Inactive Datasets",
            f"Delete all {len(filenames)} inactive dataset(s)?\n\n"
            "Your active dataset will be kept. Cleared datasets will stay excluded "
            "from automatic downloads, including after restarting the app.\n\n"
            "Use Restore Deleted Datasets to allow automatic downloads again.",
        ):
            return

        removed = 0
        failures = []
        with CONFIG_LOCK:
            previous = list(self.configuration.card_data.excluded_datasets)
            # Recheck the active selection before committing the cleanup.
            filenames = [
                name for name in filenames
                if name != self.configuration.card_data.latest_dataset
            ]
            self.configuration.card_data.excluded_datasets = list(
                dict.fromkeys(previous + filenames)
            )
            if not write_configuration(self.configuration):
                self.configuration.card_data.excluded_datasets = previous
                messagebox.showerror("Error", "Could not save dataset exclusions. No files were removed.")
                return
            for name in filenames:
                try:
                    os.remove(os.path.join(constants.SETS_FOLDER, name))
                    removed += 1
                except OSError as error:
                    failures.append(f"{name}: {error}")

        from src.utils import invalidate_local_set_cache

        invalidate_local_set_cache()
        self._update_table()
        if failures:
            messagebox.showerror(
                "Dataset Cleanup Incomplete",
                f"Removed {removed} dataset(s). These files could not be removed; "
                "their automatic downloads are disabled:\n\n" + "\n".join(failures),
            )
        else:
            messagebox.showinfo(
                "Inactive Datasets Cleared",
                f"Removed {removed} dataset(s). Your active dataset was kept. "
                "Cleared datasets will not return on restart.",
            )

    def _restore_deleted_datasets(self):
        if not messagebox.askyesno(
            "Restore Deleted Datasets",
            "Allow all deleted or cleared datasets to download automatically again?",
        ):
            return
        with CONFIG_LOCK:
            previous = self.configuration.card_data.excluded_datasets
            self.configuration.card_data.excluded_datasets = []
            if not write_configuration(self.configuration):
                self.configuration.card_data.excluded_datasets = previous
                messagebox.showerror("Error", "Could not save dataset preferences.")
                return
        messagebox.showinfo(
            "Deleted Datasets Restored",
            "Deleted datasets are eligible for automatic downloads again. "
            "Restart the app with automatic dataset sync enabled to download them, "
            "or use Download Selected Dataset.",
        )

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
            self.vars["period"].set(constants.time_period_label(args.time_period))
            self.update_idletasks()
            self._start_download(args)

    def _manual_download(self):
        self._start_download()

    def _resolve_start_date(self, set_key: str) -> str:
        """Best-known start date for a set. The set list can be stuck on the
        placeholder default (stale cache, 17Lands feed gap), so fall back to
        the earliest start_date the synced dataset manifest records for it."""
        s_info = self.sets_data.get(set_key)
        if s_info and s_info.start_date != constants.START_DATE_DEFAULT:
            return s_info.start_date

        codes = {c.upper() for c in (s_info.seventeenlands if s_info else [])}
        manifest_dates = [
            entry["start_date"]
            for key, entry in read_local_manifest().get("datasets", {}).items()
            if key.split("_")[0].upper() in codes and entry.get("start_date")
        ]
        if manifest_dates:
            return min(manifest_dates)

        return self.vars["start"].get()

    def _clear_set_history(self):
        """Deletes all locally downloaded datasets and schedules a fresh refresh on
        the next launch's splash screen. Useful when accumulated old sets slow
        loading or after a data-format change."""
        if not messagebox.askyesno(
            "Reset Dataset Cache",
            "Delete all downloaded datasets?\n\nThe latest 17Lands data will be "
            "re-downloaded automatically the next time you start the app.\n\n"
            "Deleted or cleared datasets will remain excluded. To remove unwanted "
            "datasets permanently, cancel and use Clear Inactive Datasets or right-click "
            "a dataset and choose Delete Dataset.",
        ):
            return

        from src.utils import clear_set_history

        removed = clear_set_history()

        # The active dataset file may now be gone, and resetting the version marker
        # makes the next launch perform the one-time corrected-data refresh.
        self.configuration.card_data.latest_dataset = ""
        self.configuration.settings.last_run_version = ""
        write_configuration(self.configuration)

        self._update_table()
        messagebox.showinfo(
            "Set History Cleared",
            f"Removed {removed} dataset(s). Restart the app to download fresh "
            "17Lands data.",
        )

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

        self.table.tag_configure(
            "active_dataset_card", background="#0ea5e9", foreground="#ffffff"
        )

        codes = [v.seventeenlands[0] for v in self.sets_data.values()]
        files, _ = retrieve_local_set_list(codes, list(self.sets_data.keys()))

        active_filename = self.configuration.card_data.latest_dataset

        for idx, row in enumerate(sorted(files, key=lambda x: x[7], reverse=True)):
            filepath = row[6]
            filename = os.path.basename(filepath)

            is_active = filename == active_filename
            tag = (
                "active_dataset_card"
                if is_active
                else ("bw_odd" if idx % 2 == 0 else "bw_even")
            )

            self.table.insert(
                "",
                "end",
                iid=filepath,
                values=(row[0], row[1], row[2], row[3], row[4], row[7], row[5]),
                tags=(tag,),
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
            "start": self._resolve_start_date(self.vars["set"].get()),
            "end": self.vars["end"].get(),
            "time_period": constants.time_period_value(self.vars["period"].get()),
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
            ex.set_time_period(ctx["time_period"])
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

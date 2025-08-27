import tkinter
import tkinter.messagebox
from tkinter.ttk import Label, Button, OptionMenu, Progressbar, Separator
from datetime import date, datetime, UTC
from src.scaled_window import ScaledWindow, identify_safe_coordinates
from src.constants import START_DATE_DEFAULT, LIMITED_TYPE_LIST, LIMITED_GROUPS_LIST, DATA_SET_VERSION_3, DATASET_DOWNLOAD_RATE_LIMIT_SEC
from src.logger import create_logger
from src.utils import retrieve_local_set_list
from src.file_extractor import FileExtractor
from src.configuration import write_configuration
from dataclasses import dataclass

logger = create_logger()

@dataclass
class DownloadArgs:
    draft_set: tkinter.StringVar
    draft: tkinter.StringVar
    start: tkinter.Entry
    end: tkinter.Entry
    user_group: tkinter.StringVar
    button: Button
    progress: Progressbar
    list_box: tkinter.Widget
    sets: dict
    status: tkinter.StringVar
    version: str

class DownloadDatasetWindow(ScaledWindow):
    """Tkinter window for downloading and managing datasets."""
    _instance_open = False

    def __init__(
            self,
            root,
            limited_sets,
            scale_factor,
            fonts_dict,
            configuration,
            add_set_callback=None,
            update_set_table_callback=None,
            download_args=None
        ):
        if DownloadDatasetWindow._instance_open:
            return
        DownloadDatasetWindow._instance_open = True
        super().__init__()
        self.root = root
        self.limited_sets = limited_sets
        self.scale_factor = scale_factor
        self.fonts_dict = fonts_dict
        self.add_set_callback = add_set_callback
        self.update_set_table_callback = update_set_table_callback
        self.download_args = download_args
        self._auto_add_set_ran = False  # Track if auto add_set has run
        self.configuration = configuration
        self.last_download = 0
        self.__enter()

    def __enter(self):
        """Initialize the window and its widgets."""
        self.window = tkinter.Toplevel(self.root)
        self.window.wm_title("Download Dataset")
        self.window.protocol("WM_DELETE_WINDOW", lambda window=self.window: self.__exit(window))
        self.window.resizable(width=False, height=True)
        self.window.attributes("-topmost", True)
        location_x, location_y = identify_safe_coordinates(
            self.root,
            self._scale_value(1000),
            self._scale_value(170),
            self._scale_value(250),
            self._scale_value(20)
        )
        self.window.wm_geometry(f"+{location_x}+{location_y}")

        tkinter.Grid.rowconfigure(self.window, 1, weight=1)

        try:
            sets = self.limited_sets.data

            headers = {
                "SET": {"width": .30, "anchor": tkinter.W},
                "EVENT": {"width": .12, "anchor": tkinter.CENTER},
                "USER GROUP": {"width": .10, "anchor": tkinter.CENTER},
                "START DATE": {"width": .20, "anchor": tkinter.CENTER},
                "END DATE": {"width": .20, "anchor": tkinter.CENTER},
                "# GAMES": {"width": .10, "anchor": tkinter.E},
            }

            # List box and scrollbar for displaying sets
            list_box_frame = tkinter.Frame(self.window)
            list_box_scrollbar = tkinter.Scrollbar(list_box_frame, orient=tkinter.VERTICAL)
            list_box_scrollbar.pack(side=tkinter.RIGHT, fill=tkinter.Y)

            self.list_box = self._create_header(
                "set_table",
                list_box_frame,
                0,
                self.fonts_dict["Sets.TableRow"],
                headers,
                self._scale_value(500),
                True,
                True,
                "Set.Treeview",
                True
            )
            self.list_box.config(yscrollcommand=list_box_scrollbar.set)
            list_box_scrollbar.config(command=self.list_box.yview)

            notice_label = Label(
                self.window,
                text="17Lands has an embargo period of 12 days for new sets on Magic Arena. Visit https://www.17lands.com for more details.",
                style="Notes.TLabel",
                anchor="c"
            )
            set_label = Label(self.window, text="Set:", style="SetOptions.TLabel", anchor="e")
            event_label = Label(self.window, text="Event:", style="SetOptions.TLabel", anchor="e")
            start_label = Label(self.window, text="Start Date:", style="SetOptions.TLabel", anchor="e")
            end_label = Label(self.window, text="End Date:", style="SetOptions.TLabel", anchor="e")
            group_label = Label(self.window, text="User Group:", style="SetOptions.TLabel", anchor="e")

            draft_choices = LIMITED_TYPE_LIST
            status_text = tkinter.StringVar()
            status_label = Label(self.window, textvariable=status_text, style="Status.TLabel", anchor="c")
            status_text.set("Retrieving Set List")

            event_value = tkinter.StringVar(self.root)
            event_entry = OptionMenu(
                self.window, event_value, draft_choices[0], *draft_choices)
            menu = self.root.nametowidget(event_entry['menu'])
            menu.config(font=self.fonts_dict["All.TMenubutton"])

            start_entry = tkinter.Entry(self.window)
            start_entry.insert(tkinter.END, START_DATE_DEFAULT)
            end_entry = tkinter.Entry(self.window)
            end_entry.insert(tkinter.END, str(date.today()))

            set_choices = list(sets)
            set_value = tkinter.StringVar(self.root)
            set_entry = OptionMenu(
                self.window, set_value, set_choices[0], *set_choices)
            menu = self.root.nametowidget(set_entry['menu'])
            menu.config(font=self.fonts_dict["All.TMenubutton"])

            set_value.trace_add("write", lambda *args, start=start_entry, selection=set_value,
                               set_list=sets: self.__update_set_start_date(start, selection, set_list, *args))

            draft_groups = LIMITED_GROUPS_LIST
            group_value = tkinter.StringVar(self.root)
            group_entry = OptionMenu(self.window, group_value, draft_groups[0], *draft_groups)
            menu = self.root.nametowidget(group_entry['menu'])
            menu.config(font=self.fonts_dict["All.TMenubutton"])

            progress = Progressbar(self.window, orient=tkinter.HORIZONTAL, length=100, mode='determinate')

            # Store widget references for later use
            self._widget_refs = {
                "set_value": set_value,
                "event_value": event_value,
                "start_entry": start_entry,
                "end_entry": end_entry,
                "group_value": group_value,
                "add_button": None,  # Will be set after creation
                "progress": progress,
                "status_text": status_text,
                "sets": sets,
            }

            add_button = Button(
                self.window,
                command=lambda: self.__add_set(
                    DownloadArgs(
                        draft_set=set_value,
                        draft=event_value,
                        start=start_entry,
                        end=end_entry,
                        user_group=group_value,
                        button=add_button,
                        progress=progress,
                        list_box=self.list_box,
                        sets=sets,
                        status=status_text,
                        version=DATA_SET_VERSION_3
                    )
                ),
                text="DOWNLOAD"
            )
            self._widget_refs["add_button"] = add_button

            event_separator = Separator(self.window, orient='vertical')
            set_separator = Separator(self.window, orient='vertical')
            group_separator = Separator(self.window, orient='vertical')

            notice_label.grid(row=0, column=0, columnspan=13, sticky='nsew')
            list_box_frame.grid(row=1, column=0, columnspan=13, sticky='nsew')
            add_button.grid(row=3, column=0, columnspan=13, sticky='nsew')
            progress.grid(row=4, column=0, columnspan=13, sticky='nsew')
            status_label.grid(row=5, column=0, columnspan=13, sticky='nsew')

            set_label.grid(row=2, column=0, sticky='nsew')
            set_entry.grid(row=2, column=1, sticky='nsew')
            set_separator.grid(row=2, column=2, sticky='nsew')
            event_label.grid(row=2, column=3, sticky='nsew')
            event_entry.grid(row=2, column=4, sticky='nsew')
            event_separator.grid(row=2, column=5, sticky='nsew')
            group_label.grid(row=2, column=6, sticky='nsew')
            group_entry.grid(row=2, column=7, sticky='nsew')
            group_separator.grid(row=2, column=8, sticky='nsew')
            start_label.grid(row=2, column=9, sticky='nsew')
            start_entry.grid(row=2, column=10, sticky='nsew')
            end_label.grid(row=2, column=11, sticky='nsew')
            end_entry.grid(row=2, column=12, sticky='nsew')

            self.list_box.pack(expand=True, fill="both")

            self.__update_set_table(self.list_box, sets)
            status_text.set("")
            self.window.update()

            # If download_args was provided, populate widgets and auto-run __add_set once
            if self.download_args and not self._auto_add_set_ran:
                self._populate_widgets_from_args(self.download_args)
                self.window.update()
                self._auto_add_set_ran = True
                self.__add_set(self.download_args)

        except Exception as error:
            logger.error(error)

    def _populate_widgets_from_args(self, args):
        """Populate the widgets with values from DownloadArgs."""
        refs = self._widget_refs
        try:
            refs["set_value"].set(args.draft_set.get() if hasattr(args.draft_set, "get") else args.draft_set)
            refs["event_value"].set(args.draft.get() if hasattr(args.draft, "get") else args.draft)
            refs["start_entry"].delete(0, tkinter.END)
            refs["start_entry"].insert(0, args.start.get() if hasattr(args.start, "get") else args.start)
            refs["end_entry"].delete(0, tkinter.END)
            refs["end_entry"].insert(0, args.end.get() if hasattr(args.end, "get") else args.end)
            refs["group_value"].set(args.user_group.get() if hasattr(args.user_group, "get") else args.user_group)
        except Exception as error:
            logger.error(f"Failed to populate widgets from DownloadArgs: {error}")


    def __exit(self, window):
        DownloadDatasetWindow._instance_open = False
        window.destroy()

    def __update_set_start_date(self, start, selection, set_list, *_):
        """Update the start date entry when a set is selected."""
        try:
            set_data = set_list[selection.get()]
            if set_data.start_date:
                start.delete(0, tkinter.END)
                start.insert(tkinter.END, set_data.start_date)
            self.window.update()
        except Exception as error:
            logger.error(error)

    def __add_set(self, args: DownloadArgs):
        """Initiates the set download process when the Download Dataset button is clicked."""
        args = self.download_args or args
        extractor = FileExtractor(self.configuration.settings.database_location)
        current_time = datetime.now().timestamp()

        try:
            if not self._rate_limit_check(current_time, args):
                return

            self._setup_extractor(extractor, args)
            self.last_download = current_time

            set_codes = [v.seventeenlands[0] for v in args.sets.values()]
            file_list, error_list = retrieve_local_set_list(set_codes)
            for error_string in error_list:
                logger.error(error_string)

            args.status.set("Downloading Color Ratings")
            self.window.update()
            download_success, game_count = extractor.retrieve_17lands_color_ratings()

            if not self._handle_game_count_and_notify(download_success, game_count, file_list, args):
                return

            download_success, result_string, temp_size = extractor.download_card_data(
                self.window, args.progress, args.status, self.configuration.card_data.database_size
            )
            if not download_success:
                self._handle_failure(args, result_string)
                return

            if not extractor.export_card_data():
                self._handle_failure(args, "File Write Failure")
                return

            args.progress['value'] = 100
            self.window.update()
            args.status.set("Updating Set List")
            self.__update_set_table(args.list_box, args.sets)
            args.status.set("Download Complete")
            args.button['state'] = 'normal'
            self.configuration.card_data.database_size = temp_size
            write_configuration(self.configuration)
            self.window.update()

        except Exception as error:
            self._handle_failure(args, error)

    def _rate_limit_check(self, current_time, args):
        time_difference = current_time - self.last_download
        if time_difference < DATASET_DOWNLOAD_RATE_LIMIT_SEC:
            tkinter.messagebox.showinfo(
                title="Download",
                message="Rate limit reached.\n\n"
                        f"Please wait {int(DATASET_DOWNLOAD_RATE_LIMIT_SEC - time_difference)} seconds before trying again."
            )
            return False
        confirm = tkinter.messagebox.askyesno(
            title="Download",
            message=f"Are you sure that you want to download the {args.draft_set.get()} {args.draft.get()} dataset?"
        )
        return confirm

    def _setup_extractor(self, extractor, args):
        args.status.set("Starting Download Process")
        extractor.clear_data()
        args.button['state'] = 'disabled'
        args.progress['value'] = 0
        self.window.update()
        extractor.select_sets(args.sets[args.draft_set.get()])
        extractor.set_draft_type(args.draft.get())
        if not extractor.set_start_date(args.start.get()):
            raise ValueError("Invalid Start Date (YYYY-MM-DD)")
        if not extractor.set_end_date(args.end.get()):
            raise ValueError("Invalid End Date (YYYY-MM-DD)")
        extractor.set_user_group(args.user_group.get())
        extractor.set_version(args.version)

    def _handle_game_count_and_notify(self, download_success, game_count, file_list, args):
        if download_success and file_list:
            if game_count == 0:
                message_box = tkinter.messagebox.askyesno(
                    title="Download",
                    message=f"17Lands doesn't currently have card statistics for {args.draft_set.get()} {args.draft.get()} {args.start.get()} to {args.end.get()}.\n\n"
                            "If you plan to use a tier list, you will still need to download this dataset so this application can read the Arena log.\n\n"
                            "Would you like to continue with the download?"
                )
                if not message_box:
                    args.status.set("Download Cancelled")
                    return False
            else:
                notify = False
                set_code = args.sets[args.draft_set.get()].seventeenlands[0]
                for file in file_list:
                    if (
                        set_code == file[0] and
                        args.draft.get() == file[1] and
                        args.user_group.get() == file[2] and
                        args.start.get() == file[3] and
                        (args.end.get() == file[4] or args.end.get() > file[4]) and
                        game_count == file[5]
                    ):
                        notify = True
                        break
                if notify:
                    current_time_utc = datetime.now(UTC).strftime('%H:%M:%S')
                    message_box = tkinter.messagebox.askyesno(
                        title="Download",
                        message="Your dataset is already up-to-date.\n\n"
                                f"It's currently {current_time_utc} UTC, and 17Lands updates their card data once a day around 03:00:00 UTC.\n\n"
                                "Would you still like to continue with the download?"
                    )
                    if not message_box:
                        args.status.set("Download Cancelled")
                        return False
        return True

    def _handle_failure(self, args, result_string):
        args.status.set("Download Failed")
        self.window.update()
        args.button['state'] = 'normal'
        message_string = f"Download Failed: {result_string}"
        tkinter.messagebox.showwarning(title="Error", message=message_string)
        self.window.update()

    def __update_set_table(self, list_box, sets):
        """Updates the set list in the Set View table."""
        # Delete the content of the list box
        for row in list_box.get_children():
            list_box.delete(row)
        self.window.update()
        set_codes = [v.seventeenlands[0] for v in sets.values()]
        set_names = sets.keys()
        file_list, error_list = retrieve_local_set_list(set_codes, set_names)

        # Log all errors generated by retrieve_local_set_list
        for error_string in error_list:
            logger.error(error_string)

        if file_list:
            list_box.config(height=min(len(file_list), 10))
        else:
            list_box.config(height=0)

        # Sort list by end date
        file_list.sort(key=lambda x: x[4], reverse=True)

        for count, file in enumerate(file_list):
            row_tag = self._identify_table_row_tag(False, "", count)
            list_box.insert("", index=count, iid=count, values=file, tag=(row_tag,))
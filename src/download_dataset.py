import tkinter
import tkinter.messagebox
from dataclasses import dataclass
from tkinter.ttk import Label, Button, OptionMenu, Progressbar, Separator
from datetime import date, datetime, UTC
from src.scaled_window import ScaledWindow, identify_safe_coordinates
from src.constants import START_DATE_DEFAULT, LIMITED_TYPE_LIST, LIMITED_GROUPS_LIST, DATA_SET_VERSION_3, DATASET_DOWNLOAD_RATE_LIMIT_SEC
from src.logger import create_logger
from src.utils import retrieve_local_set_list, clean_string
from src.file_extractor import FileExtractor
from src.configuration import write_configuration

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
    game_count: int = 0
    version: str = DATA_SET_VERSION_3
    color_ratings: dict = None
    enable_rate_limit: bool = True

@dataclass
class DatasetArgs:
    draft_set: str
    draft: str
    start: str
    end: str
    user_group: str
    game_count: int
    color_ratings: dict = None

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
            auto_enter=True,
            update_event_files_callback=None,
        ):
        super().__init__()
        self.root = root
        self.limited_sets = limited_sets
        self.scale_factor = scale_factor
        self.fonts_dict = fonts_dict
        self.update_event_files_callback = update_event_files_callback
        self._auto_add_set_ran = False  # Track if auto add_set has run
        self.configuration = configuration
        if auto_enter:
            self.enter()

    def enter(self, dataset_args: DatasetArgs = None):
        """Initialize the window and its widgets."""
        if DownloadDatasetWindow._instance_open:
            return
        DownloadDatasetWindow._instance_open = True
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
            set_value.trace_add("write", lambda *args, event_widget=event_entry, event_selection=event_value, set_selection=set_value,
                               set_list=sets: self.__update_event_format(event_widget, event_selection, set_selection, set_list, *args))
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
                        button=add_button,
                        progress=progress,
                        list_box=self.list_box,
                        sets=sets,
                        status=status_text,
                        draft_set=set_value,
                        draft=event_value,
                        start=start_entry,
                        end=end_entry,
                        user_group=group_value,
                        game_count = 0,
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
            self.__update_set_start_date(start_entry, set_value, sets)
            self.__update_event_format(event_entry, event_value, set_value, sets)
            status_text.set("")
            self.window.update()

            # If download_args was provided, populate widgets and auto-run add_set once
            if dataset_args and not self._auto_add_set_ran:
                set_string = [k for k, v in sets.items() if v.seventeenlands[0] == dataset_args.draft_set]
                if set_string:
                    dataset_args.draft_set = set_string[0]
                self._populate_widgets_from_args(dataset_args)
                self.window.update()
                self._auto_add_set_ran = True
                self.__add_set(
                    DownloadArgs(
                        button=add_button,
                        progress=progress,
                        list_box=self.list_box,
                        sets=sets,
                        status=status_text,
                        draft_set=set_value,
                        draft=event_value,
                        start=start_entry,
                        end=end_entry,
                        user_group=group_value,
                        game_count = dataset_args.game_count,
                        color_ratings = dataset_args.color_ratings,
                        enable_rate_limit=False
                    )
                )

        except Exception as error:
            logger.error(error)

    def check_instance_open(self):
        """Check if an instance of the DownloadDatasetWindow is already open."""
        return DownloadDatasetWindow._instance_open

    def _populate_widgets_from_args(self, args):
        """Populate the widgets with values from DownloadArgs."""
        refs = self._widget_refs
        try:
            refs["set_value"].set(args.draft_set)
            refs["event_value"].set(args.draft)
            refs["start_entry"].delete(0, tkinter.END)
            refs["start_entry"].insert(0, args.start)
            refs["end_entry"].delete(0, tkinter.END)
            refs["end_entry"].insert(0, args.end)
            refs["group_value"].set(args.user_group)
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

    def __update_event_format(self, event_widget, event_selection, set_selection, format_list, *_):
        '''Function that's used to update the Event options in the Download Dataset window
           Example: When a user selects a set, the available event formats (e.g., PremierDraft, Sealed)
           are refreshed in the Event dropdown so that only formats valid for that set are shown
        '''
        try:
            set_data = format_list[set_selection.get()]

            if set_data.formats:
                menu = event_widget['menu']
                menu.delete(0, tkinter.END)
                for event_format in set_data.formats:
                    menu.add_command(label=event_format, command=lambda value=event_format: event_selection.set(value))  # add new ones

                event_selection.set(set_data.formats[0])
            self.root.update()
        except Exception as error:
            logger.error(error)

    def __add_set(self, download_args: DownloadArgs):
        """Initiates the set download process when the Download Dataset button is clicked."""
        extractor = FileExtractor(self.configuration.settings.database_location, download_args.progress, download_args.status, self.window)
        current_time = datetime.now().timestamp()

        try:
            if download_args.enable_rate_limit:
                if not self._rate_limit_check(current_time, download_args):
                    return

            self._setup_extractor(extractor, download_args)
            self.configuration.card_data.last_check = current_time
            write_configuration(self.configuration)

            set_codes = [v.seventeenlands[0] for v in download_args.sets.values()]
            file_list, error_list = retrieve_local_set_list(set_codes)
            for error_string in error_list:
                logger.error(error_string)

            download_args.status.set("Downloading Color Ratings")
            self.window.update()
            if not download_args.color_ratings:
                download_success, game_count = extractor.retrieve_17lands_color_ratings()
            else:
                game_count = download_args.game_count
                extractor.set_game_count(game_count)
                extractor.set_color_ratings(download_args.color_ratings)
                download_success = True

            if not self._handle_game_count_and_notify(download_success, game_count, file_list, download_args):
                download_args.button['state'] = 'normal'
                self.window.update()
                return

            download_success, result_string, temp_size = extractor.download_card_data(self.configuration.card_data.database_size)
            if not download_success:
                self._handle_failure(download_args, result_string)
                return

            dataset_name = extractor.export_card_data()
            if not dataset_name:
                self._handle_failure(download_args, "File Write Failure")
                return

            download_args.progress['value'] = 100
            self.window.update()
            download_args.status.set("Updating Set List")
            self.__update_set_table(download_args.list_box, download_args.sets)
            self.update_event_files_callback()
            download_args.status.set("Download Complete")
            download_args.button['state'] = 'normal'
            self.configuration.card_data.database_size = temp_size
            self.configuration.card_data.latest_dataset = dataset_name
            write_configuration(self.configuration)
            self.window.update()

        except Exception as error:
            self._handle_failure(download_args, error)

    def _rate_limit_check(self, current_time, args):
        time_difference = current_time - self.configuration.card_data.last_check
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

    def _setup_extractor(self, extractor, download_args):
        download_args.status.set("Starting Download Process")
        extractor.clear_data()
        download_args.button['state'] = 'disabled'
        download_args.progress['value'] = 0
        self.window.update()
        extractor.select_sets(download_args.sets[download_args.draft_set.get()])
        extractor.set_draft_type(download_args.draft.get())
        if not extractor.set_start_date(download_args.start.get()):
            raise ValueError("Invalid Start Date (YYYY-MM-DD)")
        if not extractor.set_end_date(download_args.end.get()):
            raise ValueError("Invalid End Date (YYYY-MM-DD)")
        extractor.set_user_group(download_args.user_group.get())
        extractor.set_version(download_args.version)

    def _handle_game_count_and_notify(self, download_success, game_count, file_list, download_args):
        if download_success and file_list:
            if game_count == 0:
                message_box = tkinter.messagebox.askyesno(
                    title="Download",
                    message=f"17Lands doesn't currently have card statistics for {download_args.draft_set.get()} {download_args.draft.get()} {download_args.start.get()} to {download_args.end.get()}.\n\n"
                            "If you plan to use a tier list, you will still need to download this dataset so this application can read the Arena log.\n\n"
                            "Would you like to continue with the download?"
                )
                if not message_box:
                    download_args.status.set("Download Cancelled")
                    return False
            else:
                notify = False
                set_code = clean_string(download_args.sets[download_args.draft_set.get()].seventeenlands[0])
                for file in file_list:
                    if (
                        set_code == file[0] and
                        download_args.draft.get() == file[1] and
                        download_args.user_group.get() == file[2] and
                        download_args.start.get() == file[3] and
                        (download_args.end.get() == file[4] or download_args.end.get() > file[4]) and
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
                        download_args.status.set("Download Cancelled")
                        return False
        return True

    def _handle_failure(self, args, result_string):
        args.status.set("Download Failed")
        self.window.update()
        args.button['state'] = 'normal'
        message_string = f"Download Failed: {result_string}"
        tkinter.messagebox.showwarning(title="Error", message=message_string)
        self.window.update()
        logger.error(message_string)

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
        file_list.sort(key=lambda x: x[7], reverse=True)

        for count, file in enumerate(file_list):
            row_tag = self._identify_table_row_tag(False, "", count)
            list_box.insert("", index=count, iid=count, values=file, tag=(row_tag,))
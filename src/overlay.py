"""This module contains the functions and classes that are used for building and handling the application UI"""

import tkinter
from tkinter.ttk import (
    Progressbar,
    Treeview,
    Style,
    OptionMenu,
    Button,
    Checkbutton,
    Label,
    Separator,
    Entry,
)
from tkinter import filedialog, messagebox, font
import requests
import sys
import io
import math
import argparse
import webbrowser
from os import stat, path
from pynput.keyboard import Listener, KeyCode
from PIL import Image, ImageTk, ImageFont
from src.configuration import (
    read_configuration,
    write_configuration,
    reset_configuration,
)
from src.limited_sets import LimitedSets
from src.log_scanner import ArenaScanner, Source
from src.file_extractor import search_arena_log_locations, retrieve_arena_directory
from src.utils import open_file
from src import constants
from src.logger import create_logger
from src.scaled_window import ScaledWindow, identify_safe_coordinates
from src.tier_list import TierWindow, TierList
from src.download_dataset import DownloadDatasetWindow
from src.notifications import Notifications
from src.card_logic import (
    CardResult,
    copy_deck,
    stack_cards,
    field_process_sort,
    filter_options,
    deck_card_search,
    get_card_colors,
    get_deck_metrics,
    suggest_deck,
    export_draft_to_csv,
    export_draft_to_json,
    copy_pack_to_clipboard,
)
from src.signals import SignalCalculator

try:
    import win32api
except ImportError:
    pass

HOTKEY_CTRL_G = "\x07"

logger = create_logger()


def start_overlay():
    """Retrieve arguments, create overlay object, and run overlay"""
    parser = argparse.ArgumentParser()

    parser.add_argument("-f", "--file")
    parser.add_argument("-d", "--data")
    parser.add_argument("--step", action="store_true")

    args = parser.parse_known_args()

    # Ignore unknown arguments from ArgumentParser - pytest change
    overlay = Overlay(args[0])

    overlay.main_loop()


def restart_overlay(root):
    """Close/destroy the current overlay object and create a new instance"""
    root.close_overlay()
    start_overlay()


def fixed_map(style, option):
    """Returns the style map for 'option' with any styles starting with
    ("!disabled", "!selected", ...) filtered out"""
    return [
        elm
        for elm in style.map("Treeview", query_opt=option)
        if elm[:2] != ("!disabled", "!selected")
    ]


def control_table_column(table, column_fields, table_width=None):
    """Hide disabled table columns"""
    visible_columns = {}
    last_field_index = 0
    for count, (key, value) in enumerate(column_fields.items()):
        if value != constants.DATA_FIELD_DISABLED:
            table.heading(key, text=value.upper())
            visible_columns[key] = count
            last_field_index = count

    table["displaycolumns"] = list(visible_columns.keys())

    if table_width:
        total_visible_columns = len(visible_columns)
        width = table_width
        offset = 0
        if total_visible_columns <= 4:
            proportions = constants.TABLE_PROPORTIONS[total_visible_columns - 1]
            for column in table["displaycolumns"]:
                column_width = min(
                    int(math.ceil(proportions[offset] * table_width)), width
                )
                width -= column_width
                offset += 1
                table.column(column, width=column_width)

            table["show"] = "headings"

    return last_field_index, visible_columns


def copy_suggested(deck_colors, deck, color_options):
    """Copy the deck and sideboard list from the Suggest Deck window"""
    colors = color_options[deck_colors.get()]
    deck_string = ""
    try:
        deck_string = copy_deck(
            deck[colors]["deck_cards"], deck[colors]["sideboard_cards"]
        )
        copy_clipboard(deck_string)
    except Exception as error:
        logger.error(error)
    return


def copy_taken(taken_cards):
    """Copy the card list from the Taken Cards window"""
    deck_string = ""
    try:
        stacked_cards = stack_cards(taken_cards)
        deck_string = copy_deck(stacked_cards, None)
        copy_clipboard(deck_string)

    except Exception as error:
        logger.error(error)
    return


def copy_clipboard(copy):
    """Send the copied data to the clipboard"""
    try:
        clip = tkinter.Tk()
        clip.withdraw()
        clip.clipboard_clear()
        clip.clipboard_append(copy)
        clip.update()
        clip.destroy()
    except Exception as error:
        logger.error(error)
    return


def toggle_widget(input_widget, enable):
    """Hide/Display a UI widget"""
    try:
        if enable:
            input_widget.grid()
        else:
            input_widget.grid_remove()
    except Exception as error:
        logger.error(error)


def url_callback(event):
    webbrowser.open_new(event.widget.cget("text"))


class AutocompleteEntry(tkinter.Entry):
    def initialize(self, completion_list):
        self.completion_list = completion_list
        self.hitsIndex = -1
        self.hits = []
        self.autocompleted = False
        self.current = ""
        self.bind("<KeyRelease>", self.act_on_release)
        self.bind("<KeyPress>", self.act_on_press)

    def autocomplete(self):
        self.current = self.get().lower()
        self.hits = [
            item
            for item in self.completion_list
            if item.lower().startswith(self.current)
        ]
        if self.hits:
            self.hitsIndex = 0
            self.display_autocompletion()
        else:
            self.hitsIndex = -1
            self.remove_autocompletion()

    def remove_autocompletion(self):
        self.autocompleted = False

    def display_autocompletion(self):
        if self.hitsIndex == -1:
            self.remove_autocompletion()  # Don't display anything if hitsIndex is -1
            return
        if self.hits:
            cursor = self.index(tkinter.INSERT)
            self.delete(0, tkinter.END)
            self.insert(0, self.hits[self.hitsIndex])
            self.select_range(cursor, tkinter.END)
            self.icursor(cursor)
            self.autocompleted = True
        else:
            self.autocompleted = False

    def act_on_release(self, event):
        if event.keysym in ("BackSpace", "Delete"):
            self.autocompleted = False
            return

        if event.keysym not in ("Down", "Up", "Tab", "Right", "Left"):
            self.autocomplete()

    def act_on_press(self, event):
        if event.keysym == "Left":
            if self.autocompleted:
                self.remove_autocompletion()
                return "break"

        if event.keysym in ("Down", "Up", "Tab"):
            if self.select_present():
                cursor = self.index(tkinter.SEL_FIRST)
                if self.hits and self.current == self.get().lower()[0:cursor]:
                    if event.keysym == "Up":
                        self.hitsIndex = (self.hitsIndex - 1) % len(self.hits)
                    else:
                        self.hitsIndex = (self.hitsIndex + 1) % len(self.hits)
                    self.display_autocompletion()
            else:
                self.autocomplete()
            return "break"

        if event.keysym == "Right":
            if self.select_present():
                self.selection_clear()
                self.icursor(tkinter.END)
                return "break"

        if event.keysym in ("BackSpace", "Delete"):
            if self.autocompleted:
                self.remove_autocompletion()

    def select_present(self):
        try:
            self.index(tkinter.SEL_FIRST)
            return True
        except tkinter.TclError:
            return False


class Overlay(ScaledWindow):
    """Class that handles all of the UI widgets"""

    def __init__(self, args):
        super().__init__()
        self.root = tkinter.Tk()
        self.root.title(f"MTGA Draft Tool v{constants.APPLICATION_VERSION:2.2f}")
        self.configuration, _ = read_configuration()
        self.root.resizable(False, False)

        self.__set_os_configuration()

        self.table_width = self._scale_value(self.configuration.settings.table_width)

        self.listener = None
        self.configuration.settings.arena_log_location = search_arena_log_locations(
            [args.file, self.configuration.settings.arena_log_location]
        )

        if self.configuration.settings.arena_log_location:
            write_configuration(self.configuration)
        self.arena_file = self.configuration.settings.arena_log_location

        if args.data is None:
            self.configuration.settings.database_location = retrieve_arena_directory(
                self.arena_file
            )
        else:
            self.configuration.settings.database_location = args.file

        self.step_through = args.step

        self.limited_sets = LimitedSets().retrieve_limited_sets()
        self.draft = ArenaScanner(
            self.arena_file,
            self.limited_sets,
            step_through=self.step_through,
            retrieve_unknown=True,
        )

        self.trace_ids = []
        self.tier_data = {}

        self.main_options_dict = constants.COLUMNS_OPTIONS_EXTRA_DICT.copy()
        self.deck_colors = self.draft.retrieve_color_win_rate(
            self.configuration.settings.filter_format
        )
        self.data_sources = self.draft.retrieve_data_sources()
        self.tier_list = TierList()
        self.set_metrics = self.draft.retrieve_set_metrics()

        tkinter.Grid.columnconfigure(self.root, 0, weight=1)
        tkinter.Grid.columnconfigure(self.root, 1, weight=1)
        
        # Menu Bar
        self.menubar = tkinter.Menu(self.root)
        self.filemenu = tkinter.Menu(self.menubar, tearoff=0)
        self.filemenu.add_command(label="Read Draft Log", command=self.__open_draft_log)
        self.filemenu.add_command(
            label="Read Player.log",
            command=lambda: self.__open_draft_log(
                self.configuration.settings.arena_log_location
            ),
        )
        self.filemenu.add_command(
            label="Open Player.log",
            command=lambda: open_file(self.configuration.settings.arena_log_location),
        )
        self.datamenu = tkinter.Menu(self.menubar, tearoff=0)
        self.datamenu.add_command(
            label="Download Dataset",
            command=lambda: DownloadDatasetWindow(
                self.root,
                self.limited_sets,
                self.scale_factor,
                self.fonts_dict,
                self.configuration,
                True,
                self.__update_event_files_callback,
            ),
        )
        self.datamenu.add_command(
            label="Download Tier List",
            command=lambda: TierWindow(
                self.scale_factor, self.fonts_dict, self.__update_source_callback
            ),
        )
        self.cardmenu = tkinter.Menu(self.menubar, tearoff=0)
        self.cardmenu.add_command(
            label="Taken Cards", command=self.__open_taken_cards_window
        )
        self.cardmenu.add_command(
            label="Suggest Decks", command=self.__open_suggest_deck_window
        )
        self.cardmenu.add_command(
            label="Compare Cards", command=self.__open_card_compare_window
        )

        self.settingsmenu = tkinter.Menu(self.menubar, tearoff=0)
        self.settingsmenu.add_command(
            label="Settings", command=self.__open_settings_window
        )

        self.helpmenu = tkinter.Menu(self.menubar, tearoff=0)
        self.helpmenu.add_command(label="About", command=self.__open_about_window)

        self.menubar.add_cascade(label="File", menu=self.filemenu)
        self.menubar.add_cascade(label="Data", menu=self.datamenu)
        self.menubar.add_cascade(label="Cards", menu=self.cardmenu)
        self.menubar.add_cascade(label="Settings", menu=self.settingsmenu)
        self.menubar.add_cascade(label="Help", menu=self.helpmenu)
        self.root.config(menu=self.menubar)

        self.current_draft_label_frame = tkinter.Frame(self.root)

        self.status_dot = Label(self.current_draft_label_frame, text="●", foreground="#ed333b")
        self.status_dot.pack(side=tkinter.LEFT, padx=(5, 2))
        
        self.current_draft_label = Label(
            self.current_draft_label_frame,
            text="Current Draft:",
            style="MainSectionsBold.TLabel",
            anchor="e",
        )
        self.current_draft_value_frame = tkinter.Frame(self.root)
        self.current_draft_value_label = Label(
            self.current_draft_value_frame,
            text="",
            style="CurrentDraft.TLabel",
            anchor="w",
        )

        self.data_source_label_frame = tkinter.Frame(self.root)
        self.data_source_label = Label(
            self.data_source_label_frame,
            text="Data Source:",
            style="MainSectionsBold.TLabel",
            anchor="e",
        )

        self.deck_colors_label_frame = tkinter.Frame(self.root)
        self.deck_colors_label = Label(
            self.deck_colors_label_frame,
            text="Deck Filter:",
            style="MainSectionsBold.TLabel",
            anchor="e",
        )

        self.data_source_selection = tkinter.StringVar(self.root)
        self.data_source_list = self.data_sources

        # Persistence symmetric variables
        self.deck_stats_checkbox_value = tkinter.IntVar(self.root)
        self.signals_checkbox_value = tkinter.IntVar(self.root)
        self.missing_cards_checkbox_value = tkinter.IntVar(self.root)
        self.auto_highest_checkbox_value = tkinter.IntVar(self.root)
        self.curve_bonus_checkbox_value = tkinter.IntVar(self.root)
        self.color_bonus_checkbox_value = tkinter.IntVar(self.root)
        self.draft_log_checkbox_value = tkinter.IntVar(self.root)
        self.p1p1_ocr_checkbox_value = tkinter.IntVar(self.root)
        self.save_screenshot_checkbox_value = tkinter.IntVar(self.root)
        self.taken_alsa_checkbox_value = tkinter.IntVar(self.root)
        self.taken_ata_checkbox_value = tkinter.IntVar(self.root)
        self.taken_gpwr_checkbox_value = tkinter.IntVar(self.root)
        self.taken_ohwr_checkbox_value = tkinter.IntVar(self.root)
        self.taken_gndwr_checkbox_value = tkinter.IntVar(self.root)
        self.taken_iwd_checkbox_value = tkinter.IntVar(self.root)
        self.taken_wheel_checkbox_value = tkinter.IntVar(self.root)
        self.taken_gdwr_checkbox_value = tkinter.IntVar(self.root)
        self.card_colors_checkbox_value = tkinter.IntVar(self.root)
        self.color_identity_checkbox_value = tkinter.IntVar(self.root)
        self.current_draft_checkbox_value = tkinter.IntVar(self.root)
        self.data_source_checkbox_value = tkinter.IntVar(self.root)
        self.deck_filter_checkbox_value = tkinter.IntVar(self.root)
        self.refresh_button_checkbox_value = tkinter.IntVar(self.root)
        self.update_notifications_checkbox_value = tkinter.IntVar(self.root)
        self.missing_notifications_checkbox_value = tkinter.IntVar(self.root)

        self.taken_type_creature_checkbox_value = tkinter.IntVar(self.root)
        self.taken_type_creature_checkbox_value.set(True)
        self.taken_type_land_checkbox_value = tkinter.IntVar(self.root)
        self.taken_type_land_checkbox_value.set(True)
        self.taken_type_instant_sorcery_checkbox_value = tkinter.IntVar(self.root)
        self.taken_type_instant_sorcery_checkbox_value.set(True)
        self.taken_type_other_checkbox_value = tkinter.IntVar(self.root)
        self.taken_type_other_checkbox_value.set(True)

        self.column_2_selection = tkinter.StringVar(self.root)
        self.column_2_list = self.main_options_dict.keys()
        self.column_3_selection = tkinter.StringVar(self.root)
        self.column_3_list = self.main_options_dict.keys()
        self.column_4_selection = tkinter.StringVar(self.root)
        self.column_4_list = self.main_options_dict.keys()
        self.column_5_selection = tkinter.StringVar(self.root)
        self.column_5_list = self.main_options_dict.keys()
        self.column_6_selection = tkinter.StringVar(self.root)
        self.column_6_list = self.main_options_dict.keys()
        self.column_7_selection = tkinter.StringVar(self.root)
        self.column_7_list = self.main_options_dict.keys()
        self.filter_format_selection = tkinter.StringVar(self.root)
        self.filter_format_list = constants.DECK_FILTER_FORMAT_LIST
        self.result_format_selection = tkinter.StringVar(self.root)
        self.result_format_list = constants.RESULT_FORMAT_LIST
        self.deck_filter_selection = tkinter.StringVar(self.root)
        self.deck_filter_list = self.deck_colors.keys()
        self.taken_filter_selection = tkinter.StringVar(self.root)
        self.taken_type_selection = tkinter.StringVar(self.root)
        self.ui_size_selection = tkinter.StringVar(self.root)
        self.ui_size_list = constants.UI_SIZE_DICT.keys()

        self.data_source_option_frame = tkinter.Frame(self.root)
        self.data_source_options = OptionMenu(
            self.data_source_option_frame,
            self.data_source_selection,
            self.data_source_selection.get(),
            *self.data_source_list,
            style="All.TMenubutton",
        )
        menu = self.root.nametowidget(self.data_source_options["menu"])
        menu.config(font=self.fonts_dict["All.TMenubutton"])

        self.column_2_options = None
        self.column_3_options = None
        self.column_4_options = None
        self.column_5_options = None
        self.column_6_options = None
        self.column_7_options = None
        self.taken_table = None
        self.compare_table = None
        self.compare_list = None
        self.suggester_table = None

        self.about_window_open = False
        self.sets_window_open = False

        self.deck_colors_option_frame = tkinter.Frame(self.root)
        self.deck_colors_options = OptionMenu(
            self.deck_colors_option_frame,
            self.deck_filter_selection,
            self.deck_filter_selection.get(),
            *self.deck_filter_list,
            style="All.TMenubutton",
        )
        menu = self.root.nametowidget(self.deck_colors_options["menu"])
        menu.config(font=self.fonts_dict["All.TMenubutton"])

        self.refresh_button_frame = tkinter.Frame(self.root)
        self.refresh_button = Button(
            self.refresh_button_frame,
            command=lambda: self.__update_overlay_callback(True, Source.REFRESH),
            text="Refresh Log",
        )

        self.separator_frame_draft = Separator(self.root, orient="horizontal")
        self.status_frame = tkinter.Frame(self.root)
        self.pack_pick_label = Label(
            self.status_frame, text="Pack 0, Pick 0", style="MainSectionsBold.TLabel"
        )
        self.pack_pick_label.pack(side=tkinter.LEFT, padx=5)

        self.copy_pack_button = Button(
            self.status_frame,
            text="Copy Data",
            command=self.__copy_pack_data,
        )
        self.copy_pack_button.pack(side=tkinter.RIGHT, padx=5)

        self.pack_table_frame = tkinter.Frame(self.root, width=10)

        headers = {
            "Column1": {"width": 0.46, "anchor": tkinter.W},
            "Column2": {"width": 0.18, "anchor": tkinter.CENTER},
            "Column3": {"width": 0.18, "anchor": tkinter.CENTER},
            "Column4": {"width": 0.18, "anchor": tkinter.CENTER},
            "Column5": {"width": 0.18, "anchor": tkinter.CENTER},
            "Column6": {"width": 0.18, "anchor": tkinter.CENTER},
            "Column7": {"width": 0.18, "anchor": tkinter.CENTER},
        }

        self.pack_table = self._create_header(
            "pack_table",
            self.pack_table_frame,
            0,
            self.fonts_dict["All.TableRow"],
            headers,
            self.table_width,
            True,
            True,
            constants.TABLE_STYLE,
            False,
        )

        self.missing_frame = tkinter.Frame(self.root)
        self.missing_cards_label = Label(
            self.missing_frame, text="Missing Cards", style="MainSectionsBold.TLabel"
        )

        self.missing_table_frame = tkinter.Frame(self.root, width=10)

        self.missing_table = self._create_header(
            "missing_table",
            self.missing_table_frame,
            0,
            self.fonts_dict["All.TableRow"],
            headers,
            self.table_width,
            True,
            True,
            constants.TABLE_STYLE,
            False,
        )

        self.stat_frame = tkinter.Frame(self.root)

        self.stat_table = self._create_header(
            "stat_table",
            self.root,
            0,
            self.fonts_dict["All.TableRow"],
            constants.STATS_HEADER_CONFIG,
            self.table_width,
            True,
            True,
            constants.TABLE_STYLE,
            False,
        )
        self.stat_label = Label(
            self.stat_frame,
            text="Draft Stats:",
            style="MainSectionsBold.TLabel",
            anchor="e",
            width=15,
        )

        self.stat_options_selection = tkinter.StringVar(self.root)
        self.stat_options_list = [
            constants.CARD_TYPE_SELECTION_CREATURES,
            constants.CARD_TYPE_SELECTION_NONCREATURES,
            constants.CARD_TYPE_SELECTION_ALL,
        ]

        self.stat_options = OptionMenu(
            self.stat_frame,
            self.stat_options_selection,
            self.stat_options_list[0],
            *self.stat_options_list,
            style="All.TMenubutton",
        )

        menu = self.root.nametowidget(self.stat_options["menu"])
        menu.config(font=self.fonts_dict["All.TMenubutton"])

        self.signal_frame = tkinter.Frame(self.root)
        self.signal_label = Label(
            self.signal_frame, text="Signals (P1/P3)", style="MainSectionsBold.TLabel"
        )

        signal_headers = {
            "COLOR": {"width": 0.50, "anchor": tkinter.W},
            "SCORE": {"width": 0.50, "anchor": tkinter.CENTER},
        }
        self.signal_table = self._create_header(
            "signal_table",
            self.signal_frame,
            0,
            self.fonts_dict["All.TableRow"],
            signal_headers,
            self.table_width,
            True,
            True,
            constants.TABLE_STYLE,
            False,
        )

        self.separator_frame_citation = Separator(self.root, orient="horizontal")
        title_label = Label(
            self.root, text="MTGA Draft 17Lands", style="MainSectionsBold.TLabel"
        )

        footnote_label = Label(
            self.root,
            text="Not endorsed by 17Lands",
            style="Notes.TLabel",
            anchor="e",
        )

        # UI Spacing Modernization
        row_padding = (self._scale_value(6), self._scale_value(6))
        col_padding = (self._scale_value(10), self._scale_value(10))

        title_label.grid(row=0, column=0, columnspan=2, pady=(10, 5))
        self.separator_frame_citation.grid(
            row=1, column=0, columnspan=2, sticky="nsew", pady=row_padding, padx=col_padding
        )

        self.current_draft_label_frame.grid(
            row=2, column=0, columnspan=1, sticky="nsew", pady=row_padding, padx=col_padding
        )
        self.current_draft_value_frame.grid(
            row=2, column=1, columnspan=1, sticky="nsew", padx=(0, 10)
        )

        self.data_source_label_frame.grid(
            row=4, column=0, columnspan=1, sticky="nsew", pady=row_padding, padx=col_padding
        )
        self.data_source_option_frame.grid(row=4, column=1, columnspan=1, sticky="nsew", padx=(0, 10))

        self.deck_colors_label_frame.grid(
            row=6, column=0, columnspan=1, sticky="nsew", pady=row_padding, padx=col_padding
        )
        self.deck_colors_option_frame.grid(row=6, column=1, columnspan=1, sticky="nsw", padx=(0, 10))

        self.separator_frame_draft.grid(
            row=7, column=0, columnspan=2, sticky="nsew", pady=row_padding, padx=col_padding
        )

        self.refresh_button_frame.grid(row=8, column=0, columnspan=2, sticky="nsew", padx=col_padding)

        self.status_frame.grid(row=9, column=0, columnspan=2, sticky="nsew", padx=col_padding)
        self.pack_table_frame.grid(row=10, column=0, columnspan=2, padx=col_padding, pady=(0, 10))
        self.missing_frame.grid(row=11, column=0, columnspan=2, sticky="nsew", padx=col_padding)
        self.missing_table_frame.grid(row=12, column=0, columnspan=2, padx=col_padding, pady=(0, 10))
        self.stat_frame.grid(row=13, column=0, columnspan=2, sticky="nsew", padx=col_padding)
        self.stat_table.grid(row=14, column=0, columnspan=2, sticky="nsew", padx=col_padding, pady=(0, 10))

        self.signal_frame.grid(row=15, column=0, columnspan=2, sticky="nsew", padx=col_padding)
        self.signal_label.pack(anchor="w")
        self.signal_table.pack(expand=True, fill="both")

        footnote_label.grid(row=16, column=0, columnspan=2, pady=5)

        self.refresh_button.pack(expand=True, fill="both")

        self.pack_table.pack(expand=True, fill="both")
        self.missing_cards_label.pack(expand=False, fill=None)
        self.missing_table.pack(expand=True, fill="both")
        self.stat_label.pack(side=tkinter.LEFT, expand=True, fill=None)
        self.stat_options.pack(side=tkinter.RIGHT, expand=True, fill=None)
        self.current_draft_label.pack(expand=True, fill=None, anchor="e")
        self.current_draft_value_label.pack(expand=True, fill=None, anchor="w")
        self.data_source_label.pack(expand=True, fill=None, anchor="e")
        self.data_source_options.pack(expand=True, fill=None, anchor="w")
        self.deck_colors_label.pack(expand=True, fill=None, anchor="e")
        self.deck_colors_options.pack(expand=True, fill=None, anchor="w")
        
        self.current_timestamp = 0
        self.previous_timestamp = 0
        self.log_check_id = None

        self.__update_settings_data()
        self.__update_overlay_callback(False)

        self.root.attributes("-topmost", True)
        self.__initialize_overlay_widgets()
        self.notifications = Notifications(
            self.root,
            self.limited_sets,
            self.configuration,
            DownloadDatasetWindow(
                self.root,
                self.limited_sets,
                self.scale_factor,
                self.fonts_dict,
                self.configuration,
                False,
                self.__update_event_files_callback,
            ),
        )
        if self.notifications.check_for_updates():
            self.__arena_log_check()
            self.__control_trace(True)

        if self.configuration.features.hotkey_enabled:
            self.__start_hotkey_listener()

    def __copy_pack_data(self):
        """Copy the current pack table data to clipboard as CSV"""
        try:
            pack_cards = self.draft.retrieve_current_pack_cards()
            if pack_cards:
                csv_text = copy_pack_to_clipboard(pack_cards)
                copy_clipboard(csv_text)
        except Exception as error:
            logger.error(error)

    def close_overlay(self):
        if self.log_check_id is not None:
            self.root.after_cancel(self.log_check_id)
            self.log_check_id = None
        self.root.destroy()

    def lift_window(self):
        """Function that's used to minimize a window or set it as the top most window"""
        if self.root.state() == "iconic":
            self.root.deiconify()
            self.root.lift()
            self.root.attributes("-topmost", True)
        else:
            self.root.attributes("-topmost", False)
            self.root.iconify()

    def main_loop(self):
        """Run the TKinter overlay"""
        self.root.mainloop()

    def __set_os_configuration(self):
        """Modernizes the UI and fixes macOS header colors."""
        p = sys.platform
        style = Style()
        if p == "darwin":
            style.theme_use('clam')
        else:
            self.root.call("source", "dark_mode.tcl")
            
        uf = "Segoe UI" if p == "win32" else (".AppleSystemUIFont" if p == "darwin" else "Helvetica")
        self.fonts_dict = {
            "All.TableRow": self._scale_value(-12), 
            "Sets.TableRow": self._scale_value(-13), 
            "All.TMenubutton": (uf, self._scale_value(-12))
        }

        # Modern Muted Colors
        bg_color = "#2b2b2b"
        self.root.configure(background=bg_color)
        
        style.configure("Treeview", 
                        rowheight=self._scale_value(30), 
                        font=(uf, self._scale_value(-12)),
                        background="#333333", foreground="white", fieldbackground="#333333", borderwidth=0)
        
        # Dark Readable Headers
        style.configure("Treeview.Heading", 
                        background="#1e1e1e", foreground="white", 
                        font=(uf, self._scale_value(-11), "bold"), borderwidth=1, relief="flat")

        style.map("Treeview.Heading",
                  background=[('active', '#333333'), ('!active', '#1e1e1e')],
                  foreground=[('active', '#007fff'), ('!active', 'white')])

        style.configure("MainSectionsBold.TLabel", font=(uf, self._scale_value(-13), "bold"), background=bg_color, foreground="white")
        style.configure("CurrentDraft.TLabel", font=(uf, self._scale_value(-13)), background=bg_color, foreground="#007fff")
        style.configure("TCheckbutton", background=bg_color, foreground="white")
    
    def _identify_table_row_tag(self, colors_enabled, colors, index):
        """Standardized tag creation to use our new modern color palette."""
        tag = ""
        if colors_enabled:
            from src.card_logic import row_color_tag
            tag = row_color_tag(colors)
        else:
            tag = "bw_odd" if index % 2 else "bw_even"
        return tag

    def __start_hotkey_listener(self):
        """Start listener that detects the minimize hotkey"""
        self.listener = Listener(on_press=self.__process_hotkey_press).start()

    def __process_hotkey_press(self, key):
        if key == KeyCode.from_char(HOTKEY_CTRL_G):
            self.lift_window()

    def __identify_auto_colors(self, cards, selected_option):
        """Update the Deck Filter option menu when the Auto option is selected"""
        filtered_colors = [constants.FILTER_OPTION_ALL_DECKS]
        try:
            selected_color = self.deck_colors[selected_option]
            filtered_colors = filter_options(
                cards, selected_color, self.set_metrics, self.configuration
            )

            if selected_color == constants.FILTER_OPTION_AUTO:
                new_key = (
                    f"{constants.FILTER_OPTION_AUTO} ({'/'.join(filtered_colors)})"
                )
                if new_key != selected_option:
                    self.deck_colors.pop(selected_option)
                    new_dict = {new_key: constants.FILTER_OPTION_AUTO}
                    new_dict.update(self.deck_colors)
                    self.deck_colors = new_dict
                    self.__update_column_options()

        except Exception as error:
            logger.error(error)
        return filtered_colors

    def __update_pack_table(self, card_list, filtered_colors, fields):
        """Update the table that lists the cards within the current pack"""
        try:
            result_class = CardResult(
                self.set_metrics,
                self.tier_data,
                self.configuration,
                self.draft.current_pick,
            )
            result_list = result_class.return_results(
                card_list, filtered_colors, fields.values()
            )

            filtered_result_list = []
            for card in result_list:
                name = card.get(constants.DATA_FIELD_NAME, "")
                if name in constants.BASIC_LANDS or name.isdigit():
                    continue
                filtered_result_list.append(card)

            result_list = filtered_result_list

            for row in self.pack_table.get_children():
                self.pack_table.delete(row)

            if result_list:
                self.pack_table.config(height=len(result_list))
            else:
                self.pack_table.config(height=0)

            last_field_index, visible_columns = control_table_column(
                self.pack_table, fields, self.table_width
            )

            if self.table_info["pack_table"].column in visible_columns:
                column_index = visible_columns[self.table_info["pack_table"].column]
                direction = self.table_info["pack_table"].reverse
                result_list = sorted(
                    result_list,
                    key=lambda d: field_process_sort(d["results"][column_index]),
                    reverse=direction,
                )
            else:
                result_list = sorted(
                    result_list,
                    key=lambda d: field_process_sort(d["results"][last_field_index]),
                    reverse=True,
                )

            for count, card in enumerate(result_list):
                row_tag = self._identify_card_row_tag(
                    self.configuration.settings, card, count
                )
                self.pack_table.insert(
                    "", index=count, iid=count, values=tuple(card["results"]), tag=(row_tag,)
                )
            self.pack_table.bind(
                "<<TreeviewSelect>>",
                lambda event: self.__process_table_click(
                    event,
                    table=self.pack_table,
                    card_list=card_list,
                    selected_color=filtered_colors,
                    fields=fields,
                ),
            )
        except Exception as error:
            logger.error(error)

    def __update_missing_table(
        self, missing_cards, picked_cards, filtered_colors, fields
    ):
        """Update the table that lists the cards that are missing from the current pack"""
        try:
            for row in self.missing_table.get_children():
                self.missing_table.delete(row)

            last_field_index, visible_columns = control_table_column(
                self.missing_table, fields, self.table_width
            )
            if not missing_cards:
                self.missing_table.config(height=0)
            else:
                self.missing_table.config(height=len(missing_cards))
                result_class = CardResult(
                    self.set_metrics,
                    self.tier_data,
                    self.configuration,
                    self.draft.current_pick,
                )
                result_list = result_class.return_results(
                    missing_cards, filtered_colors, fields.values()
                )

                if self.table_info["missing_table"].column in visible_columns:
                    column_index = visible_columns[self.table_info["missing_table"].column]
                    direction = self.table_info["missing_table"].reverse
                    result_list = sorted(
                        result_list,
                        key=lambda d: field_process_sort(d["results"][column_index]),
                        reverse=direction,
                    )
                else:
                    result_list = sorted(
                        result_list,
                        key=lambda d: field_process_sort(d["results"][last_field_index]),
                        reverse=True,
                    )

                picked_card_names = [x[constants.DATA_FIELD_NAME] for x in picked_cards]
                for count, card in enumerate(result_list):
                    row_tag = self._identify_card_row_tag(self.configuration.settings, card, count)
                    for index, field in enumerate(fields.values()):
                        if field == constants.DATA_FIELD_NAME:
                            card["results"][index] = (
                                f'*{card["results"][index]}'
                                if card["results"][index] in picked_card_names
                                else card["results"][index]
                            )
                    self.missing_table.insert(
                        "", index=count, iid=count, values=tuple(card["results"]), tag=(row_tag,)
                    )
                self.missing_table.bind(
                    "<<TreeviewSelect>>",
                    lambda event: self.__process_table_click(
                        event,
                        table=self.missing_table,
                        card_list=missing_cards,
                        selected_color=filtered_colors,
                        fields=fields,
                    ),
                )
        except Exception as error:
            logger.error(error)

    def __clear_compare_table(self):
        self.compare_list.clear()
        self.compare_table.delete(*self.compare_table.get_children())
        self.compare_table.config(height=0)

    def __update_compare_table(self, entry_box=None):
        try:
            if self.compare_table is None or self.compare_list is None:
                return

            card_list = self.draft.set_data.get_card_ratings()
            taken_cards = self.draft.retrieve_taken_cards()
            filtered_colors = self.__identify_auto_colors(taken_cards, self.deck_filter_selection.get())
            
            fields = {
                "Column1": constants.DATA_FIELD_NAME,
                "Column2": self.main_options_dict[self.column_2_selection.get()],
                "Column3": self.main_options_dict[self.column_3_selection.get()],
                "Column4": self.main_options_dict[self.column_4_selection.get()],
                "Column5": self.main_options_dict[self.column_5_selection.get()],
                "Column6": self.main_options_dict[self.column_6_selection.get()],
                "Column7": self.main_options_dict[self.column_7_selection.get()],
            }

            if entry_box and card_list:
                added_card = entry_box.get()
                if added_card:
                    cards = [
                        card_list[x] for x in card_list
                        if card_list[x][constants.DATA_FIELD_NAME] == added_card
                        and card_list[x] not in self.compare_list
                    ]
                    entry_box.delete(0, tkinter.END)
                    if cards:
                        self.compare_list.append(cards[0])

            result_class = CardResult(self.set_metrics, self.tier_data, self.configuration, self.draft.current_pick)
            result_list = result_class.return_results(self.compare_list, filtered_colors, fields.values())

            self.compare_table.delete(*self.compare_table.get_children())
            last_field_index, visible_columns = control_table_column(self.compare_table, fields, self.table_width)

            if self.table_info["compare_table"].column in visible_columns:
                column_index = visible_columns[self.table_info["compare_table"].column]
                direction = self.table_info["compare_table"].reverse
                result_list = sorted(result_list, key=lambda d: field_process_sort(d["results"][column_index]), reverse=direction)
            else:
                result_list = sorted(result_list, key=lambda d: field_process_sort(d["results"][last_field_index]), reverse=True)

            self.compare_table.config(height=len(result_list) if result_list else 0)

            for count, card in enumerate(result_list):
                row_tag = self._identify_card_row_tag(self.configuration.settings, card, count)
                self.compare_table.insert("", index=count, iid=count, values=tuple(card["results"]), tag=(row_tag,))
                
            self.compare_table.bind("<<TreeviewSelect>>", lambda event: self.__process_table_click(event, self.compare_table, self.compare_list, filtered_colors, fields))
        except Exception as error:
            logger.error(error)

    def __update_taken_table(self, *_):
        try:
            if self.taken_table is None:
                return

            fields = {
                "Column1": constants.DATA_FIELD_NAME,
                "Column2": constants.DATA_FIELD_COUNT,
                "Column3": constants.DATA_FIELD_COLORS,
                "Column4": (constants.DATA_FIELD_ALSA if self.taken_alsa_checkbox_value.get() else constants.DATA_FIELD_DISABLED),
                "Column5": (constants.DATA_FIELD_ATA if self.taken_ata_checkbox_value.get() else constants.DATA_FIELD_DISABLED),
                "Column6": (constants.DATA_FIELD_IWD if self.taken_iwd_checkbox_value.get() else constants.DATA_FIELD_DISABLED),
                "Column7": (constants.DATA_FIELD_GPWR if self.taken_gpwr_checkbox_value.get() else constants.DATA_FIELD_DISABLED),
                "Column8": (constants.DATA_FIELD_OHWR if self.taken_ohwr_checkbox_value.get() else constants.DATA_FIELD_DISABLED),
                "Column9": (constants.DATA_FIELD_GDWR if self.taken_gdwr_checkbox_value.get() else constants.DATA_FIELD_DISABLED),
                "Column10": (constants.DATA_FIELD_GNSWR if self.taken_gndwr_checkbox_value.get() else constants.DATA_FIELD_DISABLED),
                "Column11": constants.DATA_FIELD_GIHWR,
            }

            taken_cards = self.draft.retrieve_taken_cards()
            filtered_colors = self.__identify_auto_colors(taken_cards, self.taken_filter_selection.get())

            if not (self.taken_type_creature_checkbox_value.get() and self.taken_type_land_checkbox_value.get() and self.taken_type_instant_sorcery_checkbox_value.get() and self.taken_type_other_checkbox_value.get()):
                card_types = []
                if self.taken_type_creature_checkbox_value.get(): card_types.append(constants.CARD_TYPE_CREATURE)
                if self.taken_type_land_checkbox_value.get(): card_types.append(constants.CARD_TYPE_LAND)
                if self.taken_type_instant_sorcery_checkbox_value.get(): card_types.extend([constants.CARD_TYPE_INSTANT, constants.CARD_TYPE_SORCERY])
                if self.taken_type_other_checkbox_value.get(): card_types.extend([constants.CARD_TYPE_ARTIFACT, constants.CARD_TYPE_ENCHANTMENT, constants.CARD_TYPE_PLANESWALKER])
                taken_cards = deck_card_search(taken_cards, constants.CARD_COLORS, card_types, True, True, True)

            stacked_cards = stack_cards(taken_cards)
            for row in self.taken_table.get_children(): self.taken_table.delete(row)

            result_class = CardResult(self.set_metrics, self.tier_data, self.configuration, self.draft.current_pick)
            result_list = result_class.return_results(stacked_cards, filtered_colors, fields.values())

            last_field_index, visible_columns = control_table_column(self.taken_table, fields)

            if self.table_info["taken_table"].column in visible_columns:
                column_index = visible_columns[self.table_info["taken_table"].column]
                direction = self.table_info["taken_table"].reverse
                result_list = sorted(result_list, key=lambda d: field_process_sort(d["results"][column_index]), reverse=direction)
            else:
                result_list = sorted(result_list, key=lambda d: field_process_sort(d["results"][last_field_index]), reverse=True)

            self.taken_table.config(height=min(len(result_list), 20) if result_list else 1)

            for count, card in enumerate(result_list):
                row_tag = self._identify_card_row_tag(self.configuration.settings, card, count)
                self.taken_table.insert("", index=count, iid=count, values=tuple(card["results"]), tag=(row_tag,))
            
            self.taken_table.bind("<<TreeviewSelect>>", lambda event: self.__process_table_click(event, self.taken_table, result_list, filtered_colors))
        except Exception as error:
            logger.error(error)

    def __update_suggest_table(self, selected_color, suggested_decks, color_options):
        try:
            if not self.suggester_table: return
            color = color_options[selected_color.get()]
            suggested_deck = suggested_decks[color]["deck_cards"]
            suggested_deck.sort(key=lambda x: x[constants.DATA_FIELD_CMC])
            for row in self.suggester_table.get_children(): self.suggester_table.delete(row)
            self.suggester_table.config(height=len(suggested_deck) if suggested_deck else 0)

            for count, card in enumerate(suggested_deck):
                row_tag = self._identify_card_row_tag(self.configuration.settings, card, count)
                card_colors = "".join(card[constants.DATA_FIELD_COLORS] if constants.CARD_TYPE_LAND in card[constants.DATA_FIELD_TYPES] or self.configuration.settings.color_identity_enabled else list(get_card_colors(card[constants.DATA_FIELD_MANA_COST]).keys()))
                self.suggester_table.insert("", index=count, values=(card[constants.DATA_FIELD_NAME], f"{card[constants.DATA_FIELD_COUNT]}", card_colors, card[constants.DATA_FIELD_CMC], card[constants.DATA_FIELD_TYPES]), tag=(row_tag,))
            self.suggester_table.bind("<<TreeviewSelect>>", lambda event: self.__process_table_click(event, self.suggester_table, suggested_deck, [color]))
        except Exception as error:
            logger.error(error)

    def __update_deck_stats_table(self, taken_cards, filter_type, total_width):
        try:
            card_types = constants.CARD_TYPE_DICT[filter_type]
            colors_filtered = {}
            for color, symbol in constants.CARD_COLORS_DICT.items():
                if symbol:
                    card_colors_sorted = deck_card_search(taken_cards, symbol, card_types[0], card_types[1], card_types[2], card_types[3])
                else:
                    card_colors_sorted = deck_card_search(taken_cards, symbol, card_types[0], card_types[1], True, False)
                card_metrics = get_deck_metrics(card_colors_sorted)
                colors_filtered[color] = {"symbol": symbol, "total": card_metrics.total_cards, "distribution": card_metrics.distribution_all}

            colors_filtered = dict(sorted(colors_filtered.items(), key=lambda item: item[1]["total"], reverse=True))
            for row in self.stat_table.get_children(): self.stat_table.delete(row)

            if total_width == 1:
                self.stat_table.config(height=0)
                toggle_widget(self.stat_frame, False)
                toggle_widget(self.stat_table, False)
                return

            width = total_width - 5
            for column in self.stat_table["columns"]:
                column_width = min(int(math.ceil(constants.STATS_HEADER_CONFIG[column]["width"] * total_width)), width)
                width -= column_width
                self.stat_table.column(column, width=column_width)

            self.stat_table.config(height=len(colors_filtered) if colors_filtered else 0)
            for count, (color, values) in enumerate(colors_filtered.items()):
                row_tag = self._identify_table_row_tag(self.configuration.settings.card_colors_enabled, values["symbol"], count)
                self.stat_table.insert("", index=count, values=(color, values["distribution"][1], values["distribution"][2], values["distribution"][3], values["distribution"][4], values["distribution"][5], values["distribution"][6], values["total"]), tag=(row_tag,))
        except Exception as error:
            logger.error(error)

    def __update_pack_pick_label(self, pack, pick):
        try:
            self.pack_pick_label.config(text=f"Pack {pack} / Pick {pick}")
        except Exception as error:
            logger.error(error)

    def __update_current_draft_label(self, event_set, event_type):
        try:
            self.current_draft_value_label.config(text=f" {event_set} {event_type}" if event_set and event_type else " None")
        except Exception as error:
            logger.error(error)

    def __update_data_source_options(self, new_list):
        self.__control_trace(False)
        try:
            if new_list:
                self.data_source_selection.set(next(iter(self.data_sources)))
                menu = self.data_source_options["menu"]
                menu.delete(0, "end")
                self.data_source_list = []
                for key in self.data_sources:
                    menu.add_command(label=key, command=lambda value=key: self.data_source_selection.set(value))
                    self.data_source_list.append(key)
            elif self.data_source_selection.get() not in self.data_sources:
                self.data_source_selection.set(next(iter(self.data_sources)))
        except Exception as error:
            logger.error(error)
        self.__control_trace(True)

    def __update_column_options(self):
        self.__control_trace(False)
        try:
            # Dropdown validation logic
            for sel, lst, dflt in [
                (self.filter_format_selection, self.filter_format_list, constants.DECK_FILTER_FORMAT_COLORS),
                (self.result_format_selection, self.result_format_list, constants.RESULT_FORMAT_WIN_RATE),
                (self.ui_size_selection, self.ui_size_list, constants.UI_SIZE_DEFAULT),
                (self.column_2_selection, self.main_options_dict, constants.COLUMN_2_DEFAULT),
                (self.column_3_selection, self.main_options_dict, constants.COLUMN_3_DEFAULT),
                (self.column_4_selection, self.main_options_dict, constants.COLUMN_4_DEFAULT),
                (self.column_5_selection, self.main_options_dict, constants.COLUMN_5_DEFAULT),
                (self.column_6_selection, self.main_options_dict, constants.COLUMN_6_DEFAULT),
                (self.column_7_selection, self.main_options_dict, constants.COLUMN_7_DEFAULT),
            ]:
                if sel.get() not in lst: sel.set(dflt)

            if self.deck_filter_selection.get() not in self.deck_colors:
                selection = [k for k, v in self.deck_colors.items() if v == self.configuration.settings.deck_filter]
                self.deck_filter_selection.set(selection[0] if selection else constants.DECK_FILTER_DEFAULT)

            if self.taken_filter_selection.get() not in self.deck_colors:
                selection = [k for k in self.deck_colors.keys() if constants.DECK_FILTER_DEFAULT in k]
                self.taken_filter_selection.set(selection[0] if selection else constants.DECK_FILTER_DEFAULT)
            
            if self.taken_type_selection.get() not in constants.CARD_TYPE_DICT:
                self.taken_type_selection.set(constants.CARD_TYPE_SELECTION_ALL)

            # Re-populating dropdown menus
            for menu_widget, menu_list, menu_var in [
                (self.deck_colors_options, self.deck_colors, self.deck_filter_selection),
                (self.column_2_options, self.main_options_dict, self.column_2_selection),
                (self.column_3_options, self.main_options_dict, self.column_3_selection),
                (self.column_4_options, self.main_options_dict, self.column_4_selection),
                (self.column_5_options, self.main_options_dict, self.column_5_selection),
                (self.column_6_options, self.main_options_dict, self.column_6_selection),
                (self.column_7_options, self.main_options_dict, self.column_7_selection),
            ]:
                if menu_widget:
                    m = menu_widget["menu"]
                    m.delete(0, "end")
                    for k in menu_list:
                        m.add_command(label=k, command=lambda v=k, mv=menu_var: mv.set(v))

        except Exception as error:
            logger.error(error)
        self.__control_trace(True)

    def __default_settings_callback(self, *_):
        reset_configuration()
        self.configuration, _ = read_configuration()
        self.__update_settings_data()
        self.__update_draft_data()
        self.__update_overlay_callback(False)

    def __update_source_callback(self, *_):
        self.__update_settings_storage()
        self.__update_draft_data()
        self.__update_settings_data()
        self.__update_overlay_callback(False)

    def __update_settings_callback(self, *_):
        self.__update_settings_storage()
        self.__update_settings_data()
        self.__update_overlay_callback(False)

    def __ui_size_callback(self, *_):
        self.__update_settings_storage()
        self.__update_settings_data()
        if tkinter.messagebox.askyesno("Restart", "Restart required for this setting. Restart now?"):
            restart_overlay(self)

    def __update_draft_data(self):
        dataset_location = self.data_sources[self.data_source_selection.get()]
        self.draft.retrieve_set_data(dataset_location)
        self.set_metrics = self.draft.retrieve_set_metrics()
        self.deck_colors = self.draft.retrieve_color_win_rate(self.filter_format_selection.get())
        event_set, event_type = self.draft.retrieve_current_limited_event()
        self.tier_data, tier_dict = self.tier_list.retrieve_data(event_set)
        self.main_options_dict = constants.COLUMNS_OPTIONS_EXTRA_DICT.copy()
        self.notifications.update_latest_dataset(dataset_location)
        for key, value in tier_dict.items(): self.main_options_dict[key] = value
        if self.configuration.settings.missing_notifications_enabled:
            self.notifications.check_for_missing_dataset(event_set, event_type)

    def __update_draft(self, source):
        update = False
        if self.draft.draft_start_search():
            update = True
            self.data_sources = self.draft.retrieve_data_sources()
            self.__update_data_source_options(True)
            self.__update_draft_data()

        use_ocr = (source == Source.REFRESH and self.configuration.settings.p1p1_ocr_enabled)
        if self.draft.draft_data_search(use_ocr, self.configuration.settings.save_screenshot_enabled):
            update = True
        return update

    def __update_settings_storage(self):
        """Ensure all UI values are mapped back to config object"""
        try:
            s = self.configuration.settings
            s.column_2 = self.main_options_dict.get(self.column_2_selection.get(), constants.COLUMN_2_DEFAULT)
            s.column_3 = self.main_options_dict.get(self.column_3_selection.get(), constants.COLUMN_3_DEFAULT)
            s.column_4 = self.main_options_dict.get(self.column_4_selection.get(), constants.COLUMN_4_DEFAULT)
            s.column_5 = self.main_options_dict.get(self.column_5_selection.get(), constants.COLUMN_5_DEFAULT)
            s.column_6 = self.main_options_dict.get(self.column_6_selection.get(), constants.COLUMN_6_DEFAULT)
            s.column_7 = self.main_options_dict.get(self.column_7_selection.get(), constants.COLUMN_7_DEFAULT)
            
            s.deck_filter = self.deck_colors.get(self.deck_filter_selection.get(), constants.DECK_FILTER_DEFAULT)
            s.filter_format = self.filter_format_selection.get()
            s.result_format = self.result_format_selection.get()
            s.ui_size = self.ui_size_selection.get()

            s.missing_enabled = bool(self.missing_cards_checkbox_value.get())
            s.stats_enabled = bool(self.deck_stats_checkbox_value.get())
            s.signals_enabled = bool(self.signals_checkbox_value.get())
            s.auto_highest_enabled = bool(self.auto_highest_checkbox_value.get())
            s.curve_bonus_enabled = bool(self.curve_bonus_checkbox_value.get())
            s.color_bonus_enabled = bool(self.color_bonus_checkbox_value.get())
            s.color_identity_enabled = bool(self.color_identity_checkbox_value.get())
            s.draft_log_enabled = bool(self.draft_log_checkbox_value.get())
            s.p1p1_ocr_enabled = bool(self.p1p1_ocr_checkbox_value.get())
            s.save_screenshot_enabled = bool(self.save_screenshot_checkbox_value.get())
            s.card_colors_enabled = bool(self.card_colors_checkbox_value.get())
            s.current_draft_enabled = bool(self.current_draft_checkbox_value.get())
            s.data_source_enabled = bool(self.data_source_checkbox_value.get())
            s.deck_filter_enabled = bool(self.deck_filter_checkbox_value.get())
            s.refresh_button_enabled = bool(self.refresh_button_checkbox_value.get())
            s.update_notifications_enabled = bool(self.update_notifications_checkbox_value.get())
            s.missing_notifications_enabled = bool(self.missing_notifications_checkbox_value.get())
            
            # Taken window persistent columns
            s.taken_alsa_enabled = bool(self.taken_alsa_checkbox_value.get())
            s.taken_ata_enabled = bool(self.taken_ata_checkbox_value.get())
            s.taken_gpwr_enabled = bool(self.taken_gpwr_checkbox_value.get())
            s.taken_ohwr_enabled = bool(self.taken_ohwr_checkbox_value.get())
            s.taken_iwd_enabled = bool(self.taken_iwd_checkbox_value.get())
            s.taken_gndwr_enabled = bool(self.taken_gndwr_checkbox_value.get())
            s.taken_gdwr_enabled = bool(self.taken_gdwr_checkbox_value.get())
            s.taken_wheel_enabled = bool(self.taken_wheel_checkbox_value.get())

            write_configuration(self.configuration)
        except Exception as error:
            logger.error(error)

    def __update_settings_data(self):
        """Ensure all config values are mapped to UI variables"""
        self.__control_trace(False)
        try:
            s = self.configuration.settings
            
            # Helper to find key from value
            def find_key(dct, val):
                return next((k for k, v in dct.items() if v == val), None)

            self.column_2_selection.set(find_key(self.main_options_dict, s.column_2) or constants.COLUMN_2_DEFAULT)
            self.column_3_selection.set(find_key(self.main_options_dict, s.column_3) or constants.COLUMN_3_DEFAULT)
            self.column_4_selection.set(find_key(self.main_options_dict, s.column_4) or constants.COLUMN_4_DEFAULT)
            self.column_5_selection.set(find_key(self.main_options_dict, s.column_5) or constants.COLUMN_5_DEFAULT)
            self.column_6_selection.set(find_key(self.main_options_dict, s.column_6) or constants.COLUMN_6_DEFAULT)
            self.column_7_selection.set(find_key(self.main_options_dict, s.column_7) or constants.COLUMN_7_DEFAULT)
            
            self.deck_filter_selection.set(find_key(self.deck_colors, s.deck_filter) or constants.DECK_FILTER_DEFAULT)
            self.filter_format_selection.set(s.filter_format)
            self.result_format_selection.set(s.result_format)
            self.ui_size_selection.set(s.ui_size)
            
            self.deck_stats_checkbox_value.set(int(s.stats_enabled))
            self.signals_checkbox_value.set(int(s.signals_enabled))
            self.missing_cards_checkbox_value.set(int(s.missing_enabled))
            self.auto_highest_checkbox_value.set(int(s.auto_highest_enabled))
            self.curve_bonus_checkbox_value.set(int(s.curve_bonus_enabled))
            self.color_bonus_checkbox_value.set(int(s.color_bonus_enabled))
            self.color_identity_checkbox_value.set(int(s.color_identity_enabled))
            self.draft_log_checkbox_value.set(int(s.draft_log_enabled))
            self.p1p1_ocr_checkbox_value.set(int(s.p1p1_ocr_enabled))
            self.save_screenshot_checkbox_value.set(int(s.save_screenshot_enabled))
            self.card_colors_checkbox_value.set(int(s.card_colors_enabled))
            self.current_draft_checkbox_value.set(int(s.current_draft_enabled))
            self.data_source_checkbox_value.set(int(s.data_source_enabled))
            self.deck_filter_checkbox_value.set(int(s.deck_filter_enabled))
            self.refresh_button_checkbox_value.set(int(s.refresh_button_enabled))
            self.update_notifications_checkbox_value.set(int(s.update_notifications_enabled))
            self.missing_notifications_checkbox_value.set(int(s.missing_notifications_enabled))
            
            # Persistent columns for Taken window
            self.taken_alsa_checkbox_value.set(int(s.taken_alsa_enabled))
            self.taken_ata_checkbox_value.set(int(s.taken_ata_enabled))
            self.taken_gpwr_checkbox_value.set(int(s.taken_gpwr_enabled))
            self.taken_ohwr_checkbox_value.set(int(s.taken_ohwr_enabled))
            self.taken_gdwr_checkbox_value.set(int(s.taken_gdwr_enabled))
            self.taken_gndwr_checkbox_value.set(int(s.taken_gndwr_enabled))
            self.taken_iwd_checkbox_value.set(int(s.taken_iwd_enabled))
            self.taken_wheel_checkbox_value.set(int(s.taken_wheel_enabled))

        except Exception as error:
            logger.error(error)
        self.__control_trace(True)
        if not self.step_through:
            self.draft.log_enable(self.configuration.settings.draft_log_enabled)

    def __update_signals(self):
        try:
            if not self.draft.retrieve_draft_history() or not self.set_metrics:
                self.signal_table.config(height=0)
                for row in self.signal_table.get_children(): self.signal_table.delete(row)
                return

            history = self.draft.retrieve_draft_history()
            calculator = SignalCalculator(self.set_metrics)
            total_scores = {c: 0.0 for c in constants.CARD_COLORS}

            for entry in history:
                if entry["Pack"] == 2: continue
                cards = self.draft.set_data.get_data_by_id(entry["Cards"])
                scores = calculator.calculate_pack_signals(cards, entry["Pick"])
                for color, score in scores.items(): total_scores[color] += score

            for row in self.signal_table.get_children(): self.signal_table.delete(row)
            sorted_scores = sorted(total_scores.items(), key=lambda x: x[1], reverse=True)
            self.signal_table.config(height=5)
            symbol_to_name = {v: k for k, v in constants.CARD_COLORS_DICT.items() if v in constants.CARD_COLORS}

            for count, (color, score) in enumerate(sorted_scores):
                row_tag = self._identify_table_row_tag(self.configuration.settings.card_colors_enabled, [color], count)
                self.signal_table.insert("", index=count, values=(symbol_to_name.get(color, color), f"{score:.1f}"), tag=(row_tag,))
        except Exception as error:
            logger.error(error)

    def __initialize_overlay_widgets(self):
        self.__update_data_source_options(False)
        self.__update_column_options()
        self.filemenu.add_separator()
        self.filemenu.add_command(label="Export Draft (CSV)", command=self.__export_csv, state="disabled")
        self.filemenu.add_command(label="Export Draft (JSON)", command=self.__export_json, state="disabled")
        self.__display_widgets()
        current_pack, current_pick = self.draft.retrieve_current_pack_and_pick()
        event_set, event_type = self.draft.retrieve_current_limited_event()
        self.__update_current_draft_label(event_set, event_type)
        self.__update_pack_pick_label(current_pack, current_pick)
        fields = {"Column1": constants.DATA_FIELD_NAME, "Column2": self.main_options_dict[self.column_2_selection.get()], "Column3": self.main_options_dict[self.column_3_selection.get()], "Column4": self.main_options_dict[self.column_4_selection.get()], "Column5": self.main_options_dict[self.column_5_selection.get()], "Column6": self.main_options_dict[self.column_6_selection.get()], "Column7": self.main_options_dict[self.column_7_selection.get()]}
        self.__update_pack_table([], self.deck_filter_selection.get(), fields)
        self.__update_missing_table([], {}, self.deck_filter_selection.get(), fields)
        self.__update_deck_stats_callback()
        self.__update_signals()
        self.root.update()

    def __update_overlay_callback(self, enable_draft_search, source=Source.UPDATE):
        update = True
        if enable_draft_search: update = self.__update_draft(source)
        if not update: return
        self.__update_data_source_options(False)
        self.__update_column_options()
        self.__display_widgets()
        taken_cards = self.draft.retrieve_taken_cards()
        filtered = self.__identify_auto_colors(taken_cards, self.deck_filter_selection.get())
        fields = {"Column1": constants.DATA_FIELD_NAME, "Column2": self.main_options_dict[self.column_2_selection.get()], "Column3": self.main_options_dict[self.column_3_selection.get()], "Column4": self.main_options_dict[self.column_4_selection.get()], "Column5": self.main_options_dict[self.column_5_selection.get()], "Column6": self.main_options_dict[self.column_6_selection.get()], "Column7": self.main_options_dict[self.column_7_selection.get()]}
        current_pack, current_pick = self.draft.retrieve_current_pack_and_pick()
        event_set, event_type = self.draft.retrieve_current_limited_event()
        self.__update_current_draft_label(event_set, event_type)
        self.__update_pack_pick_label(current_pack, current_pick)
        self.__update_pack_table(self.draft.retrieve_current_pack_cards(), filtered, fields)
        self.__update_missing_table(self.draft.retrieve_current_missing_cards(), self.draft.retrieve_current_picked_cards(), filtered, fields)
        self.__update_deck_stats_callback()
        self.__update_taken_table()
        self.__update_compare_table()
        self.__update_signals()
        self.__update_file_menu_state()
        if event_type in [constants.LIMITED_TYPE_STRING_SEALED, constants.LIMITED_TYPE_STRING_TRAD_SEALED]: self.__open_taken_cards_window()

    def __update_file_menu_state(self):
        state = "normal" if self.draft.retrieve_draft_history() else "disabled"
        try:
            self.filemenu.entryconfig(4, state=state)
            self.filemenu.entryconfig(5, state=state)
        except: pass

    def __export_csv(self):
        history = self.draft.retrieve_draft_history()
        if history:
            data = export_draft_to_csv(history, self.draft.set_data, self.draft.picked_cards)
            f = filedialog.asksaveasfile(mode="w", defaultextension=".csv", filetypes=[("CSV Files", "*.csv")])
            if f: f.write(data); f.close()

    def __export_json(self):
        history = self.draft.retrieve_draft_history()
        if history:
            data = export_draft_to_json(history, self.draft.set_data, self.draft.picked_cards)
            f = filedialog.asksaveasfile(mode="w", defaultextension=".json", filetypes=[("JSON Files", "*.json")])
            if f: f.write(data); f.close()

    def __update_deck_stats_callback(self, *_):
        self.root.update_idletasks()
        self.__update_deck_stats_table(self.draft.retrieve_taken_cards(), self.stat_options_selection.get(), self.pack_table.winfo_width())

    def __arena_log_check(self):
        """Update Log Reading: UI Status Dot updates color based on activity"""
        try:
            self.current_timestamp = stat(self.arena_file).st_mtime
            if self.current_timestamp != self.previous_timestamp:
                self.previous_timestamp = self.current_timestamp
                # Success: Modern Green
                self.status_dot.config(foreground="#2ec27e")
                self.__update_overlay_callback(True)
        except Exception as error:
            # Error: Modern Red
            self.status_dot.config(foreground="#ed333b")
            logger.error(error)
            self.__reset_draft(True)

        self.log_check_id = self.root.after(1000, self.__arena_log_check)

    def __close_card_compare_window(self, popup):
        self.compare_table = None
        self.compare_list = None
        popup.destroy()

    def __open_card_compare_window(self):
        if self.compare_table: return
        popup = tkinter.Toplevel()
        popup.wm_title("Compare Cards")
        popup.resizable(width=False, height=True)
        popup.attributes("-topmost", True)
        location_x, location_y = identify_safe_coordinates(self.root, self._scale_value(400), self._scale_value(170), self._scale_value(250), 0)
        popup.wm_geometry(f"+{location_x}+{location_y}")
        popup.protocol("WM_DELETE_WINDOW", lambda window=popup: self.__close_card_compare_window(window))
        
        tkinter.Grid.rowconfigure(popup, 2, weight=1)
        tkinter.Grid.columnconfigure(popup, 0, weight=1)
        self.compare_list = []
        card_frame = tkinter.Frame(popup)
        set_data = self.draft.set_data.get_card_ratings()
        set_card_names = [v[constants.DATA_FIELD_NAME] for k, v in set_data.items()] if set_data else []
        headers = {"Column1": {"width": 0.46, "anchor": tkinter.W}, "Column2": {"width": 0.18, "anchor": tkinter.CENTER}, "Column3": {"width": 0.18, "anchor": tkinter.CENTER}, "Column4": {"width": 0.18, "anchor": tkinter.CENTER}, "Column5": {"width": 0.18, "anchor": tkinter.CENTER}, "Column6": {"width": 0.18, "anchor": tkinter.CENTER}, "Column7": {"width": 0.18, "anchor": tkinter.CENTER}}
        compare_table_frame = tkinter.Frame(popup)
        compare_scrollbar = tkinter.Scrollbar(compare_table_frame, orient=tkinter.VERTICAL)
        compare_scrollbar.pack(side=tkinter.RIGHT, fill=tkinter.Y)
        self.compare_table = self._create_header("compare_table", compare_table_frame, 0, self.fonts_dict["All.TableRow"], headers, self.table_width, True, True, constants.TABLE_STYLE, False)
        self.compare_table.config(yscrollcommand=compare_scrollbar.set)
        compare_scrollbar.config(command=self.compare_table.yview)
        clear_button = Button(popup, text="Clear Table", command=self.__clear_compare_table)
        card_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        clear_button.grid(row=1, column=0, sticky="nsew", padx=5)
        compare_table_frame.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)
        self.compare_table.pack(expand=True, fill="both")
        card_entry = AutocompleteEntry(card_frame)
        card_entry.initialize(set_card_names)
        card_entry.focus_set()
        card_entry.pack(side=tkinter.LEFT, expand=True, fill="both")
        card_entry.bind("<Return>", lambda event: self.__update_compare_table(card_entry))
        self.__update_compare_table(card_entry)

    def __close_taken_cards_window(self, popup):
        self.taken_table = None
        popup.destroy()

    def __open_taken_cards_window(self):
        if self.taken_table: return
        popup = tkinter.Toplevel()
        popup.wm_title("Taken Cards")
        popup.attributes("-topmost", True)
        popup.resizable(width=False, height=True)
        popup.protocol("WM_DELETE_WINDOW", lambda window=popup: self.__close_taken_cards_window(window))
        self.__control_trace(False)
        
        tkinter.Grid.rowconfigure(popup, 4, weight=1)
        tkinter.Grid.columnconfigure(popup, 6, weight=1)
        copy_button = Button(popup, command=lambda: copy_taken(self.draft.retrieve_taken_cards()), text="Copy Card List")
        headers = {"Column1": {"width": 0.40, "anchor": tkinter.W}, "Column2": {"width": 0.20, "anchor": tkinter.CENTER}, "Column3": {"width": 0.20, "anchor": tkinter.CENTER}, "Column4": {"width": 0.20, "anchor": tkinter.CENTER}, "Column5": {"width": 0.20, "anchor": tkinter.CENTER}, "Column6": {"width": 0.20, "anchor": tkinter.CENTER}, "Column7": {"width": 0.20, "anchor": tkinter.CENTER}, "Column8": {"width": 0.20, "anchor": tkinter.CENTER}, "Column9": {"width": 0.20, "anchor": tkinter.CENTER}, "Column10": {"width": 0.20, "anchor": tkinter.CENTER}, "Column11": {"width": 0.20, "anchor": tkinter.CENTER}}
        taken_table_frame = tkinter.Frame(popup)
        taken_scrollbar = tkinter.Scrollbar(taken_table_frame, orient=tkinter.VERTICAL)
        taken_scrollbar.pack(side=tkinter.RIGHT, fill=tkinter.Y)
        self.taken_table = self._create_header("taken_table", taken_table_frame, 0, self.fonts_dict["All.TableRow"], headers, self._scale_value(440), True, True, "Taken.Treeview", False)
        self.taken_table.config(yscrollcommand=taken_scrollbar.set)
        taken_scrollbar.config(command=self.taken_table.yview)
        
        option_frame = tkinter.Frame(popup, highlightbackground="gray", highlightthickness=1)
        self.taken_filter_selection.set(self.deck_filter_selection.get())
        taken_option = OptionMenu(option_frame, self.taken_filter_selection, self.taken_filter_selection.get(), *self.deck_filter_list, style="All.TMenubutton")
        type_checkbox_frame = tkinter.Frame(popup, highlightbackground="gray", highlightthickness=1)
        for text, var in [("CREATURES", self.taken_type_creature_checkbox_value), ("LANDS", self.taken_type_land_checkbox_value), ("INSTANTS", self.taken_type_instant_sorcery_checkbox_value), ("OTHER", self.taken_type_other_checkbox_value)]:
            Checkbutton(type_checkbox_frame, text=text, variable=var, style="Taken.TCheckbutton").pack(side=tkinter.LEFT, padx=5)
        
        checkbox_frame = tkinter.Frame(popup, highlightbackground="gray", highlightthickness=1)
        for text, var in [("ALSA", self.taken_alsa_checkbox_value), ("ATA", self.taken_ata_checkbox_value), ("GPWR", self.taken_gpwr_checkbox_value), ("OHWR", self.taken_ohwr_checkbox_value), ("GDWR", self.taken_gdwr_checkbox_value), ("GNSWR", self.taken_gndwr_checkbox_value), ("IWD", self.taken_iwd_checkbox_value), ("WHEEL", self.taken_wheel_checkbox_value)]:
            Checkbutton(checkbox_frame, text=text, variable=var, style="Taken.TCheckbutton").pack(side=tkinter.LEFT, padx=5)

        option_frame.grid(row=0, column=0, columnspan=7, sticky="nsew", padx=5, pady=5)
        type_checkbox_frame.grid(row=1, column=0, columnspan=7, sticky="nsew", padx=5)
        checkbox_frame.grid(row=2, column=0, columnspan=7, sticky="nsew", padx=5, pady=5)
        copy_button.grid(row=3, column=0, columnspan=7, sticky="nsew", padx=5)
        taken_table_frame.grid(row=4, column=0, columnspan=7, sticky="nsew", padx=5, pady=5)
        self.taken_table.pack(side=tkinter.LEFT, expand=True, fill="both")
        Label(option_frame, text="Deck Filter:", style="MainSectionsBold.TLabel").pack(side=tkinter.LEFT, padx=5)
        taken_option.pack(side=tkinter.LEFT, expand=True, fill="both")

        location_x, location_y = identify_safe_coordinates(self.root, self._scale_value(700), self._scale_value(600), 250, 0)
        popup.wm_geometry(f"+{location_x}+{location_y}")
        self.__update_taken_table()
        self.__control_trace(True)

    def __close_suggest_deck_window(self, popup):
        self.suggester_table = None
        popup.destroy()

    def __open_suggest_deck_window(self):
        if self.suggester_table: return
        popup = tkinter.Toplevel()
        popup.wm_title("Suggested Decks")
        popup.attributes("-topmost", True)
        popup.resizable(width=False, height=False)
        location_x, location_y = identify_safe_coordinates(self.root, self._scale_value(400), self._scale_value(170), self._scale_value(250), 0)
        popup.wm_geometry(f"+{location_x}+{location_y}")
        popup.protocol("WM_DELETE_WINDOW", lambda window=popup: self.__close_suggest_deck_window(window))
        
        tkinter.Grid.rowconfigure(popup, 3, weight=1)
        suggested_decks = suggest_deck(self.draft.retrieve_taken_cards(), self.set_metrics, self.configuration)
        choices, deck_color_options = (["None"], {})
        if suggested_decks:
            choices = []
            for key, value in suggested_decks.items():
                label = f"{key} {value['type']} (Rating:{value['rating']})"
                deck_color_options[label] = key
                choices.append(label)

        deck_colors_value = tkinter.StringVar(popup)
        deck_colors_entry = OptionMenu(popup, deck_colors_value, choices[0], *choices)
        headers = {"CARD": {"width": 0.35, "anchor": tkinter.W}, "COUNT": {"width": 0.14, "anchor": tkinter.CENTER}, "COLOR": {"width": 0.12, "anchor": tkinter.CENTER}, "COST": {"width": 0.10, "anchor": tkinter.CENTER}, "TYPE": {"width": 0.29, "anchor": tkinter.CENTER}}
        suggester_table_frame = tkinter.Frame(popup)
        suggest_scrollbar = tkinter.Scrollbar(suggester_table_frame, orient=tkinter.VERTICAL)
        suggest_scrollbar.pack(side=tkinter.RIGHT, fill=tkinter.Y)
        self.suggester_table = self._create_header("suggester_table", suggester_table_frame, 0, self.fonts_dict["All.TableRow"], headers, self._scale_value(450), True, True, "Suggest.Treeview", False)
        self.suggester_table.config(yscrollcommand=suggest_scrollbar.set)
        suggest_scrollbar.config(command=self.suggester_table.yview)
        
        Label(popup, text="Deck Colors:", style="MainSectionsBold.TLabel").grid(row=0, column=0, sticky="nsew", padx=5)
        deck_colors_entry.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        Button(popup, command=lambda: self.__update_suggest_table(deck_colors_value, suggested_decks, deck_color_options), text="View Deck").grid(row=1, column=0, columnspan=2, sticky="nsew", padx=5)
        Button(popup, command=lambda: copy_suggested(deck_colors_value, suggested_decks, deck_color_options), text="Copy Deck to Clipboard").grid(row=2, column=0, columnspan=2, sticky="nsew", padx=5, pady=5)
        suggester_table_frame.grid(row=3, column=0, columnspan=2, sticky="nsew", padx=5)
        self.suggester_table.pack(expand=True, fill="both")
        if choices[0] != "None": self.__update_suggest_table(deck_colors_value, suggested_decks, deck_color_options)

    def __close_settings_window(self, popup):
        self.column_2_options = None
        popup.destroy()

    def __open_settings_window(self):
        if self.column_2_options: return
        popup = tkinter.Toplevel()
        popup.wm_title("Application Settings")
        popup.attributes("-topmost", True)
        popup.resizable(width=False, height=False)
        location_x, location_y = identify_safe_coordinates(self.root, self._scale_value(400), self._scale_value(170), self._scale_value(250), 0)
        popup.wm_geometry(f"+{location_x}+{location_y}")
        popup.protocol("WM_DELETE_WINDOW", lambda window=popup: self.__close_settings_window(window))
        
        self.__control_trace(False)
        container = tkinter.Frame(popup)
        container.pack(padx=10, pady=10, fill="both")

        # Config mapping
        settings_configs = [
            ("Column 2 Data:", self.column_2_selection, self.column_2_list),
            ("Column 3 Data:", self.column_3_selection, self.column_3_list),
            ("Column 4 Data:", self.column_4_selection, self.column_4_list),
            ("Column 5 Data:", self.column_5_selection, self.column_5_list),
            ("Column 6 Data:", self.column_6_selection, self.column_6_list),
            ("Column 7 Data:", self.column_7_selection, self.column_7_list),
            ("Filter Format:", self.filter_format_selection, self.filter_format_list),
            ("Win Rate Format:", self.result_format_selection, self.result_format_list),
            ("UI Scaling:", self.ui_size_selection, self.ui_size_list),
        ]

        row_idx = 0
        for label, var, lst in settings_configs:
            Label(container, text=label, style="MainSectionsBold.TLabel").grid(row=row_idx, column=0, sticky="e", pady=2, padx=5)
            om = OptionMenu(container, var, var.get(), *lst, style="All.TMenubutton")
            om.grid(row=row_idx, column=1, sticky="w", pady=2)
            if label == "Column 2 Data:": self.column_2_options = om
            row_idx += 1

        # Checkbox mapping
        check_configs = [
            ("Display Draft Stats", self.deck_stats_checkbox_value),
            ("Display Signal Scores", self.signals_checkbox_value),
            ("Display Missing Cards", self.missing_cards_checkbox_value),
            ("Enable Auto-Highest Rated", self.auto_highest_checkbox_value),
            ("Enable P1P1 OCR (Third Party)", self.p1p1_ocr_checkbox_value),
            ("Enable Color Row Highlighting", self.card_colors_checkbox_value),
            ("Use Color Identity (Abilities)", self.color_identity_checkbox_value),
            ("Enable Update Notifications", self.update_notifications_checkbox_value),
            ("Enable Missing Dataset Alerts", self.missing_notifications_checkbox_value),
        ]

        for text, var in check_configs:
            Checkbutton(container, text=text, variable=var).grid(row=row_idx, column=0, columnspan=2, sticky="w", padx=10, pady=1)
            row_idx += 1

        Button(container, text="Restore Defaults", command=self.__default_settings_callback).grid(row=row_idx, column=0, columnspan=2, pady=10, sticky="nsew")
        self.__control_trace(True)

    def __close_about_window(self, popup):
        self.about_window_open = False
        popup.destroy()

    def __open_about_window(self):
        if self.about_window_open: return
        popup = tkinter.Toplevel()
        popup.wm_title("About")
        popup.attributes("-topmost", True)
        popup.resizable(width=False, height=False)
        location_x, location_y = identify_safe_coordinates(self.root, self._scale_value(400), self._scale_value(170), self._scale_value(250), 0)
        popup.wm_geometry(f"+{location_x}+{location_y}")
        popup.protocol("WM_DELETE_WINDOW", lambda window=popup: self.__close_about_window(window))
        
        container = tkinter.Frame(popup, padx=20, pady=20)
        container.pack()
        Label(container, text="MTGA Draft 17Lands", style="Status.TLabel").pack()
        Label(container, text=f"Version {constants.APPLICATION_VERSION}", style="Notes.TLabel").pack(pady=(0, 10))
        Label(container, text="A real-time draft assistant powered by 17Lands data.", wraplength=300, justify="center").pack()
        
        gh = Label(container, text="GitHub Repository", foreground="#007fff", cursor="hand2")
        gh.pack(pady=5); gh.bind("<Button-1>", lambda e: webbrowser.open("https://github.com/unrealities/MTGA_Draft_17Lands"))
        
        sl = Label(container, text="Visit 17Lands.com", foreground="#007fff", cursor="hand2")
        sl.pack(); sl.bind("<Button-1>", lambda e: webbrowser.open("https://www.17lands.com"))
        
        self.about_window_open = True

    def __process_table_click(self, event, table, card_list, selected_color, fields=None):
        for item in table.selection():
            card_name = table.item(item, "value")[0]
            card_name = card_name[1:] if card_name.startswith("*") else card_name
            for card in card_list:
                if card[constants.DATA_FIELD_NAME] == card_name:
                    color_dict = {}
                    for color in selected_color:
                        color_dict[color] = {x: card.get(constants.DATA_FIELD_DECK_COLORS, {}).get(color, {}).get(x, "NA") for x in constants.DATA_FIELDS_LIST}
                    
                    tier_info = {n: t.ratings[card_name].comment for n, t in self.tier_data.items() if fields and n in fields.values() and card_name in t.ratings}
                    archetypes = self.draft.set_data.get_card_archetypes_by_field(card_name, constants.DATA_FIELD_GIHWR)
                    
                    if self.configuration.settings.result_format != constants.RESULT_FORMAT_WIN_RATE:
                        cr = CardResult(self.set_metrics, self.tier_data, self.configuration, self.draft.current_pick)
                        for a in archetypes: a.append(cr.return_results([card], [a[1]], [constants.DATA_FIELD_GIHWR])[0]["results"][0])
                    
                    CreateCardToolTip(table, event, card_name, color_dict, card[constants.DATA_SECTION_IMAGES], self.configuration.features.images_enabled, self.scale_factor, self.fonts_dict, tier_info, archetypes)
                    break

    def __open_draft_log(self, log_path=""):
        filename = log_path if log_path and path.isfile(log_path) else filedialog.askopenfilename(filetypes=(("Log Files", "*.log"), ("All files", "*.*")))
        if filename:
            self.arena_file = filename
            self.draft.set_arena_file(filename)
            if constants.LOG_NAME in self.arena_file:
                self.configuration.settings.arena_log_location = self.arena_file
                write_configuration(self.configuration)
            self.__update_event_files_callback()

    def __update_event_files_callback(self):
        self.__reset_draft(True)
        self.draft.log_suspend(True)
        self.__update_overlay_callback(True)
        self.draft.log_suspend(False)

    def __control_trace(self, enabled):
        """Standardizing trace logic to ensure settings persist"""
        trc = [
            (self.column_2_selection, self.__update_settings_callback),
            (self.column_3_selection, self.__update_settings_callback),
            (self.column_4_selection, self.__update_settings_callback),
            (self.column_5_selection, self.__update_settings_callback),
            (self.column_6_selection, self.__update_settings_callback),
            (self.column_7_selection, self.__update_settings_callback),
            (self.deck_stats_checkbox_value, self.__update_settings_callback),
            (self.signals_checkbox_value, self.__update_settings_callback),
            (self.missing_cards_checkbox_value, self.__update_settings_callback),
            (self.auto_highest_checkbox_value, self.__update_settings_callback),
            (self.data_source_selection, self.__update_source_callback),
            (self.stat_options_selection, self.__update_deck_stats_callback),
            (self.filter_format_selection, self.__update_source_callback),
            (self.result_format_selection, self.__update_source_callback),
            (self.deck_filter_selection, self.__update_source_callback),
            (self.taken_alsa_checkbox_value, self.__update_settings_callback),
            (self.taken_ata_checkbox_value, self.__update_settings_callback),
            (self.taken_gpwr_checkbox_value, self.__update_settings_callback),
            (self.taken_ohwr_checkbox_value, self.__update_settings_callback),
            (self.taken_gdwr_checkbox_value, self.__update_settings_callback),
            (self.taken_gndwr_checkbox_value, self.__update_settings_callback),
            (self.taken_iwd_checkbox_value, self.__update_settings_callback),
            (self.taken_wheel_checkbox_value, self.__update_settings_callback),
            (self.taken_filter_selection, self.__update_settings_callback),
            (self.card_colors_checkbox_value, self.__update_settings_callback),
            (self.color_identity_checkbox_value, self.__update_settings_callback),
            (self.current_draft_checkbox_value, self.__update_settings_callback),
            (self.data_source_checkbox_value, self.__update_settings_callback),
            (self.deck_filter_checkbox_value, self.__update_settings_callback),
            (self.refresh_button_checkbox_value, self.__update_settings_callback),
            (self.update_notifications_checkbox_value, self.__update_settings_callback),
            (self.missing_notifications_checkbox_value, self.__update_settings_callback),
            (self.p1p1_ocr_checkbox_value, self.__update_settings_callback),
        ]
        if enabled:
            if not self.trace_ids:
                for v, cb in trc: self.trace_ids.append(v.trace_add("write", cb))
        elif self.trace_ids:
            for v, _ in trc:
                try: v.trace_remove("write", self.trace_ids.pop(0))
                except: pass
            self.trace_ids = []

    def __reset_draft(self, full_reset):
        self.draft.clear_draft(full_reset)

    def __display_widgets(self):
        toggle_widget(self.stat_frame, self.deck_stats_checkbox_value.get())
        toggle_widget(self.stat_table, self.deck_stats_checkbox_value.get())
        toggle_widget(self.signal_frame, self.signals_checkbox_value.get())
        toggle_widget(self.missing_frame, self.missing_cards_checkbox_value.get())
        toggle_widget(self.missing_table_frame, self.missing_cards_checkbox_value.get())
        toggle_widget(self.refresh_button_frame, self.refresh_button_checkbox_value.get())
        dv = self.current_draft_checkbox_value.get()
        toggle_widget(self.current_draft_label_frame, dv)
        toggle_widget(self.current_draft_value_frame, dv)
        sv = self.data_source_checkbox_value.get()
        toggle_widget(self.data_source_label_frame, sv)
        toggle_widget(self.data_source_option_frame, sv)
        cv = self.deck_filter_checkbox_value.get()
        toggle_widget(self.deck_colors_label_frame, cv)
        toggle_widget(self.deck_colors_option_frame, cv)
        toggle_widget(self.separator_frame_draft, dv or sv or cv)


class CreateCardToolTip(ScaledWindow):
    """Reliable, modern Tooltip for macOS."""
    def __init__(self, widget, event, name, stats, images, img_enabled, scale, fonts, tier_info, top_archetypes):
        super().__init__()
        self.tw = tkinter.Toplevel(widget)
        self.tw.transient(widget.winfo_toplevel())
        self.tw.wm_overrideredirect(True)
        self.tw.attributes("-topmost", True)
        
        main_f = tkinter.Frame(self.tw, background="#1a1a1a", borderwidth=1, relief="solid")
        main_f.pack()
        
        # Standard Label forces black background on macOS
        header = tkinter.Label(
            main_f, text=name, fg="white", bg="#1a1a1a", 
            font=(fonts["All.TMenubutton"][0], self._scale_value(-15), "bold"),
            padx=15, pady=10, highlightthickness=0
        )
        header.pack(fill="x")
        
        content_f = tkinter.Frame(main_f, background="#2b2b2b", padx=10, pady=10)
        content_f.pack()
        
        if img_enabled and images:
            try:
                r = requests.get(images[0], timeout=5); im = Image.open(io.BytesIO(r.content))
                im.thumbnail((self._scale_value(260), self._scale_value(380)), Image.Resampling.LANCZOS)
                tk_im = ImageTk.PhotoImage(im); self.img_refs = [tk_im]
                tkinter.Label(content_f, image=tk_im, bg="#2b2b2b", highlightthickness=0).pack(side="left", padx=(0, 10))
            except: pass

        stats_f = tkinter.Frame(content_f, background="#2b2b2b")
        stats_f.pack(side="left", fill="y")
        
        ck = list(stats.keys())[0] if stats else "All Decks"; d = stats.get(ck, {})
        rows = [("GIH WR", f"{d.get('gihwr', 0)}%"), ("OH WR", f"{d.get('ohwr', 0)}%"), ("GP WR", f"{d.get('gpwr', 0)}%"), ("IWD", f"{d.get('iwd', 0)}pp")]
        
        tkinter.Label(stats_f, text=f"FILTER: {ck.upper()}", fg="#007fff", bg="#2b2b2b", font=(fonts["All.TMenubutton"][0], self._scale_value(-10), "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        for i, (l, v) in enumerate(rows):
            tkinter.Label(stats_f, text=l, fg="#888888", bg="#2b2b2b", font=(fonts["All.TMenubutton"][0], self._scale_value(-11))).grid(row=i+1, column=0, sticky="w", pady=2)
            tkinter.Label(stats_f, text=str(v), fg="white", bg="#2b2b2b", font=(fonts["All.TMenubutton"][0], self._scale_value(-11), "bold")).grid(row=i+1, column=1, sticky="e", padx=(20, 0))

        x, y = identify_safe_coordinates(widget, self._scale_value(520), self._scale_value(420), 25, 25)
        self.tw.wm_geometry(f"+{x}+{y}")
        self.tw.lift()
        widget.bind("<Leave>", lambda e: self.tw.destroy())

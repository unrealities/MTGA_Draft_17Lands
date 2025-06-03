import tkinter
import math
from tkinter.ttk import Treeview
from src import constants
from src.logger import create_logger
from src.card_logic import (
    field_process_sort,
    row_color_tag
)

logger = create_logger()

def identify_safe_coordinates(root, window_width, window_height, offset_x, offset_y):
    '''Return x,y coordinates that fall within the bounds of the screen'''
    location_x = 0
    location_y = 0

    try:
        pointer_x = root.winfo_pointerx()
        pointer_y = root.winfo_pointery()
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()

        if pointer_x + offset_x + window_width > screen_width:
            location_x = max(pointer_x - offset_x - window_width, 0)
        else:
            location_x = pointer_x + offset_x

        if pointer_y + offset_y + window_height > screen_height:
            location_y = max(pointer_y - offset_y - window_height, 0)
        else:
            location_y = pointer_y + offset_y

    except Exception as error:
        logger.error(error)

    return location_x, location_y

class TableInfo:
    reverse: bool = True
    column: str = ""

class ScaledWindow:
    def __init__(self):
        self.scale_factor = 1
        self.fonts_dict = {}
        self.table_info = {}

    def _scale_value(self, value):
        scaled_value = int(value * self.scale_factor)
        return scaled_value

    def _create_header(self, table_label, frame, height, font, headers, total_width, include_header, fixed_width, table_style, stretch_enabled):
        """Configure the tkinter Treeview widget tables that are used to list draft data"""
        header_labels = tuple(headers.keys())
        show_header = "headings" if include_header else ""
        column_stretch = tkinter.YES if stretch_enabled else tkinter.NO
        list_box = Treeview(frame, columns=header_labels,
                            show=show_header, style=table_style, height=height)

        try:
            for key, value in constants.ROW_TAGS_BW_DICT.items():
                list_box.tag_configure(
                    key, font=(value[0], font, "bold"), background=value[1], foreground=value[2])

            for key, value in constants.ROW_TAGS_COLORS_DICT.items():
                list_box.tag_configure(
                    key, font=(value[0], font, "bold"), background=value[1], foreground=value[2])

            for column in header_labels:
                if fixed_width:
                    column_width = int(
                        math.ceil(headers[column]["width"] * total_width))
                    list_box.column(column,
                                    stretch=column_stretch,
                                    anchor=headers[column]["anchor"],
                                    width=column_width)
                else:
                    list_box.column(column, stretch=column_stretch,
                                    anchor=headers[column]["anchor"])
                list_box.heading(column, text=column, anchor=tkinter.CENTER,
                                 command=lambda _col=column: self._sort_table_column(table_label, list_box, _col, True))
            list_box["show"] = show_header  # use after setting columns
            if include_header:
                list_box.bind(
                    '<Button-1>', lambda event: self._disable_resizing(event, table=list_box))
            self.table_info[table_label] = TableInfo()
        except Exception as error:
            logger.error(error)
        return list_box

    def _sort_table_column(self, table_label, table, column, reverse):
        """Sort the table columns when clicked"""
        row_colors = False
        row_list = []
        for k in table.get_children(''):
            column_value = table.set(k, column)
            try:
                row_list.append((float(column_value), k))
            except ValueError:
                row_list.append((column_value, k))

        row_list.sort(key=lambda x: field_process_sort(
            x[0]), reverse=reverse)

        if row_list:
            tags = table.item(row_list[0][1])["tags"][0]
            row_colors = True if tags in constants.ROW_TAGS_COLORS_DICT else False

        for index, value in enumerate(row_list):
            table.move(value[1], "", index)

            # Reset the black/white shades for sorted rows
            if not row_colors:
                row_tag = self._identify_table_row_tag(False, "", index)
                table.item(value[1], tags=row_tag)

        if table_label in self.table_info:
            self.table_info[table_label].reverse = reverse
            self.table_info[table_label].column = column

        table.heading(column, command=lambda: self._sort_table_column(
            table_label, table, column, not reverse))

    def _disable_resizing(self, event, table):
        '''Disable the column resizing for a treeview table'''
        if table.identify_region(event.x, event.y) == "separator":
            return "break"

    def _identify_table_row_tag(self, colors_enabled, colors, index):
        """Return the row color (black/white or card color) depending on the application settings"""
        tag = ""
        if colors_enabled:
            tag = row_color_tag(colors)
        else:
            tag = constants.BW_ROW_COLOR_ODD_TAG if index % 2 else constants.BW_ROW_COLOR_EVEN_TAG
        return tag

    def _identify_card_row_tag(self, configuration, card_data, count):
        '''Wrapper function for setting the row color for a card'''
        if constants.CARD_TYPE_LAND in card_data[constants.DATA_FIELD_TYPES]:
            colors = card_data[constants.DATA_FIELD_COLORS]
        else:
            colors = card_data[constants.DATA_FIELD_MANA_COST]

        row_tag = self._identify_table_row_tag(configuration.card_colors_enabled, colors, count)

        return row_tag

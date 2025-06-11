"""This module contains the functions and classes that are used for building the set files and communicating with platforms"""
from urllib.parse import quote as urlencode
import sys
import os
import time
import json
import urllib.request
import datetime
import ssl
import itertools
import re
import sqlite3
from src import constants
from src.logger import create_logger
from src.utils import Result, check_file_integrity

logger = create_logger()

if not os.path.exists(constants.SETS_FOLDER):
    os.makedirs(constants.SETS_FOLDER)

if not os.path.exists(constants.TEMP_FOLDER):
    os.makedirs(constants.TEMP_FOLDER)

def initialize_card_data(card_data):
    card_data[constants.DATA_FIELD_DECK_COLORS] = {}
    for color in constants.DECK_COLORS:
        card_data[constants.DATA_FIELD_DECK_COLORS][color] = {
            x: 0.0 for x in constants.DATA_FIELD_17LANDS_DICT if x != constants.DATA_SECTION_IMAGES}


def check_set_data(set_data, ratings_data):
    '''Run through 17Lands card list and determine if there are any cards missing from the assembled set file'''
    for rated_card in ratings_data:
        try:
            card_found = False
            for card_id in set_data:
                card_name = set_data[card_id][constants.DATA_FIELD_NAME].replace(
                    "///", "//")
                if rated_card == card_name:
                    card_found = True
                    break
            if not card_found:
                logger.error("Card %s Missing", rated_card)

        except Exception as error:
            logger.error(error)


def decode_mana_cost(encoded_cost):
    '''Parse the raw card mana_cost field and return the cards cmc and color identity list'''
    decoded_cost = ""
    cmc = 0
    if encoded_cost:
        cost_string = re.sub(r"\(|\)", "", encoded_cost)

        sections = cost_string[1:].split("o")
        for section in sections:
            cmc += int(section) if section.isnumeric() else 1

        decoded_cost = "".join(f"{{{x}}}" for x in sections)

    return decoded_cost, cmc

def search_arena_log_locations(input_location=None):
    '''Searches local directories for the location of the Arena Player.log file'''
    log_location = ""
    try:
        paths = []

        if input_location:
            paths.extend(input_location)

        if sys.platform == constants.PLATFORM_ID_LINUX:
            paths.extend([os.path.join(os.path.expanduser(
                '~'), constants.LOG_LOCATION_LINUX)])
        elif sys.platform == constants.PLATFORM_ID_OSX:
            paths.extend([os.path.join(os.path.expanduser(
                '~'), constants.LOG_LOCATION_OSX)])
        else:
            path_list = [constants.WINDOWS_DRIVES,
                         [constants.LOG_LOCATION_WINDOWS]]
            paths.extend([os.path.join(*x)
                         for x in itertools.product(*path_list)])

        for file_path in paths:
            if file_path:
                logger.info("Arena Log: Searching File Path %s", file_path)
                if os.path.exists(file_path):
                    log_location = file_path
                    break

    except Exception as error:
        logger.error(error)
    return log_location


def retrieve_arena_directory(log_location):
    '''Searches the Player.log file for the Arena install location'''
    arena_directory = ""
    try:
        # Retrieve the arena directory
        with open(log_location, 'r', encoding="utf-8", errors="replace") as log_file:
            line = log_file.readline()
            if sys.platform == constants.PLATFORM_ID_WINDOWS:
                # Windows: original regex
                location = re.findall(r"'(.*?)/Managed'", line, re.DOTALL)
            else:
                # Other platforms: exclude 'X:/...'
                location = re.findall(r"'.*?([/][^']+)/Managed'", line)
            if location:
                path = location[0]
                if os.path.exists(path):
                    arena_directory = path

    except Exception as error:
        logger.error(error)
    return arena_directory


def search_local_files(paths, file_prefixes):
    '''Generic function that's used for searching local directories for a file'''
    file_locations = []
    for file_path in paths:
        try:
            if os.path.exists(file_path):
                for prefix in file_prefixes:
                    files = [filename for filename in os.listdir(
                        file_path) if filename.startswith(prefix)]

                    for file in files:
                        file_location = os.path.join(file_path, file)
                        file_locations.append(file_location)

        except Exception as error:
            logger.error(error)

    return file_locations


def extract_types(type_line):
    '''Parses a type string and returns a list of card types'''
    types = []
    if constants.CARD_TYPE_CREATURE in type_line:
        types.append(constants.CARD_TYPE_CREATURE)

    if constants.CARD_TYPE_PLANESWALKER in type_line:
        types.append(constants.CARD_TYPE_PLANESWALKER)

    if constants.CARD_TYPE_LAND in type_line:
        types.append(constants.CARD_TYPE_LAND)

    if constants.CARD_TYPE_INSTANT in type_line:
        types.append(constants.CARD_TYPE_INSTANT)

    if constants.CARD_TYPE_SORCERY in type_line:
        types.append(constants.CARD_TYPE_SORCERY)

    if constants.CARD_TYPE_ENCHANTMENT in type_line:
        types.append(constants.CARD_TYPE_ENCHANTMENT)

    if constants.CARD_TYPE_ARTIFACT in type_line:
        types.append(constants.CARD_TYPE_ARTIFACT)

    return types


def check_date(date):
    '''Checks a date string and returns false if the date is in the future'''
    result = True
    try:
        parts = date.split("-")
        year = int(parts[0])
        month = int(parts[1])
        day = int(parts[2])
        hour = 0

        if datetime.datetime(year=year, month=month, day=day, hour=hour) > datetime.datetime.now():
            result = False

    except Exception:
        result = False
    return result

class FileExtractor:
    '''Class that handles the creation of set files and the retrieval of platform information'''

    def __init__(self, directory):
        self.selected_sets = []
        self.set_list = []
        self.draft = ""
        self.session = ""
        self.start_date = ""
        self.end_date = ""
        self.user_group = ""
        self.directory = directory
        self.context: ssl.SSLContext = ssl.SSLContext(protocol=ssl.PROTOCOL_TLS_CLIENT)
        self.context.load_default_certs()
        self.card_ratings = {}
        self.combined_data = {
            "meta": {"collection_date": str(datetime.datetime.now())}}
        self.card_dict = {}
        self.deck_colors = constants.DECK_COLORS
        self.sets_17lands = []

    def clear_data(self):
        '''Clear stored set information'''
        self.combined_data = {
            "meta": {"collection_date": str(datetime.datetime.now())}}
        self.card_dict = {}
        self.card_ratings = {}

    def select_sets(self, sets):
        '''Public function that's used for setting class variables'''
        self.selected_sets = sets

    def set_draft_type(self, draft_type):
        '''Public function that's used for setting class variables'''
        self.draft = draft_type

    def set_start_date(self, start_date):
        '''Sets the start data in a set file'''
        result = False
        if check_date(start_date):
            result = True
            self.start_date = start_date
            self.combined_data["meta"]["start_date"] = self.start_date
        return result

    def set_end_date(self, end_date):
        '''Sets the end date in a set file'''
        result = False
        if check_date(end_date):
            result = True
            self.end_date = end_date
            self.combined_data["meta"]["end_date"] = self.end_date
        return result
    
    def set_user_group(self, user_group):
        '''Sets the user_group filter in a set file (all/bottom/middle/top)'''
        if user_group in constants.LIMITED_GROUPS_LIST:
            self.user_group = user_group
        else:
            self.user_group = constants.LIMITED_USER_GROUP_ALL       

    def set_version(self, version):
        '''Sets the version in a set file'''
        self.combined_data["meta"]["version"] = version

    def download_card_data(self, ui_root, progress_bar, status, database_size):
        '''Wrapper function for starting the set file download/creation process'''
        result = False
        result_string = ""
        temp_size = 0
        try:
            result, result_string, temp_size = self._download_expansion(
                ui_root, progress_bar, status, database_size)

        except Exception as error:
            logger.error(error)
            result_string = error

        return result, result_string, temp_size

    def _download_expansion(self, ui_root, progress_bar, status, database_size):
        ''' Function that performs the following steps:
            1. Build a card data file from local Arena files (stored as temp_card_data.json in the Temp folder)
               - The card sets contains the Arena IDs, card name, mana cost, colors, etc.
            1A. Collect the card data from Scryfall if it's unavailable locally (fallback)
            2. Collect the card_ratings data from scryfall
            3. Build a set file by combining the card data and the card ratings
        '''
        result = False
        result_string = ""
        temp_size = 0
        try:
            while True:
                progress_bar['value'] = 5
                ui_root.update()

                result, result_string, temp_size = self._retrieve_local_arena_data(
                    ui_root, status, database_size)

                if not result:
                    result, result_string = self._retrieve_scryfall_data(
                        ui_root, status)
                    if not result:
                        break

                progress_bar['value'] = 10
                status.set("Collecting 17Lands Data")
                ui_root.update()

                if not self.retrieve_17lands_data(self.selected_sets.seventeenlands,
                                                  self.deck_colors,
                                                  ui_root,
                                                  progress_bar,
                                                  progress_bar['value'],
                                                  status):
                    result = False
                    result_string = "Couldn't Collect 17Lands Data"
                    break

                matching_only = True if constants.SET_SELECTION_ALL in self.selected_sets.arena else False

                if not matching_only:
                    self._initialize_17lands_data()

                status.set("Building Data Set File")
                ui_root.update()
                self._assemble_set(matching_only)
                check_set_data(
                    self.combined_data["card_ratings"], self.card_ratings)
                break

        except Exception as error:
            logger.error(error)
            result_string = error

        return result, result_string, temp_size

    def _retrieve_local_arena_data(self, root, status, previous_database_size):
        '''Builds a card data file from raw Arena files'''
        result_string = "Couldn't Collect Local Card Data"
        result = False
        self.card_dict = {}
        database_size = 0
        status.set("Searching Local Files")
        root.update()
        if sys.platform == constants.PLATFORM_ID_OSX:
            directory = os.path.join(os.path.expanduser('~'),
                                     constants.LOCAL_DATA_FOLDER_PATH_OSX) if not self.directory else self.directory
            paths = [os.path.join(directory, constants.LOCAL_DOWNLOADS_DATA)]
        elif sys.platform == constants.PLATFORM_ID_LINUX:
            if constants.LOCAL_DATA_FOLDER_PATH_LINUX:
                directory = constants.LOCAL_DATA_FOLDER_PATH_LINUX if not self.directory else self.directory
                paths = [os.path.join(directory, constants.LOCAL_DOWNLOADS_DATA)]
            else:
                paths = [] # program was giving errors on WSL without this
        else:
            if not self.directory:
                path_list = [constants.WINDOWS_DRIVES, constants.WINDOWS_PROGRAM_FILES, [
                    constants.LOCAL_DATA_FOLDER_PATH_WINDOWS]]
                paths = [os.path.join(*x)
                         for x in itertools.product(*path_list)]
            else:
                paths = [os.path.join(
                    self.directory, constants.LOCAL_DOWNLOADS_DATA)]

        arena_database_locations = search_local_files(
            paths, [constants.LOCAL_DATA_FILE_PREFIX_DATABASE])

        while True:
            try:
                if not arena_database_locations:
                    logger.error("Can't Locate Local Files")
                    break

                current_database_size = os.path.getsize(
                    arena_database_locations[0])

                if current_database_size != previous_database_size:
                    logger.info(
                        "Local File Change Detected %d, %d",
                        current_database_size, previous_database_size)
                    logger.info(
                        "Local Database Data: Searching File Path %s",
                        arena_database_locations[0])
                    status.set("Retrieving Localization Data")
                    root.update()
                    result, card_text, card_enumerators, raw_card_data = self._retrieve_local_database(
                        arena_database_locations[0])

                    if not result:
                        break

                    status.set("Building Temporary Card Data File")
                    root.update()
                    result = self._assemble_stored_data(
                        card_text, card_enumerators, raw_card_data)

                    if not result:
                        break

                # Assemble information for local data set
                status.set("Retrieving Temporary Card Data")
                root.update()
                result = self._retrieve_stored_data(
                    self.selected_sets.arena)

                database_size = current_database_size

            except Exception as error:
                logger.error(error)
            break

        if not result:
            logger.error(result_string)

        return result, result_string, database_size

    def _retrieve_local_cards(self, data):
        '''Function that retrieves pertinent card data from raw Arena files'''
        result = False
        card_data = {}
        try:
            for card in data:
                # Making all of the keys lowercase
                card = {k.lower(): v for k, v in card.items()}
                try:
                    card_set = card[constants.LOCAL_CARDS_KEY_SET]
                    if ((card[constants.LOCAL_CARDS_KEY_DIGITAL_RELEASE_SET]) and
                       (re.findall(r"^[yY]\d{2}$", card_set, re.DOTALL))):
                        card_set = card[constants.LOCAL_CARDS_KEY_DIGITAL_RELEASE_SET]
                    if card_set not in card_data:
                        card_data[card_set] = {}
                    if card[constants.LOCAL_CARDS_KEY_TOKEN]:
                        # Skip tokens
                        continue
                    if not card[constants.LOCAL_CARDS_KEY_TITLE_ID]:
                        # Skip cards that don't have titles
                        continue
                    group_id = card[constants.LOCAL_CARDS_KEY_GROUP_ID]

                    card_data[card_set][group_id] = {
                        constants.DATA_FIELD_NAME: [card[constants.LOCAL_CARDS_KEY_TITLE_ID]],
                        constants.DATA_FIELD_CMC: 0,
                        constants.DATA_FIELD_MANA_COST: "",
                        constants.LOCAL_CARDS_KEY_PRIMARY: 1,
                        constants.LOCAL_CARDS_KEY_LINKED_FACE_TYPE: 0,
                        constants.DATA_FIELD_TYPES: [],
                        constants.DATA_FIELD_RARITY: "",
                        constants.DATA_SECTION_IMAGES: []}

                    mana_cost, cmc = decode_mana_cost(
                        card[constants.LOCAL_CARDS_KEY_CASTING_COST]) if card[constants.LOCAL_CARDS_KEY_CASTING_COST] else ("", 0)
                    card_data[card_set][group_id][constants.DATA_FIELD_CMC] = cmc
                    card_data[card_set][group_id][constants.DATA_FIELD_MANA_COST] = mana_cost
                    card_data[card_set][group_id][constants.DATA_FIELD_TYPES].extend([int(
                        x) for x in card[constants.LOCAL_CARDS_KEY_TYPES].split(',')] if card[constants.LOCAL_CARDS_KEY_TYPES] else [])
                    card_data[card_set][group_id][constants.DATA_FIELD_COLORS] = [int(
                        x) for x in card[constants.LOCAL_CARDS_KEY_COLOR_ID].split(',')] if card[constants.LOCAL_CARDS_KEY_COLOR_ID] else []

                    card_data[card_set][group_id][constants.DATA_FIELD_RARITY] = constants.CARD_RARITY_DICT[card[constants.LOCAL_CARDS_KEY_RARITY]
                                                                                                            ] if card[constants.LOCAL_CARDS_KEY_RARITY] in constants.CARD_RARITY_DICT else constants.CARD_RARITY_COMMON
                    card_data[card_set][group_id][constants.LOCAL_CARDS_KEY_PRIMARY] = card[constants.LOCAL_CARDS_KEY_PRIMARY]
                    card_data[card_set][group_id][constants.LOCAL_CARDS_KEY_LINKED_FACE_TYPE] = card[constants.LOCAL_CARDS_KEY_LINKED_FACE_TYPE]

                    self._process_linked_faces(
                        card, card_data, card_set, group_id)

                    result = True
                except Exception as error:
                    logger.error(
                        f"Card Read Error: {error}, {card}")
                    break
        except Exception as error:
            logger.error(error)

        return result, card_data

    def _process_linked_faces(self, card, card_data, card_set, group_id):
        ''''''
        try:

            if card[constants.LOCAL_CARDS_KEY_LINKED_FACES]:
                linked_ids = [
                    int(x) for x in card[constants.LOCAL_CARDS_KEY_LINKED_FACES].split(',')]
                for linked_id in linked_ids:
                    if linked_id < group_id:
                        if (not card[constants.LOCAL_CARDS_KEY_PRIMARY] and
                                card_data[card_set][linked_id][constants.LOCAL_CARDS_KEY_PRIMARY]):
                            # Add types to previously seen linked cards
                            types = [int(x) for x in card[constants.LOCAL_CARDS_KEY_TYPES].split(
                                ',')] if card[constants.LOCAL_CARDS_KEY_TYPES] else []
                            card_data[card_set][linked_id][constants.LOCAL_CARDS_KEY_TYPES].extend(
                                types)

                            # Use the lowest mana cost/CMC for dual-faced cards (e.g., 4 for Dusk /// Dawn)
                            if (card[constants.LOCAL_CARDS_KEY_CASTING_COST] and
                                card_data[card_set][linked_id][constants.LOCAL_CARDS_KEY_LINKED_FACE_TYPE] and
                                    card_data[card_set][linked_id][constants.LOCAL_CARDS_KEY_LINKED_FACE_TYPE] == 6):

                                mana_cost, cmc = decode_mana_cost(
                                    card[constants.LOCAL_CARDS_KEY_CASTING_COST])
                                if cmc < card_data[card_set][linked_id][constants.DATA_FIELD_CMC]:
                                    card_data[card_set][linked_id][constants.DATA_FIELD_CMC] = cmc
                                    card_data[card_set][linked_id][constants.DATA_FIELD_MANA_COST] = mana_cost

                        elif card[constants.LOCAL_CARDS_KEY_PRIMARY]:
                            # Retrieve types from previously seen linked cards
                            card_data[card_set][group_id][constants.LOCAL_CARDS_KEY_TYPES].extend(
                                card_data[card_set][linked_id][constants.LOCAL_CARDS_KEY_TYPES])

                            # Use the lowest cmc for dual-faced cards (e.g., 4 for Dusk /// Dawn)
                            if (card[constants.LOCAL_CARDS_KEY_LINKED_FACE_TYPE] and
                                    card[constants.LOCAL_CARDS_KEY_LINKED_FACE_TYPE] == 6):

                                if card_data[card_set][linked_id][constants.DATA_FIELD_CMC] < card_data[card_set][group_id][constants.DATA_FIELD_CMC]:
                                    card_data[card_set][group_id][constants.DATA_FIELD_CMC] = card_data[
                                        card_set][group_id][constants.DATA_FIELD_CMC]
                                    card_data[card_set][group_id][constants.DATA_FIELD_MANA_COST] = card_data[
                                        card_set][group_id][constants.DATA_FIELD_MANA_COST]

        except Exception as error:
            logger.error(error)

    def _retrieve_local_database(self, file_location):
        '''Retrieves localization and enumeration data from an Arena database'''
        result = False
        card_text = {}
        card_enumerators = {}
        card_data = {}
        try:
            # Open Sqlite3 database
            while True:
                connection = sqlite3.connect(file_location)
                connection.row_factory = sqlite3.Row
                cursor = connection.cursor()

                rows = [dict(row) for row in cursor.execute(
                    constants.LOCAL_DATABASE_LOCALIZATION_QUERY)]

                if not rows:
                    break

                result, card_text = self._retrieve_local_card_text(rows)

                if not result:
                    break

                rows = [dict(row) for row in cursor.execute(
                    constants.LOCAL_DATABASE_ENUMERATOR_QUERY)]

                if not rows:
                    break

                result, card_enumerators = self._retrieve_local_card_enumerators(
                    rows)

                if not result:
                    break

                rows = [dict(row) for row in cursor.execute(
                    constants.LOCAL_DATABASE_CARDS_QUERY)]

                result, card_data = self._retrieve_local_cards(rows)
                break

        except Exception as error:
            result = False
            logger.error(error)

        return result, card_text, card_enumerators, card_data

    def _retrieve_local_card_text(self, data):
        '''Returns a dict containing localization data'''
        result = True
        card_text = {}
        try:
            # Retrieve the title (card name) for each of the collected arena IDs
            card_text = {x[constants.LOCAL_DATABASE_LOCALIZATION_COLUMN_ID]: x[constants.LOCAL_DATABASE_LOCALIZATION_COLUMN_TEXT] for x in data}

        except Exception as error:
            result = False
            logger.error(error)

        return result, card_text

    def _retrieve_local_card_enumerators(self, data):
        '''Returns a dict containing card enumeration data'''
        result = True
        card_enumerators = {constants.DATA_FIELD_COLORS: {},
                            constants.DATA_FIELD_TYPES: {}}
        try:
            for row in data:
                if row[constants.LOCAL_DATABASE_ENUMERATOR_COLUMN_TYPE] == constants.LOCAL_DATABASE_ENUMERATOR_TYPE_CARD_TYPES:
                    card_enumerators[constants.DATA_FIELD_TYPES][row[constants.LOCAL_DATABASE_ENUMERATOR_COLUMN_VALUE]
                                                                 ] = row[constants.LOCAL_DATABASE_ENUMERATOR_COLUMN_ID]
                elif row[constants.LOCAL_DATABASE_ENUMERATOR_COLUMN_TYPE] == constants.LOCAL_DATABASE_ENUMERATOR_TYPE_COLOR:
                    card_enumerators[constants.DATA_FIELD_COLORS][row[constants.LOCAL_DATABASE_ENUMERATOR_COLUMN_VALUE]
                                                                  ] = row[constants.LOCAL_DATABASE_ENUMERATOR_COLUMN_ID]

        except Exception as error:
            result = False
            logger.error(error)

        return result, card_enumerators

    def _assemble_stored_data(self, card_text, card_enumerators, card_data):
        '''Creates a temporary card data file from data collected from local Arena files'''
        result = False
        try:
            for card_set in card_data:
                for card in card_data[card_set]:
                    try:
                        card_data[card_set][card][constants.DATA_FIELD_NAME] = " // ".join(
                            card_text[x] for x in card_data[card_set][card][constants.DATA_FIELD_NAME])
                        card_data[card_set][card][constants.DATA_FIELD_TYPES] = list(set(
                            [card_text[card_enumerators[constants.DATA_FIELD_TYPES][x]] for x in card_data[card_set][card][constants.DATA_FIELD_TYPES]]))
                        card_data[card_set][card][constants.DATA_FIELD_COLORS] = [
                            constants.CARD_COLORS_DICT[card_text[card_enumerators[constants.DATA_FIELD_COLORS][x]]] for x in card_data[card_set][card][constants.DATA_FIELD_COLORS]]
                        if constants.CARD_TYPE_CREATURE in card_data[card_set][card][constants.DATA_FIELD_TYPES]:
                            index = card_data[card_set][card][constants.DATA_FIELD_TYPES].index(
                                constants.CARD_TYPE_CREATURE)
                            card_data[card_set][card][constants.DATA_FIELD_TYPES].insert(
                                0, card_data[card_set][card][constants.DATA_FIELD_TYPES].pop(index))
                        result = True
                    except Exception:
                        pass

            if result:
                # Store all of the processed card data
                with open(constants.TEMP_CARD_DATA_FILE, 'w', encoding="utf-8", errors="replace") as json_file:
                    json.dump(card_data, json_file)

        except Exception as error:
            result = False
            logger.error(error)

        return result

    def _retrieve_stored_data(self, set_list):
        '''Retrieves card data from the temp_card_data.json file stored in the Temp folder'''
        result = False
        self.card_dict = {}
        try:
            with open(constants.TEMP_CARD_DATA_FILE, 'r', encoding="utf-8", errors="replace") as data:
                json_file = data.read()
                json_data = json.loads(json_file)

            if constants.SET_SELECTION_ALL in set_list:
                for card_data in json_data.values():
                    self.card_dict.update(card_data.copy())
            else:
                for search_set in set_list:
                    matching_sets = list(
                        filter(lambda x, ss=search_set: ss in x, json_data))
                    for match in matching_sets:
                        self.card_dict.update(json_data[match].copy())

            if self.card_dict:
                result = True

        except Exception as error:
            result = False
            logger.error(error)

        return result

    def _retrieve_scryfall_data(self, root, status):
        '''Use the Scryfall API to retrieve the set data needed for building a card set file*
           - This is a fallback feature feature that's used in case there's an issue with the local Arena files
        '''
        result = False
        self.card_dict = {}
        result_string = "Couldn't Retrieve Card Data"
        url = ""
        for card_set in self.selected_sets.scryfall:
            retry = constants.SCRYFALL_REQUEST_ATTEMPT_MAX
            while retry:
                try:
                    status.set("Collecting Scryfall Data")
                    root.update()
                    url = "https://api.scryfall.com/cards/search?order=set&unique=prints&q=e" + \
                        urlencode(':', safe='') + f"{card_set}"
                    url_data = urllib.request.urlopen(
                        url, context=self.context).read()

                    set_json_data = json.loads(url_data)

                    result, result_string = self._process_scryfall_data(
                        set_json_data["data"])

                    while set_json_data["has_more"]:
                        url = set_json_data["next_page"]
                        url_data = urllib.request.urlopen(
                            url, context=self.context).read()
                        set_json_data = json.loads(url_data)
                        result, result_string = self._process_scryfall_data(
                            set_json_data["data"])

                    if self.card_dict:
                        result = True
                        break

                except Exception as error:
                    logger.error(url)
                    logger.error(error)

                if not result:
                    retry -= 1

                    if retry:
                        attempt_count = constants.CARD_RATINGS_ATTEMPT_MAX - retry
                        status.set(
                            f"""Collecting Scryfall Data - Request Failed ({attempt_count}/{constants.SCRYFALL_REQUEST_ATTEMPT_MAX}) - Retry in {constants.SCRYFALL_REQUEST_BACKOFF_DELAY_SECONDS} seconds""")
                        root.update()
                        time.sleep(
                            constants.SCRYFALL_REQUEST_BACKOFF_DELAY_SECONDS)
        return result, result_string

    def _initialize_17lands_data(self):
        '''Initialize the 17Lands data by setting the fields to 0 in case there are gaps in the downloaded card data'''
        for data in self.card_dict.values():
            initialize_card_data(data)

    def retrieve_17lands_data(self, sets, deck_colors, root, progress, initial_progress, status):
        '''Use the 17Lands endpoint to download the card ratings data for all of the deck filter options'''
        self.card_ratings = {}
        current_progress = 0
        result = False
        url = ""
        for set_code in sets:
            for color in deck_colors:
                retry = constants.CARD_RATINGS_ATTEMPT_MAX
                result = False
                while retry:

                    try:
                        status.set(f"Collecting {color} 17Lands Data")
                        root.update()
                        if self.user_group == constants.LIMITED_USER_GROUP_ALL:
                            user_group = ""
                        else:
                            user_group = "&user_group=" + self.user_group.lower()
                        url = f"https://www.17lands.com/card_ratings/data?expansion={set_code}&format={self.draft}&start_date={self.start_date}&end_date={self.end_date}{user_group}"
                        if color != constants.FILTER_OPTION_ALL_DECKS:
                            url += "&colors=" + color
                        url_data = urllib.request.urlopen(
                            url, context=self.context).read()

                        set_json_data = json.loads(url_data)
                        self._process_17lands_data(color, set_json_data)
                        result = True
                        break
                    except Exception as error:
                        logger.error(url)
                        logger.error(error)
                        retry -= 1

                        if retry:
                            attempt_count = constants.CARD_RATINGS_ATTEMPT_MAX - retry
                            status.set(
                                f"""Collecting {color} 17Lands Data - Request Failed ({attempt_count}/{constants.CARD_RATINGS_ATTEMPT_MAX}) - Retry in {constants.CARD_RATINGS_BACKOFF_DELAY_SECONDS} seconds""")
                            root.update()
                            time.sleep(
                                constants.CARD_RATINGS_BACKOFF_DELAY_SECONDS)

                if result:
                    current_progress += (3 /
                                         len(self.selected_sets.seventeenlands))
                    progress['value'] = current_progress + initial_progress
                    root.update()
                else:
                    break
                time.sleep(constants.CARD_RATINGS_INTER_DELAY_SECONDS)

        return result

    def _assemble_set(self, matching_only):
        '''Combine the 17Lands ratings and the card data to form the complete set data'''
        self.combined_data["card_ratings"] = {}
        for card, card_data in self.card_dict.items():
            if self._process_card_data(card_data):
                self.combined_data["card_ratings"][card] = card_data
            elif not matching_only:
                self.combined_data["card_ratings"][card] = card_data

    def retrieve_17lands_color_ratings(self):
        '''Use 17Lands endpoint to collect the data from the color_ratings page'''
        result = True
        game_count = 0
        try:
            if self.user_group == constants.LIMITED_USER_GROUP_ALL:
                user_group = ""
            else:
                user_group = "&user_group=" + self.user_group.lower()
            url = f"https://www.17lands.com/color_ratings/data?expansion={self.selected_sets.seventeenlands[0]}&event_type={self.draft}&start_date={self.start_date}&end_date={self.end_date}{user_group}&combine_splash=true"
            url_data = urllib.request.urlopen(url, context=self.context).read()

            color_json_data = json.loads(url_data)
            game_count = self._process_17lands_color_ratings(color_json_data)

        except Exception as error:
            result = False
            logger.error(url)
            logger.error(error)
        return result, game_count

    def _process_17lands_data(self, colors, cards):
        '''Parse the 17Lands json data to extract the card ratings'''
        result = True

        for card in cards:
            try:
                card_data = {constants.DATA_SECTION_RATINGS: [],
                             constants.DATA_SECTION_IMAGES: []}
                color_data = {colors: {}}
                for key, value in constants.DATA_FIELD_17LANDS_DICT.items():
                    if key == constants.DATA_SECTION_IMAGES:
                        for field in value:
                            if field in card and len(card[field]):
                                image_url = f"{constants.URL_17LANDS}{card[field]}" if card[field].startswith(
                                    constants.IMAGE_17LANDS_SITE_PREFIX) else card[field]
                                card_data[constants.DATA_SECTION_IMAGES].append(
                                    image_url)
                    elif value in card:
                        if (key in constants.WIN_RATE_OPTIONS) or (key == constants.DATA_FIELD_IWD):
                            color_data[colors][key] = round(
                                float(card[value]) * 100.0, 2) if card[value] else 0.0
                        elif ((key == constants.DATA_FIELD_ATA) or
                              (key == constants.DATA_FIELD_ALSA)):
                            color_data[colors][key] = round(float(card[value] if card[value] else 0.0), 2)
                        else:
                            color_data[colors][key] = int(card[value] if card[value] else 0)

                card_name = card[constants.DATA_FIELD_NAME]

                if card_name not in self.card_ratings:
                    self.card_ratings[card_name] = card_data

                self.card_ratings[card_name][constants.DATA_SECTION_RATINGS].append(
                    color_data)

            except Exception as error:
                result = False
                logger.error(error)

        return result

    def _process_17lands_color_ratings(self, colors):
        '''Parse the 17Lands json data to collect the color ratings'''
        color_ratings_dict = {
            "Mono-White": "W",
            "Mono-Blue": "U",
            "Mono-Black": "B",
            "Mono-Red": "R",
            "Mono-Green": "G",
            "(WU)": "WU",
            "(UB)": "UB",
            "(BR)": "BR",
            "(RG)": "RG",
            "(GW)": "GW",
            "(WB)": "WB",
            "(BG)": "BG",
            "(GU)": "GU",
            "(UR)": "UR",
            "(RW)": "RW",
            "(WUR)": "WUR",
            "(UBG)": "UBG",
            "(BRW)": "BRW",
            "(RGU)": "RGU",
            "(GWB)": "GWB",
            "(WUB)": "WUB",
            "(UBR)": "UBR",
            "(BRG)": "BRG",
            "(RGW)": "RGW",
            "(GWU)": "GWU",
        }
        game_count = 0
        try:
            self.combined_data["color_ratings"] = {}
            for color in colors:
                games = color["games"]
                if not color["is_summary"] and (games > 5000):
                    color_name = color["color_name"]
                    winrate = round(
                        (float(color["wins"])/color["games"]) * 100, 1)

                    color_label = [
                        x for x in color_ratings_dict if x in color_name]

                    if color_label:

                        processed_colors = color_ratings_dict[color_label[0]]

                        if processed_colors not in self.combined_data["color_ratings"]:
                            self.combined_data["color_ratings"][processed_colors] = winrate
                elif color["is_summary"] and color["color_name"] == "All Decks":
                    game_count = color["games"] if color["games"] else 0
                    self.combined_data["meta"]["game_count"] = game_count

        except Exception as error:
            logger.error(error)
        return game_count

    def _process_scryfall_data(self, data):
        '''Parse json data from the Scryfall API to extract pertinent card data'''
        result = False
        result_string = "Scryfall Data Unavailable"
        for card_data in data:
            try:
                if "arena_id" not in card_data:
                    continue

                arena_id = card_data["arena_id"]

                card_name = card_data[constants.DATA_FIELD_NAME]

                if card_data["layout"] == "transform":
                    card_name = card_name.split(" // ")[0]

                self.card_dict[arena_id] = {
                    constants.DATA_FIELD_NAME: card_name,
                    constants.DATA_FIELD_CMC: card_data[constants.DATA_FIELD_CMC],
                    constants.DATA_FIELD_COLORS: card_data["color_identity"],
                    constants.DATA_FIELD_TYPES: extract_types(card_data["type_line"]),
                    constants.DATA_FIELD_MANA_COST: 0,
                    constants.DATA_SECTION_IMAGES: [],
                }

                if "card_faces" in card_data:
                    self.card_dict[arena_id][constants.DATA_FIELD_MANA_COST] = card_data["card_faces"][0][constants.DATA_FIELD_MANA_COST]
                    self.card_dict[arena_id][constants.DATA_SECTION_IMAGES].append(
                        card_data["card_faces"][0]["image_uris"]["normal"])
                    self.card_dict[arena_id][constants.DATA_SECTION_IMAGES].append(
                        card_data["card_faces"][1]["image_uris"]["normal"])

                else:
                    self.card_dict[arena_id][constants.DATA_FIELD_MANA_COST] = card_data[constants.DATA_FIELD_MANA_COST]
                    self.card_dict[arena_id][constants.DATA_SECTION_IMAGES] = [
                        card_data["image_uris"]["normal"]]

                result = True

            except Exception as error:
                logger.error(error)
                result_string = error

        return result, result_string

    def _process_card_data(self, card):
        '''Link the 17Lands card ratings with the card data'''
        result = False
        try:
            card_name = card[constants.DATA_FIELD_NAME].replace("///", "//")
            matching_cards = [
                x for x in self.card_ratings if x == card_name]
            if matching_cards:
                ratings_card_name = matching_cards[0]
                deck_colors = self.card_ratings[ratings_card_name][constants.DATA_SECTION_RATINGS]

                card[constants.DATA_SECTION_IMAGES] = self.card_ratings[ratings_card_name][constants.DATA_SECTION_IMAGES]
                card[constants.DATA_FIELD_DECK_COLORS] = {}
                for color in self.deck_colors:
                    card[constants.DATA_FIELD_DECK_COLORS][color] = {
                        x: 0.0 for x in constants.DATA_FIELD_17LANDS_DICT if x != constants.DATA_SECTION_IMAGES}
                result = True
                for deck_color in deck_colors:
                    for key, value in deck_color.items():
                        for field in value:
                            card[constants.DATA_FIELD_DECK_COLORS][key][field] = value[field]

        except Exception as error:
            logger.error(error)

        return result

    def export_card_data(self):
        '''Build the file for the set data'''
        result = True
        try:
            output_file = "_".join(
                (self.selected_sets.seventeenlands[0], self.draft, self.user_group, constants.SET_FILE_SUFFIX))
            location = os.path.join(constants.SETS_FOLDER, output_file)

            with open(location, 'w', encoding="utf-8", errors="replace") as file:
                json.dump(self.combined_data, file)

            # Verify that the file was written
            write_data = check_file_integrity(location)

            if write_data[0] != Result.VALID:
                result = False

        except Exception as error:
            logger.error(error)
            result = False

        return result

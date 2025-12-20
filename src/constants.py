import os
import getpass

APPLICATION_VERSION = 3.36
OLD_APPLICATION_VERSION = "0320"
PREVIOUS_APPLICATION_VERSION = "0335"

FONT_SANS_SERIF = "Arial"
FONT_MONO_SPACE = "Courier"

BASIC_LANDS = ["Island", "Mountain", "Swamp", "Plains", "Forest"]

CARD_COLOR_SYMBOL_WHITE = "W"
CARD_COLOR_SYMBOL_BLACK = "B"
CARD_COLOR_SYMBOL_BLUE = "U"
CARD_COLOR_SYMBOL_RED = "R"
CARD_COLOR_SYMBOL_GREEN = "G"
CARD_COLOR_SYMBOL_NONE = "NC"

CARD_COLORS = [
    CARD_COLOR_SYMBOL_WHITE,
    CARD_COLOR_SYMBOL_BLUE,
    CARD_COLOR_SYMBOL_BLACK,
    CARD_COLOR_SYMBOL_RED,
    CARD_COLOR_SYMBOL_GREEN,
]

CARD_COLOR_LABEL_WHITE = "White"
CARD_COLOR_LABEL_BLACK = "Black"
CARD_COLOR_LABEL_BLUE = "Blue"
CARD_COLOR_LABEL_RED = "Red"
CARD_COLOR_LABEL_GREEN = "Green"
CARD_COLOR_LABEL_NC = "NC"

LIMITED_TYPE_UNKNOWN = 0
LIMITED_TYPE_DRAFT_PREMIER_V1 = 1
LIMITED_TYPE_DRAFT_PREMIER_V2 = 2
LIMITED_TYPE_DRAFT_QUICK = 3
LIMITED_TYPE_DRAFT_TRADITIONAL = 4
LIMITED_TYPE_SEALED = 5
LIMITED_TYPE_SEALED_TRADITIONAL = 6
LIMITED_TYPE_DRAFT_PICK_TWO = 7
LIMITED_TYPE_DRAFT_PICK_TWO_TRAD = 8
LIMITED_TYPE_DRAFT_PICK_TWO_QUICK = 9

DATA_FIELD_17LANDS_OHWR = "opening_hand_win_rate"
DATA_FIELD_17LANDS_NGOH = "opening_hand_game_count"
DATA_FIELD_17LANDS_GPWR = "win_rate"
DATA_FIELD_17LANDS_NGP = "game_count"
DATA_FIELD_17LANDS_GIHWR = "ever_drawn_win_rate"
DATA_FIELD_17LANDS_IWD = "drawn_improvement_win_rate"
DATA_FIELD_17LANDS_ALSA = "avg_seen"
DATA_FIELD_17LANDS_GIH = "ever_drawn_game_count"
DATA_FIELD_17LANDS_ATA = "avg_pick"
DATA_FIELD_17LANDS_NGND = "never_drawn_game_count"
DATA_FIELD_17LANDS_GNSWR = "never_drawn_win_rate"
DATA_FIELD_17LANDS_GDWR = "drawn_win_rate"
DATA_FIELD_17LANDS_NGD = "drawn_game_count"
DATA_FIELD_17LANDS_IMAGE = "url"
DATA_FIELD_17LANDS_IMAGE_BACK = "url_back"


DATA_FIELD_GIHWR = "gihwr"
DATA_FIELD_OHWR = "ohwr"
DATA_FIELD_GPWR = "gpwr"
DATA_FIELD_ALSA = "alsa"
DATA_FIELD_IWD = "iwd"
DATA_FIELD_ATA = "ata"
DATA_FIELD_NGP = "ngp"
DATA_FIELD_NGOH = "ngoh"
DATA_FIELD_GIH = "gih"
DATA_FIELD_GNSWR = "gnswr"
DATA_FIELD_NGND = "ngnd"
DATA_FIELD_GDWR = "gdwr"
DATA_FIELD_NGD = "ngd"
DATA_FIELD_WHEEL = "wheel"

DATA_SECTION_IMAGES = "image"
DATA_SECTION_RATINGS = "ratings"

DATA_FIELD_CMC = "cmc"
DATA_FIELD_COLORS = "colors"
DATA_FIELD_NAME = "name"
DATA_FIELD_TYPES = "types"
DATA_FIELD_DECK_COLORS = "deck_colors"
DATA_FIELD_COUNT = "count"
DATA_FIELD_DISABLED = "disabled"
DATA_FIELD_RARITY = "rarity"
DATA_FIELD_MANA_COST = "mana_cost"

DATA_FIELDS_LIST = [
    DATA_FIELD_GIHWR,
    DATA_FIELD_OHWR,
    DATA_FIELD_GPWR,
    DATA_FIELD_GNSWR,
    DATA_FIELD_ALSA,
    DATA_FIELD_ATA,
    DATA_FIELD_IWD,
    DATA_FIELD_NGP,
    DATA_FIELD_NGOH,
    DATA_FIELD_GIH,
    DATA_FIELD_NGND,
    DATA_FIELD_GDWR,
    DATA_FIELD_NGD,
]

DATA_SET_FIELDS = [
    DATA_FIELD_GIHWR,
    DATA_FIELD_OHWR,
    DATA_FIELD_GPWR,
    DATA_FIELD_ALSA,
    DATA_FIELD_IWD,
    DATA_FIELD_CMC,
    DATA_FIELD_COLORS,
    DATA_FIELD_NAME,
    DATA_FIELD_TYPES,
    DATA_FIELD_MANA_COST,
    DATA_SECTION_IMAGES,
    DATA_FIELD_DECK_COLORS,
]

FILTER_OPTION_ALL_DECKS = "All Decks"
FILTER_OPTION_AUTO = "Auto"
FILTER_OPTION_TIER = "TIER"

FIELD_LABEL_ATA = "ATA: Average Taken At"
FIELD_LABEL_ALSA = "ALSA: Average Last Seen At"
FIELD_LABEL_IWD = "IWD: Improvement When Drawn"
FIELD_LABEL_OHWR = "OHWR: Opening Hand Win Rate"
FIELD_LABEL_GPWR = "GPWR: Games Played Win Rate"
FIELD_LABEL_GIHWR = "GIHWR: Games In Hand Win Rate"
FIELD_LABEL_GNSWR = "GNSWR: Games Not Seen Win Rate"
FIELD_LABEL_COLORS = "COLORS: Card Colors"
FIELD_LABEL_DISABLED = "DISABLED: Remove Column"
FIELD_LABEL_COUNT = "COUNT: Total Card Count"
FIELD_LABEL_WHEEL = "WHEEL: Probability of Wheeling"
FIELD_LABEL_GDWR = "GDWR: Games Drawn Win Rate"

DATA_SET_VERSION_3 = 3.0

START_DATE_DEFAULT = "2019-01-01"

WIN_RATE_OPTIONS = [
    DATA_FIELD_GIHWR,
    DATA_FIELD_OHWR,
    DATA_FIELD_GPWR,
    DATA_FIELD_GNSWR,
    DATA_FIELD_GDWR,
]
NON_COLORS_OPTIONS = WIN_RATE_OPTIONS + [
    DATA_FIELD_IWD,
    DATA_FIELD_ALSA,
    DATA_FIELD_ATA,
]
COLUMN_OPTIONS = NON_COLORS_OPTIONS

COLUMN_2_DEFAULT = FIELD_LABEL_GIHWR
COLUMN_3_DEFAULT = FIELD_LABEL_DISABLED
COLUMN_4_DEFAULT = FIELD_LABEL_DISABLED
COLUMN_5_DEFAULT = FIELD_LABEL_DISABLED
COLUMN_6_DEFAULT = FIELD_LABEL_DISABLED
COLUMN_7_DEFAULT = FIELD_LABEL_DISABLED

DECK_FILTER_DEFAULT = FILTER_OPTION_AUTO

UI_SIZE_DEFAULT = "100%"

DRAFT_LOG_PREFIX = "DraftLog_"
DRAFT_LOG_FOLDER = os.path.join(os.getcwd(), "Logs")

DRAFT_DETECTION_CATCH_ALL = ["Draft", "draft"]

DRAFT_START_STRING_PREMIER = "[UnityCrossThreadLogger]==> Event_Join "
DRAFT_PICK_STRING_PREMIER = "[UnityCrossThreadLogger]==> Event_PlayerDraftMakePick "
DRAFT_PICK_STRING_PREMIER_OLD = "[UnityCrossThreadLogger]==> Draft.MakeHumanDraftPick "
DRAFT_P1P1_STRING_PREMIER = "CardsInPack"
DRAFT_PACK_STRING_PREMIER = "[UnityCrossThreadLogger]Draft.Notify "

DRAFT_START_STRING_QUICK_DRAFT = "[UnityCrossThreadLogger]==> BotDraft_DraftStatus "
DRAFT_PACK_STRING_QUICK = "DraftPack"
DRAFT_PICK_STRING_QUICK = "[UnityCrossThreadLogger]==> BotDraft_DraftPick "

DRAFT_START_STRINGS = [DRAFT_START_STRING_PREMIER, DRAFT_START_STRING_QUICK_DRAFT]

DATA_SOURCES_NONE = {"None": ""}

DECK_FILTER_FORMAT_NAMES = "Names"
DECK_FILTER_FORMAT_COLORS = "Colors"
DECK_FILTER_FORMAT_SET_NAMES = "Set Names"

DECK_FILTER_FORMAT_LIST = [DECK_FILTER_FORMAT_COLORS, DECK_FILTER_FORMAT_NAMES]

RESULT_FORMAT_WIN_RATE = "Percentage"
RESULT_FORMAT_RATING = "Rating"
RESULT_FORMAT_GRADE = "Grade"

RESULT_FORMAT_LIST = [RESULT_FORMAT_WIN_RATE, RESULT_FORMAT_RATING, RESULT_FORMAT_GRADE]

RESULT_UNKNOWN_STRING = " "
RESULT_UNKNOWN_VALUE = 0.0

LOCAL_DATA_FOLDER_PATH_WINDOWS = os.path.join(
    "Wizards of the Coast", "MTGA", "MTGA_Data"
)
LOCAL_DATA_FOLDER_PATH_OSX = os.path.join(
    "Library", "Application Support", "com.wizards.mtga"
)
LOCAL_DATA_FOLDER_PATH_LINUX = next(
    filter(
        os.path.exists,
        [
            # Steam
            os.path.join(
                os.path.expanduser("~"),
                ".local",
                "share",
                "Steam",
                "steamapps",
                "common",
                "MTGA",
                "MTGA_Data",
            ),
            # Steam (debian)
            os.path.join(
                os.path.expanduser("~"),
                ".steam",
                "debian-installation",
                "steamapps",
                "common",
                "MTGA",
                "MTGA_Data",
            ),
            # Lutris
            os.path.join(
                os.path.expanduser("~"),
                "Games",
                "magic-the-gathering-arena",
                "drive_c",
                "Program Files",
                "Wizards of the Coast",
                "MTGA",
                "MTGA_Data",
            ),
            # Bottles
            os.path.join(
                os.path.expanduser("~"),
                ".var",
                "app",
                "com.usebottles.bottles",
                "data",
                "bottles",
                "bottles",
                "MTG-Arena",
                "drive_c",
                "Program Files",
                "Wizards of the Coast",
                "MTGA",
                "MTGA_Data",
            ),
        ],
    ),
    None,
)

LOCAL_DOWNLOADS_DATA = os.path.join("Downloads", "Raw")

LOCAL_DATA_FILE_PREFIX_CARDS = "Raw_cards_"
LOCAL_DATA_FILE_PREFIX_DATABASE = "Raw_CardDatabase_"

LOCAL_DATABASE_TABLE_LOCALIZATION = "Localizations_enUS"
LOCAL_DATABASE_TABLE_ENUMERATOR = "Enums"
LOCAL_DATABASE_TABLE_CARDS = "Cards"

LOCAL_DATABASE_LOCALIZATION_COLUMN_ID = "LocId"
LOCAL_DATABASE_LOCALIZATION_COLUMN_FORMAT = "Formatted"
LOCAL_DATABASE_LOCALIZATION_COLUMN_TEXT = "Loc"

LOCAL_DATABASE_ENUMERATOR_COLUMN_ID = "LocId"
LOCAL_DATABASE_ENUMERATOR_COLUMN_TYPE = "Type"
LOCAL_DATABASE_ENUMERATOR_COLUMN_VALUE = "Value"

LOCAL_DATABASE_ENUMERATOR_TYPE_COLOR = "Color"
LOCAL_DATABASE_ENUMERATOR_TYPE_CARD_TYPES = "CardType"

LOCAL_DATABASE_LOCALIZATION_QUERY = f"""SELECT
                                            A.{LOCAL_DATABASE_LOCALIZATION_COLUMN_ID}, 
                                            A.{LOCAL_DATABASE_LOCALIZATION_COLUMN_FORMAT}, 
                                            A.{LOCAL_DATABASE_LOCALIZATION_COLUMN_TEXT}
                                        FROM {LOCAL_DATABASE_TABLE_LOCALIZATION} A INNER JOIN(
                                            SELECT 
                                                {LOCAL_DATABASE_LOCALIZATION_COLUMN_ID},
                                                min({LOCAL_DATABASE_LOCALIZATION_COLUMN_FORMAT}) AS MIN_FORMAT 
                                            FROM {LOCAL_DATABASE_TABLE_LOCALIZATION} 
                                            GROUP BY {LOCAL_DATABASE_LOCALIZATION_COLUMN_ID}) 
                                        B ON A.{LOCAL_DATABASE_LOCALIZATION_COLUMN_ID} = B.{LOCAL_DATABASE_LOCALIZATION_COLUMN_ID} 
                                        AND A.{LOCAL_DATABASE_LOCALIZATION_COLUMN_FORMAT} = B.MIN_FORMAT"""

LOCAL_DATABASE_ENUMERATOR_QUERY = f"""SELECT
                                        {LOCAL_DATABASE_ENUMERATOR_COLUMN_ID},
                                        {LOCAL_DATABASE_ENUMERATOR_COLUMN_TYPE},
                                        {LOCAL_DATABASE_ENUMERATOR_COLUMN_VALUE}
                                      FROM {LOCAL_DATABASE_TABLE_ENUMERATOR}
                                      WHERE {LOCAL_DATABASE_ENUMERATOR_COLUMN_TYPE} 
                                      IN ('{LOCAL_DATABASE_ENUMERATOR_TYPE_COLOR}', 
                                          '{LOCAL_DATABASE_ENUMERATOR_TYPE_CARD_TYPES}')"""

LOCAL_DATABASE_CARDS_QUERY = f"SELECT * FROM {LOCAL_DATABASE_TABLE_CARDS}"

LOCAL_CARDS_KEY_SET = "expansioncode"
LOCAL_CARDS_KEY_DIGITAL_RELEASE_SET = "digitalreleaseset"
LOCAL_CARDS_KEY_GROUP_ID = "grpid"
LOCAL_CARDS_KEY_TOKEN = "istoken"
LOCAL_CARDS_KEY_LINKED_FACES = "linkedfacegrpids"
LOCAL_CARDS_KEY_LINKED_FACE_TYPE = "linkedfacetype"
LOCAL_CARDS_KEY_TYPES = "types"
LOCAL_CARDS_KEY_TITLE_ID = "titleid"
LOCAL_CARDS_KEY_CMC = "cmc"
LOCAL_CARDS_KEY_COLOR_ID = "coloridentity"
LOCAL_CARDS_KEY_CASTING_COST = "oldschoolmanatext"
LOCAL_CARDS_KEY_RARITY = "rarity"
LOCAL_CARDS_KEY_PRIMARY = "isprimarycard"

SETS_FOLDER = os.path.join(os.getcwd(), "Sets")
SET_FILE_SUFFIX = "Data.json"

SCRYFALL_REQUEST_BACKOFF_DELAY_SECONDS = 5
SCRYFALL_REQUEST_ATTEMPT_MAX = 5

DATASET_DOWNLOAD_RATE_LIMIT_SEC = 60

PLATFORM_ID_OSX = "darwin"
PLATFORM_ID_WINDOWS = "win32"
PLATFORM_ID_LINUX = "linux"

LOG_NAME = "Player.log"

LOG_LOCATION_WINDOWS = os.path.join(
    "Users",
    getpass.getuser(),
    "AppData",
    "LocalLow",
    "Wizards Of The Coast",
    "MTGA",
    LOG_NAME,
)
LOG_LOCATION_OSX = os.path.join(
    "Library", "Logs", "Wizards of the Coast", "MTGA", LOG_NAME
)
LOG_LOCATION_LINUX = os.path.join(
    ".local",
    "share",
    "Steam",
    "steamapps",
    "compatdata",
    "2141910",
    "pfx",
    "drive_c",
    "users",
    "steamuser",
    "AppData",
    "LocalLow",
    "Wizards Of The Coast",
    "MTGA",
    LOG_NAME,
)

DEFAULT_GIHWR_AVERAGE = 0.0

WINDOWS_DRIVES = ["C:/", "D:/", "E:/", "F:/"]
WINDOWS_PROGRAM_FILES = ["Program Files", "Program Files (x86)"]

LIMITED_TYPE_STRING_DRAFT_PREMIER = "PremierDraft"
LIMITED_TYPE_STRING_DRAFT_QUICK = "QuickDraft"
LIMITED_TYPE_STRING_DRAFT_BOT = "BotDraft"
LIMITED_TYPE_STRING_DRAFT_TRAD = "TradDraft"
LIMITED_TYPE_STRING_SEALED = "Sealed"
LIMITED_TYPE_STRING_TRAD_SEALED = "TradSealed"
LIMITED_TYPE_STRING_DRAFT_PICK_TWO = "PickTwoDraft"
LIMITED_TYPE_STRING_DRAFT_PICK_TWO_TRAD = "PickTwoTradDraft"
LIMITED_TYPE_STRING_DRAFT_PICK_TWO_QUICK = "PickTwoQuickDraft"

LIMITED_TYPE_LIST = [
    LIMITED_TYPE_STRING_DRAFT_PREMIER,
    LIMITED_TYPE_STRING_DRAFT_QUICK,
    LIMITED_TYPE_STRING_DRAFT_TRAD,
    LIMITED_TYPE_STRING_SEALED,
    LIMITED_TYPE_STRING_TRAD_SEALED,
    LIMITED_TYPE_STRING_DRAFT_PICK_TWO,
    LIMITED_TYPE_STRING_DRAFT_PICK_TWO_TRAD,
]

LIMITED_USER_GROUP_ALL = "All"
LIMITED_USER_GROUP_BOTTOM = "Bottom"
LIMITED_USER_GROUP_MIDDLE = "Middle"
LIMITED_USER_GROUP_TOP = "Top"

LIMITED_GROUPS_LIST = [
    LIMITED_USER_GROUP_ALL,
    LIMITED_USER_GROUP_TOP,
    LIMITED_USER_GROUP_MIDDLE,
    LIMITED_USER_GROUP_BOTTOM,
]

SET_TYPE_EXPANSION = "expansion"
SET_TYPE_ALCHEMY = "alchemy"
SET_TYPE_MASTERS = "masters"
SET_TYPE_MASTERPIECE = "masterpiece"
SET_TYPE_CORE = "core"
SET_TYPE_DRAFT_INNOVATION = "draft_innovation"

SET_LIST_ARENA = "arena"
SET_LIST_SCRYFALL = "scryfall"
SET_LIST_17LANDS = "17Lands"

SET_LIST_FIELDS = [SET_LIST_ARENA, SET_LIST_SCRYFALL, SET_LIST_17LANDS]

SET_START_DATE = "start_date"

SET_SELECTION_ALL = "ALL"
SET_SELECTION_CUBE = "CUBE"

SET_RELEASE_OFFSET_DAYS = -7
SET_LIST_COUNT_MAX = 50

SET_ARENA_CUBE_START_OFFSET_DAYS = -25

SUPPORTED_SET_TYPES = [
    SET_TYPE_EXPANSION,
    SET_TYPE_ALCHEMY,
    SET_TYPE_MASTERS,
    SET_TYPE_CORE,
    SET_TYPE_DRAFT_INNOVATION,
]

TABLE_STYLE = "Treeview"

TEMP_FOLDER = os.path.join(os.getcwd(), "Temp")
TEMP_LOCALIZATION_FILE = os.path.join(TEMP_FOLDER, "temp_localization.json")
TEMP_CARD_DATA_FILE = os.path.join(TEMP_FOLDER, "temp_card_data.json")

BW_ROW_COLOR_ODD_TAG = "bw_odd"
BW_ROW_COLOR_EVEN_TAG = "bw_even"
CARD_ROW_COLOR_WHITE_TAG = "white_card"
CARD_ROW_COLOR_RED_TAG = "red_card"
CARD_ROW_COLOR_BLUE_TAG = "blue_card"
CARD_ROW_COLOR_BLACK_TAG = "black_card"
CARD_ROW_COLOR_GREEN_TAG = "green_card"
CARD_ROW_COLOR_GOLD_TAG = "gold_card"
CARD_ROW_COLOR_COLORLESS_TAG = "colorless_card"

LETTER_GRADE_A_PLUS = "A+"
LETTER_GRADE_A = "A "
LETTER_GRADE_A_MINUS = "A-"
LETTER_GRADE_B_PLUS = "B+"
LETTER_GRADE_B = "B "
LETTER_GRADE_B_MINUS = "B-"
LETTER_GRADE_C_PLUS = "C+"
LETTER_GRADE_C = "C "
LETTER_GRADE_C_MINUS = "C-"
LETTER_GRADE_D_PLUS = "D+"
LETTER_GRADE_D = "D "
LETTER_GRADE_D_MINUS = "D-"
LETTER_GRADE_F = "F "
LETTER_GRADE_NA = " "
LETTER_GRADE_SB = "SB"

CARD_TYPE_CREATURE = "Creature"
CARD_TYPE_PLANESWALKER = "Planeswalker"
CARD_TYPE_INSTANT = "Instant"
CARD_TYPE_SORCERY = "Sorcery"
CARD_TYPE_ENCHANTMENT = "Enchantment"
CARD_TYPE_ARTIFACT = "Artifact"
CARD_TYPE_LAND = "Land"

CARD_TYPE_SELECTION_ALL = "All Cards"
CARD_TYPE_SELECTION_CREATURES = "Creatures"
CARD_TYPE_SELECTION_NONCREATURES = "Noncreatures"
CARD_TYPE_SELECTION_NON_LANDS = "Non-Lands"

TABLE_MISSING = "missing"
TABLE_PACK = "pack"
TABLE_COMPARE = "compare"
TABLE_TAKEN = "taken"
TABLE_SUGGEST = "suggest"
TABLE_STATS = "stats"
TABLE_SETS = "sets"

CARD_RARITY_COMMON = "common"
CARD_RARITY_UNCOMMON = "uncommon"
CARD_RARITY_RARE = "rare"
CARD_RARITY_MYTHIC = "mythic"

# Dictionaries
# Used to identify the limited type based on log string
LIMITED_TYPES_DICT = {
    LIMITED_TYPE_STRING_DRAFT_PREMIER: LIMITED_TYPE_DRAFT_PREMIER_V1,
    LIMITED_TYPE_STRING_DRAFT_QUICK: LIMITED_TYPE_DRAFT_QUICK,
    LIMITED_TYPE_STRING_DRAFT_TRAD: LIMITED_TYPE_DRAFT_TRADITIONAL,
    LIMITED_TYPE_STRING_DRAFT_BOT: LIMITED_TYPE_DRAFT_QUICK,
    LIMITED_TYPE_STRING_SEALED: LIMITED_TYPE_SEALED,
    LIMITED_TYPE_STRING_TRAD_SEALED: LIMITED_TYPE_SEALED_TRADITIONAL,
    LIMITED_TYPE_STRING_DRAFT_PICK_TWO: LIMITED_TYPE_DRAFT_PICK_TWO,
    LIMITED_TYPE_STRING_DRAFT_PICK_TWO_TRAD: LIMITED_TYPE_DRAFT_PICK_TWO_TRAD,
    LIMITED_TYPE_STRING_DRAFT_PICK_TWO_QUICK: LIMITED_TYPE_DRAFT_PICK_TWO_QUICK,
}

COLOR_NAMES_DICT = {
    "W": CARD_COLOR_LABEL_WHITE,
    "U": CARD_COLOR_LABEL_BLUE,
    "B": CARD_COLOR_LABEL_BLACK,
    "R": CARD_COLOR_LABEL_RED,
    "G": CARD_COLOR_LABEL_GREEN,
    "WU": "Azorius",
    "UB": "Dimir",
    "BR": "Rakdos",
    "RG": "Gruul",
    "WG": "Selesnya",
    "WB": "Orzhov",
    "BG": "Golgari",
    "UG": "Simic",
    "UR": "Izzet",
    "WR": "Boros",
    "WUR": "Jeskai",
    "UBG": "Sultai",
    "WBR": "Mardu",
    "URG": "Temur",
    "WBG": "Abzan",
    "WUB": "Esper",
    "UBR": "Grixis",
    "BRG": "Jund",
    "WRG": "Naya",
    "WUG": "Bant",
    "WUBR": "Not-Green",
    "UBRG": "Not-White",
    "WBRG": "Not-Blue",
    "WURG": "Not-Black",
    "WUBG": "Not-Red",
    "WUBRG": "Five-Color",
}
DECK_COLORS = [FILTER_OPTION_ALL_DECKS] + [k for k in COLOR_NAMES_DICT.keys()]
DECK_FILTERS = [FILTER_OPTION_AUTO] + DECK_COLORS

CARD_COLORS_DICT = {
    CARD_COLOR_LABEL_WHITE: CARD_COLOR_SYMBOL_WHITE,
    CARD_COLOR_LABEL_BLACK: CARD_COLOR_SYMBOL_BLACK,
    CARD_COLOR_LABEL_BLUE: CARD_COLOR_SYMBOL_BLUE,
    CARD_COLOR_LABEL_RED: CARD_COLOR_SYMBOL_RED,
    CARD_COLOR_LABEL_GREEN: CARD_COLOR_SYMBOL_GREEN,
    CARD_COLOR_LABEL_NC: "",
}

PLATFORM_LOG_DICT = {
    PLATFORM_ID_OSX: LOG_LOCATION_OSX,
    PLATFORM_ID_WINDOWS: LOG_LOCATION_WINDOWS,
}

WIN_RATE_FIELDS_DICT = {
    DATA_FIELD_GIHWR: DATA_FIELD_GIH,
    DATA_FIELD_OHWR: DATA_FIELD_NGOH,
    DATA_FIELD_GPWR: DATA_FIELD_NGP,
    DATA_FIELD_GNSWR: DATA_FIELD_NGND,
    DATA_FIELD_GDWR: DATA_FIELD_NGD,
}

DATA_FIELD_17LANDS_DICT = {
    DATA_FIELD_GIHWR: DATA_FIELD_17LANDS_GIHWR,
    DATA_FIELD_OHWR: DATA_FIELD_17LANDS_OHWR,
    DATA_FIELD_GPWR: DATA_FIELD_17LANDS_GPWR,
    DATA_FIELD_ALSA: DATA_FIELD_17LANDS_ALSA,
    DATA_FIELD_IWD: DATA_FIELD_17LANDS_IWD,
    DATA_FIELD_ATA: DATA_FIELD_17LANDS_ATA,
    DATA_FIELD_NGP: DATA_FIELD_17LANDS_NGP,
    DATA_FIELD_NGOH: DATA_FIELD_17LANDS_NGOH,
    DATA_FIELD_GIH: DATA_FIELD_17LANDS_GIH,
    DATA_FIELD_GNSWR: DATA_FIELD_17LANDS_GNSWR,
    DATA_FIELD_NGND: DATA_FIELD_17LANDS_NGND,
    DATA_FIELD_GDWR: DATA_FIELD_17LANDS_GDWR,
    DATA_FIELD_NGD: DATA_FIELD_17LANDS_NGD,
    DATA_SECTION_IMAGES: [DATA_FIELD_17LANDS_IMAGE, DATA_FIELD_17LANDS_IMAGE_BACK],
}

COLUMNS_OPTIONS_MAIN_DICT = {
    FIELD_LABEL_ATA: DATA_FIELD_ATA,
    FIELD_LABEL_ALSA: DATA_FIELD_ALSA,
    FIELD_LABEL_IWD: DATA_FIELD_IWD,
    FIELD_LABEL_OHWR: DATA_FIELD_OHWR,
    FIELD_LABEL_GPWR: DATA_FIELD_GPWR,
    FIELD_LABEL_GIHWR: DATA_FIELD_GIHWR,
    FIELD_LABEL_GDWR: DATA_FIELD_GDWR,
    FIELD_LABEL_GNSWR: DATA_FIELD_GNSWR,
    FIELD_LABEL_WHEEL: DATA_FIELD_WHEEL,
    FIELD_LABEL_COLORS: DATA_FIELD_COLORS,
}

COLUMNS_OPTIONS_EXTRA_DICT = {
    FIELD_LABEL_DISABLED: DATA_FIELD_DISABLED,
    FIELD_LABEL_ATA: DATA_FIELD_ATA,
    FIELD_LABEL_ALSA: DATA_FIELD_ALSA,
    FIELD_LABEL_IWD: DATA_FIELD_IWD,
    FIELD_LABEL_OHWR: DATA_FIELD_OHWR,
    FIELD_LABEL_GPWR: DATA_FIELD_GPWR,
    FIELD_LABEL_GIHWR: DATA_FIELD_GIHWR,
    FIELD_LABEL_GDWR: DATA_FIELD_GDWR,
    FIELD_LABEL_GNSWR: DATA_FIELD_GNSWR,
    FIELD_LABEL_WHEEL: DATA_FIELD_WHEEL,
    FIELD_LABEL_COLORS: DATA_FIELD_COLORS,
}

STATS_HEADER_CONFIG = {
    "Colors": {"width": 0.19, "anchor": "w"},
    "1": {"width": 0.11, "anchor": "c"},
    "2": {"width": 0.11, "anchor": "c"},
    "3": {"width": 0.11, "anchor": "c"},
    "4": {"width": 0.11, "anchor": "c"},
    "5": {"width": 0.11, "anchor": "c"},
    "6+": {"width": 0.11, "anchor": "c"},
    "Total": {"width": 0.15, "anchor": "c"},
}

ROW_TAGS_BW_DICT = {
    BW_ROW_COLOR_ODD_TAG: (FONT_SANS_SERIF, "#3d3d3d", "#e6ecec"),
    BW_ROW_COLOR_EVEN_TAG: (FONT_SANS_SERIF, "#333333", "#e6ecec"),
}

ROW_TAGS_COLORS_DICT = {
    CARD_ROW_COLOR_WHITE_TAG: (FONT_SANS_SERIF, "#E9E9E9", "#000000"),
    CARD_ROW_COLOR_RED_TAG: (FONT_SANS_SERIF, "#FF6C6C", "#000000"),
    CARD_ROW_COLOR_BLUE_TAG: (FONT_SANS_SERIF, "#6078c6", "#000000"),
    CARD_ROW_COLOR_BLACK_TAG: (FONT_SANS_SERIF, "#BFBFBF", "#000000"),
    CARD_ROW_COLOR_GREEN_TAG: (FONT_SANS_SERIF, "#60BC68", "#000000"),
    CARD_ROW_COLOR_GOLD_TAG: (FONT_SANS_SERIF, "#F0BE26", "#000000"),
    CARD_ROW_COLOR_COLORLESS_TAG: (FONT_SANS_SERIF, "#8e9eae", "#000000"),
}

GRADE_ORDER_DICT = {
    LETTER_GRADE_A_PLUS: 14,
    LETTER_GRADE_A: 13,
    LETTER_GRADE_A_MINUS: 12,
    LETTER_GRADE_B_PLUS: 11,
    LETTER_GRADE_B: 10,
    LETTER_GRADE_B_MINUS: 9,
    LETTER_GRADE_C_PLUS: 8,
    LETTER_GRADE_C: 7,
    LETTER_GRADE_C_MINUS: 6,
    LETTER_GRADE_D_PLUS: 5,
    LETTER_GRADE_D: 4,
    LETTER_GRADE_D_MINUS: 3,
    LETTER_GRADE_F: 2,
    LETTER_GRADE_SB: 1,
    LETTER_GRADE_NA: 0,
}

TIER_CONVERSION_RATINGS_GRADES_DICT = {
    LETTER_GRADE_A_PLUS: 5.0,
    LETTER_GRADE_A: 4.6,
    LETTER_GRADE_A_MINUS: 4.2,
    LETTER_GRADE_B_PLUS: 3.8,
    LETTER_GRADE_B: 3.5,
    LETTER_GRADE_B_MINUS: 3.1,
    LETTER_GRADE_C_PLUS: 2.7,
    LETTER_GRADE_C: 2.3,
    LETTER_GRADE_C_MINUS: 1.9,
    LETTER_GRADE_D_PLUS: 1.5,
    LETTER_GRADE_D: 1.2,
    LETTER_GRADE_D_MINUS: 0.8,
    LETTER_GRADE_F: 0.4,
}

GRADE_DEVIATION_DICT = {
    LETTER_GRADE_A_PLUS: 2.00,
    LETTER_GRADE_A: 1.67,
    LETTER_GRADE_A_MINUS: 1.33,
    LETTER_GRADE_B_PLUS: 1,
    LETTER_GRADE_B: 0.67,
    LETTER_GRADE_B_MINUS: 0.33,
    LETTER_GRADE_C_PLUS: 0,
    LETTER_GRADE_C: -0.33,
    LETTER_GRADE_C_MINUS: -0.67,
    LETTER_GRADE_D_PLUS: -1.00,
    LETTER_GRADE_D: -1.33,
    LETTER_GRADE_D_MINUS: -1.67,
}

CARD_TYPE_DICT = {
    CARD_TYPE_SELECTION_ALL: (
        [
            CARD_TYPE_CREATURE,
            CARD_TYPE_PLANESWALKER,
            CARD_TYPE_INSTANT,
            CARD_TYPE_SORCERY,
            CARD_TYPE_ENCHANTMENT,
            CARD_TYPE_ARTIFACT,
            CARD_TYPE_LAND,
        ],
        True,
        False,
        True,
    ),
    CARD_TYPE_SELECTION_CREATURES: ([CARD_TYPE_CREATURE], True, False, True),
    CARD_TYPE_SELECTION_NONCREATURES: ([CARD_TYPE_CREATURE], False, False, True),
    CARD_TYPE_SELECTION_NON_LANDS: (
        [
            CARD_TYPE_CREATURE,
            CARD_TYPE_PLANESWALKER,
            CARD_TYPE_INSTANT,
            CARD_TYPE_SORCERY,
            CARD_TYPE_ENCHANTMENT,
            CARD_TYPE_ARTIFACT,
        ],
        True,
        False,
        True,
    ),
}

TABLE_PROPORTIONS = [(1,), (0.75, 0.25), (0.60, 0.20, 0.20), (0.46, 0.18, 0.18, 0.18)]

# TODO: Where are these values from?
# My understanding is this array is an array for values for each of the first six packs
# The four values are used in a numpy polyval with the ALSA
# Meaning if you have a card with an ALSA of 7.2 in pack #1, then your wheel % would be
# -0.46*(7.2^3) + 7.97*(7.2^2) - 27.43*7.2 + 26.61 = 70.6% (69.4% in MTGAZone article)
# For pack #6: 0.25*(7.2^3) +-2.65*(7.2^2) + 9.76*7.2 - 11.21 = 15.0% (13.0% in MTGAZone article)
# The numbers seem reasonable, but don't know if it is generalized from a set's draft data?
# https://mtgazone.com/how-to-wheel-in-drafts/ is the best I could find online and the percentages are close
WHEEL_COEFFICIENTS = [
    [-0.46, 7.97, -27.43, 26.61],
    [-0.33, 6.31, -23.12, 23.86],
    [-0.19, 4.39, -17.06, 17.71],
    [-0.06, 2.27, -9.22, 9.43],
    [0.08, 0.15, -1.88, 2.36],
    [0.25, -2.65, 9.76, -11.21],
]

CARD_RARITY_DICT = {
    1: CARD_RARITY_COMMON,
    2: CARD_RARITY_COMMON,
    3: CARD_RARITY_UNCOMMON,
    4: CARD_RARITY_RARE,
    5: CARD_RARITY_MYTHIC,
}

UI_SIZE_DICT = {
    "80%": 0.8,
    "90%": 0.9,
    "100%": 1.0,
    "110%": 1.1,
    "120%": 1.2,
    "130%": 1.3,
    "140%": 1.4,
    "150%": 1.5,
    "160%": 1.6,
    "170%": 1.7,
    "180%": 1.8,
    "190%": 1.9,
    "200%": 2.0,
    "210%": 2.1,
    "220%": 2.2,
    "230%": 2.3,
    "240%": 2.4,
    "250%": 2.5,
}

PACK_PARSER_URL = "https://us-central1-mtgalimited.cloudfunctions.net/pack_parser"

SCREENSHOT_FOLDER = os.path.join(os.getcwd(), "Screenshots")
SCREENSHOT_PREFIX = "p1p1_screenshot_"

PICK_TWO_EVENT_STRING = "PickTwo"

CARD_RATINGS_BACKOFF_DELAY_SECONDS = 30
CARD_RATINGS_INTER_DELAY_SECONDS = 1
CARD_RATINGS_ATTEMPT_MAX = 5

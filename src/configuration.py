"""This module encompasses functions for reading from, writing to, and resetting the configuration file"""

import json
import os
import sys
from pydantic import BaseModel, field_validator, Field
from typing import Tuple
from src import constants
from src.logger import create_logger

logger = create_logger()


def get_config_path():
    """Returns the platform-specific path for the configuration file."""
    app_name = "MTGA_Draft_Tool"
    if sys.platform == "win32":
        base_path = os.getenv("APPDATA")
    elif sys.platform == "darwin":
        base_path = os.path.expanduser("~/Library/Application Support")
    else:  # Linux/Unix
        base_path = os.path.expanduser("~/.config")

    config_dir = os.path.join(base_path, app_name)
    if not os.path.exists(config_dir):
        os.makedirs(config_dir)

    return os.path.join(config_dir, "config.json")


# Use local config if it exists (Development mode), otherwise use User Data path
LOCAL_CONFIG = os.path.join(os.getcwd(), "config.json")
if os.path.exists(LOCAL_CONFIG):
    CONFIG_FILE = LOCAL_CONFIG
    logger.info(f"Using local configuration file: {CONFIG_FILE}")
else:
    CONFIG_FILE = get_config_path()
    logger.info(f"Using system configuration file: {CONFIG_FILE}")


class DeckType(BaseModel):
    """This class holds the data for the various deck types (Aggro, Mid, and Control)"""

    distribution: list = Field(default_factory=lambda: [0, 0, 0, 0, 0, 0, 0])
    maximum_card_count: int = 0
    recommended_creature_count: int = 0
    cmc_average: float = 0.0


class Settings(BaseModel):
    """This class holds UI settings"""

    table_width: int = 270
    column_2: str = constants.COLUMNS_OPTIONS_EXTRA_DICT[constants.COLUMN_2_DEFAULT]
    column_3: str = constants.COLUMNS_OPTIONS_EXTRA_DICT[constants.COLUMN_3_DEFAULT]
    column_4: str = constants.COLUMNS_OPTIONS_EXTRA_DICT[constants.COLUMN_4_DEFAULT]
    column_5: str = constants.COLUMNS_OPTIONS_EXTRA_DICT[constants.COLUMN_5_DEFAULT]
    column_6: str = constants.COLUMNS_OPTIONS_EXTRA_DICT[constants.COLUMN_6_DEFAULT]
    column_7: str = constants.COLUMNS_OPTIONS_EXTRA_DICT[constants.COLUMN_7_DEFAULT]
    deck_filter: str = constants.DECK_FILTER_DEFAULT
    filter_format: str = constants.DECK_FILTER_FORMAT_COLORS
    result_format: str = constants.RESULT_FORMAT_WIN_RATE
    ui_size: str = constants.UI_SIZE_DEFAULT
    theme: str = "Dark"
    theme_base: str = "clam" # aqua, vista, clam, etc.
    theme_palette: str = "Neutral" # Forest, Island, etc.
    theme_custom_path: str = "" # Path to user's .tcl file
    card_colors_enabled: bool = False
    missing_enabled: bool = True
    stats_enabled: bool = False
    auto_highest_enabled: bool = True
    curve_bonus_enabled: bool = False
    color_bonus_enabled: bool = False
    draft_log_enabled: bool = True
    p1p1_ocr_enabled: bool = True
    save_screenshot_enabled: bool = False
    color_identity_enabled: bool = False
    current_draft_enabled: bool = True
    data_source_enabled: bool = True
    deck_filter_enabled: bool = True
    refresh_button_enabled: bool = True
    update_notifications_enabled: bool = True
    missing_notifications_enabled: bool = True
    taken_alsa_enabled: bool = False
    taken_ata_enabled: bool = False
    taken_gpwr_enabled: bool = False
    taken_ohwr_enabled: bool = False
    taken_gdwr_enabled: bool = False
    taken_gndwr_enabled: bool = False
    taken_iwd_enabled: bool = False
    taken_wheel_enabled: bool = False
    arena_log_location: str = ""
    database_location: str = ""
    signals_enabled: bool = True

    @field_validator("deck_filter")
    @classmethod
    def validate_deck_filter(cls, value, info):
        allowed_values = constants.DECK_FILTERS
        if value not in allowed_values:
            return cls.model_fields[info.field_name].default
        return value

    @field_validator("filter_format")
    @classmethod
    def validate_filter_format(cls, value, info):
        allowed_values = constants.DECK_FILTER_FORMAT_LIST
        if value not in allowed_values:
            return cls.model_fields[info.field_name].default
        return value

    @field_validator("result_format")
    @classmethod
    def validate_result_format(cls, value, info):
        allowed_values = constants.RESULT_FORMAT_LIST
        if value not in allowed_values:
            return cls.model_fields[info.field_name].default
        return value

    @field_validator("ui_size")
    @classmethod
    def validate_ui_size(cls, value, info):
        allowed_values = constants.UI_SIZE_DICT
        if value not in allowed_values:
            return cls.model_fields[info.field_name].default
        return value


class CardLogic(BaseModel):
    """This class represents the configuration for card logic within the application"""

    minimum_creatures: int = 9
    minimum_noncreatures: int = 6
    ratings_threshold: int = 500
    alsa_weight: float = 0.0
    iwd_weight: float = 0.0
    deck_mid: DeckType = DeckType(
        distribution=[0, 0, 4, 3, 2, 1, 0],
        maximum_card_count=23,
        recommended_creature_count=15,
        cmc_average=3.04,
    )
    deck_aggro: DeckType = DeckType(
        distribution=[0, 2, 5, 3, 0, 0, 0],
        maximum_card_count=24,
        recommended_creature_count=17,
        cmc_average=2.40,
    )
    deck_control: DeckType = DeckType(
        distribution=[0, 0, 3, 2, 2, 1, 0],
        maximum_card_count=22,
        recommended_creature_count=10,
        cmc_average=3.68,
    )


class Features(BaseModel):
    """This class represents a collection of features that can be enabled or disabled within the overlay"""

    override_scale_factor: float = 0.0
    hotkey_enabled: bool = True
    images_enabled: bool = True


class CardData(BaseModel):
    """This class holds the data used for building a card list from the local Arena files"""

    database_size: int = 0
    latest_dataset: str = ""
    last_check: float = 0
    last_auto_check: float = 0


class Configuration(BaseModel):
    """This class groups together the data stored in the config.json file"""

    settings: Settings = Field(default_factory=lambda: Settings())
    card_logic: CardLogic = Field(default_factory=lambda: CardLogic())
    features: Features = Field(default_factory=lambda: Features())
    card_data: CardData = Field(default_factory=lambda: CardData())


def read_configuration(file_location: str = CONFIG_FILE) -> Tuple[Configuration, bool]:
    """function is responsible for reading the contents of file and storing it as a Configuration object"""
    config_object = Configuration()
    success = False

    try:
        with open(file_location, "r", encoding="utf8", errors="replace") as data:
            config_data = json.loads(data.read())

        config_object = Configuration.model_validate(config_data)
        success = True
    except (FileNotFoundError, json.JSONDecodeError) as error:
        logger.error(error)

    return config_object, success


def write_configuration(
    config_object: Configuration, file_location: str = CONFIG_FILE
) -> bool:
    """function is responsible for writing the contents of a Configuration object to a specified file location"""
    success = False

    try:
        with open(file_location, "w", encoding="utf8", errors="replace") as data:
            json.dump(config_object.model_dump(), data, ensure_ascii=False, indent=4)
        success = True
    except (FileNotFoundError, TypeError, OSError) as error:
        logger.error(error)

    return success


def reset_configuration(file_location: str = CONFIG_FILE) -> bool:
    """function is responsible for reseting the contents of a Configuration object to a specified file location"""
    config_object = Configuration()
    success = False
    try:
        with open(file_location, "w", encoding="utf8", errors="replace") as data:
            json.dump(config_object.model_dump(), data, ensure_ascii=False, indent=4)
        success = True
    except (FileNotFoundError, TypeError, OSError) as error:
        logger.error(error)

    return success


if not os.path.exists(CONFIG_FILE):
    reset_configuration(CONFIG_FILE)

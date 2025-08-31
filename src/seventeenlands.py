from dataclasses import dataclass, field
from typing import List, Dict, Any, Tuple
import requests
from src.logger import create_logger
from src.constants import (
    WIN_RATE_OPTIONS,
    DATA_FIELD_17LANDS_DICT,
    DATA_SECTION_IMAGES,
    DATA_FIELD_NAME,
    LIMITED_USER_GROUP_ALL,
    FILTER_OPTION_ALL_DECKS,
    DATA_FIELD_IWD,
    DATA_FIELD_ATA,
    DATA_FIELD_ALSA,
    DATA_SECTION_RATINGS
)

URL_17LANDS = "https://www.17lands.com"
IMAGE_17LANDS_SITE_PREFIX = "/static/images/"
COLOR_FILTER = [
    "W", "U", "B", "R", "G", "WU", "UB", "BR", "RG", "GW", "WB", "BG", "GU", "UR", "RW",
    "WUR", "UBG", "BRW", "RGU", "GWB", "WUB", "UBR", "BRG", "RGW", "GWU",
]
REQUEST_TIMEOUT = 30
COLOR_WIN_RATE_GAME_COUNT_THRESHOLD = 5000

logger = create_logger()

class Seventeenlands():
    def _build_card_ratings_url(self, set_code, draft, start_date, end_date, user_group, color):
        user_group_param = "" if user_group == LIMITED_USER_GROUP_ALL else f"&user_group={user_group.lower()}"
        url = (
            f"https://www.17lands.com/card_ratings/data?expansion={set_code}"
            f"&format={draft}&start_date={start_date}&end_date={end_date}{user_group_param}"
        )
        if color != FILTER_OPTION_ALL_DECKS:
            url += f"&colors={color}"
        return url

    def download_card_ratings(
        self,
        set_code: str,
        colors: str,
        draft: str,
        start_date: str,
        end_date: str,
        user_group: str,
        card_data: Dict
    ):
        """
        Fetch card ratings from 17Lands with retry, progress, and UI update logic.
        """
        url = self._build_card_ratings_url(set_code, draft, start_date, end_date, user_group, colors)
        try:
            response = requests.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            set_json_data = response.json()
            self._process_card_ratings(colors, set_json_data, card_data)
        except Exception as error:
            logger.error(url)
            logger.error(error)

    def download_color_ratings(
        self,
        set_code: str,
        draft: str,
        start_date: str,
        end_date: str,
        user_group: str,
        color_filter: List = None
    ):
        color_filter = color_filter or COLOR_FILTER
        url = self._build_color_ratings_url(set_code, draft, start_date, end_date, user_group)
        try:
            response = requests.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            color_json_data = response.json()
            return self._process_color_ratings(color_json_data, color_filter)
        except Exception as error:
            logger.error(url)
            logger.error(error)
            return ({}, 0)

    def _process_card_ratings(
        self,
        color: str,
        cards: Dict[str, Any],
        card_data: Dict
    ) -> Dict:
        for card in cards:
            try:
                name = card.get(DATA_FIELD_NAME, "")
                if name not in card_data:
                    card_data[name] = {DATA_SECTION_RATINGS: [], DATA_SECTION_IMAGES: []}
                # Images
                for data_field in DATA_FIELD_17LANDS_DICT[DATA_SECTION_IMAGES]:
                    if data_field in card and card[data_field]:
                        image_url = (
                            f"{URL_17LANDS}{card[data_field]}"
                            if card[data_field].startswith(IMAGE_17LANDS_SITE_PREFIX)
                            else card[data_field]
                        )
                        if image_url not in card_data[name][DATA_SECTION_IMAGES]:
                            card_data[name][DATA_SECTION_IMAGES].append(image_url)
                # Ratings
                color_data = {color: {}}
                for key, value in DATA_FIELD_17LANDS_DICT.items():
                    if key == DATA_SECTION_IMAGES:
                        continue
                    if value in card:
                        if key in WIN_RATE_OPTIONS or key == DATA_FIELD_IWD:
                            color_data[color][key] = round(float(card[value]) * 100.0, 2) if card[value] else 0.0
                        elif key in (DATA_FIELD_ATA, DATA_FIELD_ALSA):
                            color_data[color][key] = round(float(card[value] or 0.0), 2)
                        else:
                            color_data[color][key] = int(card[value] or 0)
                card_data[name][DATA_SECTION_RATINGS].append(color_data)
            except Exception as error:
                logger.error(error)
        return card_data

    def _build_color_ratings_url(self, set_code, draft, start_date, end_date, user_group):
        user_group_param = "" if user_group == LIMITED_USER_GROUP_ALL else f"&user_group={user_group.lower()}"
        return (
            f"https://www.17lands.com/color_ratings/data?expansion={set_code}"
            f"&event_type={draft}&start_date={start_date}&end_date={end_date}"
            f"{user_group_param}&combine_splash=true"
        )

    def _process_color_ratings(
        self,
        colors: dict,
        color_filter: list
    ):
        color_ratings = {}
        game_count = 0
        for color in colors:
            try:
                if not color["is_summary"] and color["games"] > COLOR_WIN_RATE_GAME_COUNT_THRESHOLD:
                    color_name = color["short_name"]
                    winrate = round((float(color["wins"]) / color["games"]) * 100, 1)
                    if color_filter and color_name not in color_filter:
                        continue
                    color_ratings[color_name] = winrate
                elif color["is_summary"] and color["color_name"] == "All Decks":
                    game_count = color.get("games", 0)
            except Exception as error:
                logger.error(error)
        return (color_ratings, game_count)

from typing import List, Dict, Any
import requests
import re
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
    DATA_SECTION_RATINGS,
    DECK_COLORS,
)

URL_17LANDS = "https://www.17lands.com"
IMAGE_17LANDS_SITE_PREFIX = "/static/images/"
COLOR_FILTER = [c for c in DECK_COLORS if c not in [FILTER_OPTION_ALL_DECKS, "Auto"]]
REQUEST_TIMEOUT = 30
COLOR_WIN_RATE_GAME_COUNT_THRESHOLD = 5000

logger = create_logger()


class Seventeenlands:
    def build_card_ratings_url(
        self, set_code, draft, start_date, end_date, user_group, color
    ):
        from src.utils import normalize_color_string

        user_group_param = (
            ""
            if user_group == LIMITED_USER_GROUP_ALL
            else f"&user_group={user_group.lower()}"
        )
        std_color = normalize_color_string(color)
        url = (
            f"https://www.17lands.com/card_ratings/data?expansion={set_code}"
            f"&format={draft}&start_date={start_date}&end_date={end_date}{user_group_param}"
        )
        if std_color != FILTER_OPTION_ALL_DECKS:
            url += f"&colors={std_color}"
        return url

    def download_card_ratings(
        self, set_code, colors, draft, start_date, end_date, user_group, card_data
    ):
        from src.utils import normalize_color_string

        url = self.build_card_ratings_url(
            set_code, draft, start_date, end_date, user_group, colors
        )
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        self.process_card_ratings(
            normalize_color_string(colors), response.json(), card_data
        )

    def download_color_ratings(
        self, set_code, draft, start_date, end_date, user_group, color_filter=None
    ):
        url = self._build_color_ratings_url(
            set_code, draft, start_date, end_date, user_group
        )
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return self._process_color_ratings(
            response.json(), color_filter or COLOR_FILTER
        )

    def process_card_ratings(self, color, cards, card_data):
        for card in cards:
            try:
                name = card.get(DATA_FIELD_NAME, "")
                if name not in card_data:
                    card_data[name] = {
                        DATA_SECTION_RATINGS: [],
                        DATA_SECTION_IMAGES: [],
                    }
                for data_field in DATA_FIELD_17LANDS_DICT[DATA_SECTION_IMAGES]:
                    if data_field in card and card[data_field]:
                        img = (
                            f"{URL_17LANDS}{card[data_field]}"
                            if card[data_field].startswith(IMAGE_17LANDS_SITE_PREFIX)
                            else card[data_field]
                        )
                        if img not in card_data[name][DATA_SECTION_IMAGES]:
                            card_data[name][DATA_SECTION_IMAGES].append(img)
                color_data = {color: {}}
                for key, value in DATA_FIELD_17LANDS_DICT.items():
                    if key == DATA_SECTION_IMAGES:
                        continue
                    if value in card:
                        if key in WIN_RATE_OPTIONS or key == DATA_FIELD_IWD:
                            color_data[color][key] = (
                                round(float(card[value]) * 100.0, 2)
                                if card[value]
                                else 0.0
                            )
                        elif key in (DATA_FIELD_ATA, DATA_FIELD_ALSA):
                            color_data[color][key] = round(float(card[value] or 0.0), 2)
                        else:
                            color_data[color][key] = int(card[value] or 0)
                card_data[name][DATA_SECTION_RATINGS].append(color_data)
            except Exception as error:
                logger.error(error)
        return card_data

    def _build_color_ratings_url(
        self, set_code, draft, start_date, end_date, user_group
    ):
        user_group_param = (
            ""
            if user_group == LIMITED_USER_GROUP_ALL
            else f"&user_group={user_group.lower()}"
        )
        return f"https://www.17lands.com/color_ratings/data?expansion={set_code}&event_type={draft}&start_date={start_date}&end_date={end_date}{user_group_param}&combine_splash=true"

    def _process_color_ratings(self, colors_json: List[Dict], color_filter: list):
        from src.utils import normalize_color_string

        color_ratings = {}
        game_count = 0
        for entry in colors_json:
            try:
                if entry.get("is_summary"):
                    if entry.get("color_name") == "All Decks":
                        game_count = entry.get("games", 0)
                    continue

                raw_code = entry.get("short_name", "")
                if not raw_code:
                    match = re.search(r"\((.*?)\)", entry.get("color_name", ""))
                    raw_code = match.group(1) if match else ""

                if not raw_code:
                    continue
                std_key = normalize_color_string(raw_code)

                if entry.get("games", 0) >= COLOR_WIN_RATE_GAME_COUNT_THRESHOLD:
                    winrate = round(
                        (float(entry.get("wins", 0)) / entry.get("games", 1)) * 100, 1
                    )
                    color_ratings[std_key] = winrate
            except Exception:
                continue

        return (color_ratings, game_count)

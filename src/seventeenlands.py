"""
src/seventeenlands.py
Professional, Rate-Limited 17Lands Client.
"""

import requests
import time
import os
import json
import logging
from typing import List, Dict, Any, Optional
from src.utils import is_cache_stale, normalize_color_string

logger = logging.getLogger(__name__)


class Seventeenlands:
    URL_BASE = "https://www.17lands.com"
    HEADERS = {
        "User-Agent": "MTGADraftTool/3.38 (Educational Tool; https://github.com/unrealities/MTGA_Draft_17Lands)"
    }
    CACHE_DIR = os.path.join(os.getcwd(), "Temp", "RawCache")
    ARCHETYPES = ["All", "WU", "UB", "BR", "RG", "WG", "WB", "UR", "BG", "WR", "UG"]

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        if not os.path.exists(self.CACHE_DIR):
            os.makedirs(self.CACHE_DIR)

    def download_set_data(
        self,
        set_code: str,
        draft_format: str,
        colors: List[str] = None,
        user_group: str = "All",
        progress_callback=None,
    ) -> Dict[str, Any]:
        """
        Builds a full multi-archetype dataset.
        """
        master_card_map = {}
        target_colors = colors if colors else self.ARCHETYPES

        start_time = time.time()

        for i, color in enumerate(target_colors):
            pct = int((i / len(target_colors)) * 100)

            if progress_callback:
                elapsed = time.time() - start_time
                if i > 0:
                    # Calculate rolling average time per request
                    avg_time = elapsed / i
                    rem_time = avg_time * (len(target_colors) - i)
                else:
                    # Initial guess: ~1.5s delay + ~0.5s network time per archetype
                    rem_time = 2.0 * len(target_colors)

                rem_mins = int(rem_time // 60)
                rem_secs = int(rem_time % 60)
                eta_str = f"{rem_mins}m {rem_secs}s" if rem_mins > 0 else f"{rem_secs}s"

                msg = f"Downloading '{color}' ({i+1}/{len(target_colors)}) - {pct}% [ETA: {eta_str}]"
                progress_callback(msg, pct)

            # Fetch raw data (from cache or network)
            raw_data, from_cache = self._fetch_archetype_with_cache(
                set_code, draft_format, color, user_group
            )

            # Process into master map
            self._process_archetype_data(color, raw_data, master_card_map)

            # Throttle ONLY if we actually hit the network, otherwise blast through cache!
            if not from_cache:
                time.sleep(1.5)

        if progress_callback:
            progress_callback("Finalizing Dataset...", 100)

        return master_card_map

    def _fetch_archetype_with_cache(
        self, set_code: str, draft_format: str, color: str, user_group: str = "All"
    ):
        """Retrieves data from 17Lands, prioritizing the local raw cache."""
        ug_label = user_group if user_group and user_group != "All" else "All"
        cache_name = f"{set_code}_{draft_format}_{color}_{ug_label}.json".lower()
        cache_path = os.path.join(self.CACHE_DIR, cache_name)

        if not is_cache_stale(cache_path, hours=24):
            logger.info(f"Using cached 17Lands data for {set_code}/{color}/{ug_label}")
            try:
                with open(cache_path, "r") as f:
                    return json.load(f), True
            except json.JSONDecodeError:
                pass  # Cache corrupt, fetch new

        # Build URL
        url = (
            f"{self.URL_BASE}/card_ratings/data?expansion={set_code.upper()}"
            f"&format={draft_format}"
        )
        if color != "All" and color != "All Decks":
            url += f"&colors={color}"
        if user_group and user_group != "All":
            url += f"&user_group={user_group}"

        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()

        # Save to cache
        with open(cache_path, "w") as f:
            json.dump(data, f)

        return data, False

    def _process_archetype_data(
        self, color_key: str, raw_list: List[Dict], card_map: Dict
    ):
        internal_color_key = (
            "All Decks" if color_key == "All" or color_key == "All Decks" else color_key
        )

        for card in raw_list:
            name = card.get("name")
            if not name:
                continue

            if name not in card_map:
                card_map[name] = {
                    "name": name,
                    "image": self._extract_images(card),
                    "deck_colors": {},
                }

            card_map[name]["deck_colors"][internal_color_key] = {
                "gihwr": round(float(card.get("ever_drawn_win_rate") or 0) * 100, 2),
                "ohwr": round(float(card.get("opening_hand_win_rate") or 0) * 100, 2),
                "gpwr": round(float(card.get("win_rate") or 0) * 100, 2),
                "gnswr": round(float(card.get("never_drawn_win_rate") or 0) * 100, 2),
                "gdwr": round(float(card.get("drawn_win_rate") or 0) * 100, 2),
                "alsa": round(float(card.get("avg_seen") or 0), 2),
                "ata": round(float(card.get("avg_pick") or 0), 2),
                "iwd": round(
                    float(card.get("drawn_improvement_win_rate") or 0) * 100, 2
                ),
                "samples": int(card.get("ever_drawn_game_count") or 0),
            }

    def _extract_images(self, card_data: Dict) -> List[str]:
        imgs = []
        for f in ["url", "url_back"]:
            val = card_data.get(f)
            if val:
                imgs.append(
                    f"{self.URL_BASE}{val}" if val.startswith("/static") else val
                )
        return imgs

    def download_color_ratings(
        self,
        set_code,
        draft,
        start_date,
        end_date,
        user_group,
        threshold=5000,
        color_filter=None,
    ):
        """Retrieves general color performance data."""
        params = {
            "expansion": set_code,
            "event_type": draft,
            "start_date": start_date,
            "end_date": end_date,
            "combine_splash": True,
        }
        if user_group and user_group.lower() != "all":
            params["user_group"] = user_group

        url = f"{self.URL_BASE}/color_ratings/data"
        response = self.session.get(url, params=params, timeout=30)

        if response.status_code == 429:
            raise Exception(
                "Rate Limited (HTTP 429). You are requesting data too fast."
            )
        if response.status_code == 403:
            raise Exception(
                "Access Denied (HTTP 403). 17Lands is blocking the request."
            )

        response.raise_for_status()
        data = response.json()

        results, game_count = self._process_color_ratings(data, color_filter, threshold)
        return results, game_count

    def _process_color_ratings(self, data, color_filter, threshold=5000):
        results = {}
        game_count = 0
        for entry in data:
            if entry.get("is_summary"):
                game_count = entry.get("games", 0)

            color_key = entry.get("short_name")
            if not color_key:
                color_name = entry.get("color_name", "")
                if "All Decks" in color_name:
                    color_key = "All Decks"
                else:
                    import re

                    match = re.search(r"\((.*?)\)", color_name)
                    if match:
                        color_key = match.group(1)

            if color_key:
                normalized_key = normalize_color_string(color_key)
                if not color_filter or normalized_key in color_filter:
                    games = entry.get("games", 0)
                    if games >= threshold:
                        wins = entry.get("wins", 0)
                        winrate = (wins / games) * 100 if games > 0 else 0.0
                        results[normalized_key] = round(winrate, 1)
        return results, game_count

    # RESTORED LEGACY METHOD
    def download_card_ratings(
        self, set_code, color, draft, start_date, end_date, user_group, card_data
    ):
        """
        Legacy method to populate a card dictionary with 17Lands data.
        Restored to prevent potential regressions in flows relying on it.
        """
        params = {
            "expansion": set_code,
            "format": draft,
            "start_date": start_date,
            "end_date": end_date,
            "colors": color if color != "All Decks" else None,
        }

        if user_group and user_group.lower() != "all":
            params["user_group"] = user_group

        url = f"{self.URL_BASE}/card_ratings/data"
        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        self.process_card_ratings(color, data, card_data)

    def process_card_ratings(self, color, data, card_data):
        from src import constants

        for card in data:
            name = card.get("name")
            if not name:
                continue

            if name not in card_data:
                card_data[name] = {
                    constants.DATA_SECTION_IMAGES: [],
                    constants.DATA_SECTION_RATINGS: [],
                }

            if "url" in card and card["url"]:
                img = card["url"]
                if img.startswith("/static"):
                    img = f"{self.URL_BASE}{img}"
                if img not in card_data[name][constants.DATA_SECTION_IMAGES]:
                    card_data[name][constants.DATA_SECTION_IMAGES].append(img)

            entry = {
                constants.DATA_FIELD_GIHWR: float(
                    card.get("ever_drawn_win_rate") or 0.0
                )
                * 100,
                constants.DATA_FIELD_ALSA: float(card.get("avg_seen") or 0.0),
                constants.DATA_FIELD_IWD: float(
                    card.get("drawn_improvement_win_rate") or 0.0
                )
                * 100,
                constants.DATA_FIELD_NGD: int(card.get("drawn_game_count") or 0),
                constants.DATA_FIELD_OHWR: float(
                    card.get("opening_hand_win_rate") or 0.0
                )
                * 100,
                constants.DATA_FIELD_GPWR: float(card.get("win_rate") or 0.0) * 100,
            }
            card_data[name][constants.DATA_SECTION_RATINGS].append({color: entry})

    def build_card_ratings_url(
        self, set_code, draft, start_date, end_date, user_group, color
    ):
        base = f"{self.URL_BASE}/card_ratings/data?expansion={set_code}&format={draft}&start_date={start_date}&end_date={end_date}"
        if user_group and user_group != "All":
            base += f"&user_group={user_group}"
        if color and color != "All Decks":
            base += f"&colors={color}"
        return base

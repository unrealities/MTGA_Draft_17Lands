"""
src/seventeenlands.py
Professional, Rate-Limited 17Lands Client.
Supports Archetype-Specific performance data with a 24-hour raw cache.
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
    # Identify the app to 17Lands as per professional standards
    HEADERS = {
        "User-Agent": "MTGADraftTool/3.38 (Educational Tool; https://github.com/unrealities/MTGA_Draft_17Lands)"
    }
    CACHE_DIR = os.path.join(os.getcwd(), "Temp", "RawCache")

    # Standard color pairs for Archetype Fit logic
    ARCHETYPES = ["All", "WU", "UB", "BR", "RG", "WG", "WB", "UR", "BG", "WR", "UG"]

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        if not os.path.exists(self.CACHE_DIR):
            os.makedirs(self.CACHE_DIR)

    def download_set_data(
        self, set_code: str, draft_format: str, progress_callback=None
    ) -> Dict[str, Any]:
        """
        Public entry point to build a full multi-archetype dataset.
        """
        master_card_map = {}

        for i, color in enumerate(self.ARCHETYPES):
            if progress_callback:
                progress_callback(
                    f"Fetching {color} Archetype...", (i / len(self.ARCHETYPES)) * 100
                )

            raw_data = self._fetch_archetype_with_cache(set_code, draft_format, color)
            self._process_archetype_data(color, raw_data, master_card_map)

            # Respectful Throttling: Sleep 1.5s between network calls if not from cache
            # This is the 'Elite' way to avoid hitting rate limits.
            # We only sleep if the previous call was a real network request (simplified here).
            time.sleep(1.5)

        return master_card_map

    def _fetch_archetype_with_cache(
        self, set_code: str, draft_format: str, color: str
    ) -> List[Dict]:
        """Retrieves data from 17Lands, prioritizing the local raw cache."""
        cache_name = f"{set_code}_{draft_format}_{color}.json".lower()
        cache_path = os.path.join(self.CACHE_DIR, cache_name)

        if not is_cache_stale(cache_path, hours=24):
            logger.info(f"Using cached 17Lands data for {set_code}/{color}")
            with open(cache_path, "r") as f:
                return json.load(f)

        # Cache is stale or missing - go to network
        url = (
            f"{self.URL_BASE}/card_ratings/data?expansion={set_code.upper()}"
            f"&format={draft_format}"
        )
        if color != "All":
            url += f"&colors={color}"

        try:
            response = self.session.get(url, timeout=20)
            response.raise_for_status()
            data = response.json()

            # Update cache immediately
            with open(cache_path, "w") as f:
                json.dump(data, f)

            return data
        except Exception as e:
            logger.error(f"17Lands API Failure ({color}): {e}")
            return []

    def _process_archetype_data(
        self, color_key: str, raw_list: List[Dict], card_map: Dict
    ):
        """Merges individual archetype stats into the master card objects."""
        # 17Lands 'All' maps to our 'All Decks' filter
        internal_color_key = "All Decks" if color_key == "All" else color_key

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

            # Store the performance data for this specific archetype
            card_map[name]["deck_colors"][internal_color_key] = {
                "gihwr": round(float(card.get("ever_drawn_win_rate") or 0) * 100, 2),
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

    # --- RESTORED LEGACY METHODS FOR COMPATIBILITY ---

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
        """
        Retrieves win rate data for color archetypes (e.g. 'WU', 'All Decks').
        Used by FileExtractor to determine available deck filters.
        """
        params = {
            "expansion": set_code,
            "event_type": draft,
            "start_date": start_date,
            "end_date": end_date,
            "combine_splash": False,
            "user_group": user_group,
        }

        url = f"{self.URL_BASE}/color_ratings/data"
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            return self._process_color_ratings(data, color_filter, threshold)

        except Exception as e:
            logger.error(f"Failed to download color ratings: {e}")
            return {}, 0

    def _process_color_ratings(self, data, color_filter, threshold=5000):
        results = {}
        game_count = 0

        for entry in data:
            if entry.get("is_summary"):
                game_count = entry.get("games", 0)

            # Logic to extract color label (e.g. "UB" or "All Decks")
            color_key = entry.get("short_name")
            if not color_key:
                # Fallback for "All Decks" or malformed entries
                color_name = entry.get("color_name", "")
                if "All Decks" in color_name:
                    color_key = "All Decks"
                else:
                    # Attempt to extract from "Dimir (UB)"
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

    def download_card_ratings(
        self, set_code, color, draft, start_date, end_date, user_group, card_data
    ):
        """
        Legacy method to populate a card dictionary with 17Lands data.
        Used by FileExtractor._download_expansion.
        """
        params = {
            "expansion": set_code,
            "format": draft,
            "start_date": start_date,
            "end_date": end_date,
            "user_group": user_group,
            "colors": color if color != "All Decks" else None,
        }

        url = f"{self.URL_BASE}/card_ratings/data"
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            self.process_card_ratings(color, data, card_data)
        except Exception as e:
            logger.error(f"Failed to download card ratings for {color}: {e}")

    def process_card_ratings(self, color, data, card_data):
        """Helper to map API response to internal structure."""
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

            # Process Images
            if "url" in card and card["url"]:
                img_url = card["url"]
                if img_url.startswith("/static"):
                    img_url = f"{self.URL_BASE}{img_url}"
                if img_url not in card_data[name][constants.DATA_SECTION_IMAGES]:
                    card_data[name][constants.DATA_SECTION_IMAGES].append(img_url)

            # Process Ratings
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

            # Append dictionary for this color to the ratings list
            card_data[name][constants.DATA_SECTION_RATINGS].append({color: entry})

    def build_card_ratings_url(
        self, set_code, draft, start_date, end_date, user_group, color
    ):
        """Helper for building the URL string (used by tests)."""
        base = f"{self.URL_BASE}/card_ratings/data?expansion={set_code}&format={draft}&start_date={start_date}&end_date={end_date}"
        if user_group and user_group != "All":
            base += f"&user_group={user_group}"
        if color and color != "All Decks":
            base += f"&colors={color}"
        return base

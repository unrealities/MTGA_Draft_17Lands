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
        self,
        set_code: str,
        draft_format: str,
        colors: List[str] = None,
        progress_callback=None,
    ) -> Dict[str, Any]:
        """
        Public entry point to build a full multi-archetype dataset.
        Allows passing a dynamic list of colors to fetch.
        """
        master_card_map = {}

        # Use dynamic colors if provided, otherwise default to standard pairs
        target_colors = colors if colors else self.ARCHETYPES

        for i, color in enumerate(target_colors):
            if progress_callback:
                progress_callback(
                    f"Fetching {color} Archetype...", (i / len(target_colors)) * 100
                )

            # Let exceptions bubble up here to be handled by the UI/Extractor
            raw_data = self._fetch_archetype_with_cache(set_code, draft_format, color)
            self._process_archetype_data(color, raw_data, master_card_map)

            # Respectful Throttling: Sleep 1.5s between network calls if not from cache
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

        # 'All' in our logic maps to no color param in API
        if color != "All" and color != "All Decks":
            url += f"&colors={color}"

        # No try/except here - we want failures to bubble up for retry logic
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()

        # Update cache immediately
        with open(cache_path, "w") as f:
            json.dump(data, f)

        return data

    def _process_archetype_data(
        self, color_key: str, raw_list: List[Dict], card_map: Dict
    ):
        """Merges individual archetype stats into the master card objects."""
        # 17Lands 'All' maps to our 'All Decks' filter
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
            "combine_splash": True,
        }

        # Only add user_group if it's NOT "All".
        # 17Lands API defaults to "All" if omitted, but sometimes fails if "All" is sent explicitly string.
        if user_group and user_group.lower() != "all":
            params["user_group"] = user_group

        url = f"{self.URL_BASE}/color_ratings/data"
        logger.info(f"Requesting Color Ratings: {url} | Params: {params}")

        # We explicitly DO NOT catch exceptions here.
        # The caller (FileExtractor) needs to see the crash to trigger its retry loop.
        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()

        try:
            data = response.json()
        except json.JSONDecodeError:
            logger.error(f"Color Ratings Response was not JSON: {response.text[:200]}")
            raise Exception("Invalid JSON response from 17Lands")

        logger.info(f"Color Ratings Response: Received {len(data)} entries")

        results, game_count = self._process_color_ratings(data, color_filter, threshold)

        # DEBUG: If results are empty, log the raw data to see what happened
        if not results and data:
            logger.warning(
                f"Color Ratings processing yielded 0 results. Raw Data Sample: {str(data)[:500]}"
            )

        return results, game_count

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
                # If no filter is provided (normal case for full dataset download),
                # or if the key matches the filter
                if not color_filter or normalized_key in color_filter:
                    games = entry.get("games", 0)
                    if games >= threshold:
                        wins = entry.get("wins", 0)
                        winrate = (wins / games) * 100 if games > 0 else 0.0
                        results[normalized_key] = round(winrate, 1)
                    else:
                        # DEBUG: Log skipped entries to diagnose missing stats
                        # Only log if it's "All Decks" or a standard pair to avoid log spam from splashing
                        if normalized_key == "All Decks" or (
                            color_filter and normalized_key in color_filter
                        ):
                            logger.info(
                                f"Color Rating Skipped (Threshold {threshold}): {normalized_key} has {games} games"
                            )

        logger.info(
            f"Processed Color Ratings: {len(results)} valid archetypes found. Total Game Count: {game_count}"
        )
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
            "colors": color if color != "All Decks" else None,
        }

        # Consistent user_group handling
        if user_group and user_group.lower() != "all":
            params["user_group"] = user_group

        url = f"{self.URL_BASE}/card_ratings/data"
        # Letting exceptions bubble up for consistency with new retry logic
        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        self.process_card_ratings(color, data, card_data)

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

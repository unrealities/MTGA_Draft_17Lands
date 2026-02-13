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
from src.utils import is_cache_stale

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

"""
src/scryfall_tagger.py
Harvests community-sourced card tags from the Scryfall Oracle Tags (otag) project.
Implements Set-Level caching to prevent redundant API calls.
"""

import requests
import time
import logging
import os
import json
from typing import Dict, List
from src.utils import is_cache_stale

logger = logging.getLogger(__name__)


class ScryfallTagger:
    BASE_URL = "https://api.scryfall.com/cards/search"
    HEADERS = {
        "User-Agent": "MTGADraftTool/5.0 (Educational Tool)",
        "Accept": "application/json",
    }
    CACHE_DIR = os.path.join(os.getcwd(), "Temp", "RawCache")

    # Define the community tags we care about for the Pro-Tour engine
    TAG_QUERIES = {
        "removal": "otag:removal OR otag:board-wipe OR otag:pacifism OR otag:counterspell",
        "combat_trick": "otag:combat-trick",
        "fixing": "otag:mana-fixing OR otag:fetchland OR otag:mana-dork OR otag:mana-ramp",
        "card_draw": "otag:card-draw OR otag:card-selection OR otag:cantrip",
        "evasion": "otag:evasion",
        "mana_sink": "otag:mana-sink",
    }

    def __init__(self):
        if not os.path.exists(self.CACHE_DIR):
            os.makedirs(self.CACHE_DIR)

    def harvest_set_tags(self, set_code: str) -> Dict[str, List[str]]:
        """
        Queries Scryfall for specific tags in a set.
        Checks local cache first to prevent redundant network calls.
        """
        cache_path = os.path.join(
            self.CACHE_DIR, f"{set_code.lower()}_scryfall_tags.json"
        )

        # 1. CHECK CACHE (Valid for 24 hours. If a set is brand new, tags update frequently in the first few days)
        if not is_cache_stale(cache_path, hours=24):
            logger.info(f"Using cached Scryfall tags for {set_code}")
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                pass  # Cache corrupt, fallback to fetching

        # 2. FETCH FROM SCRYFALL
        logger.info(
            f"Cache miss/stale. Harvesting Scryfall tags for {set_code} from network..."
        )
        card_tags = {}

        for tag_name, query_string in self.TAG_QUERIES.items():
            q = f"set:{set_code} is:booster ({query_string})"

            try:
                self._fetch_and_map_tags(q, tag_name, card_tags)
            except Exception as e:
                logger.error(
                    f"Failed to harvest Scryfall tag '{tag_name}' for {set_code}: {e}"
                )

            # Respect Scryfall's rate limit (100ms recommended, using 200ms to be safe)
            time.sleep(0.2)

        # 3. SAVE TO CACHE
        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(card_tags, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to write Scryfall tags cache: {e}")

        return card_tags

    def _fetch_and_map_tags(
        self, query: str, tag_name: str, card_tags: Dict[str, List[str]]
    ):
        """Handles pagination and mapping the API response."""
        url = f"{self.BASE_URL}?q={requests.utils.quote(query)}"

        while url:
            response = requests.get(url, headers=self.HEADERS, timeout=10)
            if response.status_code == 404:
                # 404 means no cards matched the tag in this set, which is expected for some mechanics
                break
            response.raise_for_status()

            data = response.json()
            for card in data.get("data", []):
                # Handle split cards (Scryfall uses " // ", we use " // ")
                name = card.get("name", "").replace("///", "//")

                if name not in card_tags:
                    card_tags[name] = []
                card_tags[name].append(tag_name)

            url = data.get("next_page")
            if url:
                time.sleep(0.1)

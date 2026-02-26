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

    TAG_QUERIES = {
        "removal": "otag:removal OR otag:board-wipe OR otag:pacifism OR otag:counterspell OR otag:bounce OR otag:edict OR otag:burn",
        "combat_trick": "otag:combat-trick OR otag:pump-spell",
        "enhancement": "otag:aura OR otag:equipment OR otag:vehicle",
        "fixing_ramp": "otag:mana-fixing OR otag:fetchland OR otag:mana-dork OR otag:mana-rock OR otag:treasure OR otag:ramp",
        "card_advantage": "otag:card-draw OR otag:card-selection OR otag:recursion OR otag:tutor OR otag:cantrip OR kw:investigate OR kw:surveil",
        "evasion": "otag:evasion OR kw:flying OR kw:menace OR kw:trample",
        "mana_sink": "otag:mana-sink",
        "token_maker": "otag:token-generator",
        "lifegain": "otag:lifegain OR kw:lifelink",
        "protection": "otag:hexproof-granter OR otag:indestructible-granter OR otag:protection-spell OR otag:blink OR otag:flicker",
        "hate": "otag:graveyard-hate OR otag:artifact-destruction OR otag:enchantment-destruction",
    }

    def __init__(self):
        if not os.path.exists(self.CACHE_DIR):
            os.makedirs(self.CACHE_DIR)

    def harvest_set_tags(
        self, set_code: str, progress_callback=None
    ) -> Dict[str, List[str]]:
        """
        Queries Scryfall for specific tags in a set.
        """
        # FIX: Explicitly abort for Cubes to prevent API abuse
        if "CUBE" in set_code.upper():
            logger.info(
                f"Skipping Scryfall community tags for {set_code} to prevent API abuse."
            )
            if progress_callback:
                progress_callback("Skipping tags for Cube...", 100)
            return {}

        safe_set_code = set_code.lower().replace(" ", "")
        cache_path = os.path.join(self.CACHE_DIR, f"{safe_set_code}_scryfall_tags.json")

        # 1. CHECK CACHE
        if not is_cache_stale(cache_path, hours=24):
            logger.info(f"Using cached Scryfall tags for {set_code}")
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                pass  # Cache corrupt, fallback to fetching

        # 2. FETCH FROM SCRYFALL
        logger.info(f"Harvesting Scryfall tags for {set_code} from network...")
        card_tags = {}
        total_tags = len(self.TAG_QUERIES)

        for i, (tag_name, query_string) in enumerate(self.TAG_QUERIES.items()):
            # Update UI with live progress
            if progress_callback:
                progress_callback(
                    f"Harvesting Tags: '{tag_name}' ({i+1}/{total_tags})", 100
                )

            q = f"set:{set_code} is:booster ({query_string})"
            try:
                self._fetch_and_map_tags(q, tag_name, card_tags)
            except Exception as e:
                logger.error(
                    f"Failed to harvest Scryfall tag '{tag_name}' for {set_code}: {e}"
                )

            time.sleep(0.2)  # Respect Scryfall limits

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
            retries = 3
            success = False

            while retries > 0:
                try:
                    response = requests.get(url, headers=self.HEADERS, timeout=15)
                    success = True
                    break
                except requests.exceptions.RequestException:
                    retries -= 1
                    time.sleep(2)

            if not success:
                break

            if response.status_code == 404:
                # 404 means no cards matched the tag in this chunk
                break
            response.raise_for_status()

            data = response.json()
            for card in data.get("data", []):
                name = card.get("name", "").replace("///", "//")
                if name not in card_tags:
                    card_tags[name] = []
                if tag_name not in card_tags[name]:
                    card_tags[name].append(tag_name)

            url = data.get("next_page")
            if url:
                time.sleep(0.1)

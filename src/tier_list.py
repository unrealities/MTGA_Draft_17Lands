"""
src/tier_list.py

This module defines the data models and logic for fetching/saving Tier Lists.
"""

import requests
import os
import json
from datetime import datetime
from pydantic import BaseModel
from typing import Dict, Optional, List, Tuple
from src.logger import create_logger
from src.constants import GRADE_ORDER_DICT, LETTER_GRADE_NA

# Constants for tier list storage and API
TIER_FOLDER = os.path.join(os.getcwd(), "Tier")
TIER_FILE_PREFIX = "Tier"
TIER_URL_17LANDS = "https://www.17lands.com/tier_list/"
TIER_VERSION = 3

logger = create_logger()

# Ensure the tier folder exists
if not os.path.exists(TIER_FOLDER):
    os.makedirs(TIER_FOLDER)

_TIER_CACHE = {"mtime": 0.0, "files": []}


class Meta(BaseModel):
    """Metadata for a tier list."""

    collection_date: str = ""
    label: str = ""
    set: str = ""
    version: int = TIER_VERSION
    url: str = ""


class Rating(BaseModel):
    """Rating for a single card."""

    rating: str = ""
    comment: Optional[str] = None


class TierList(BaseModel):
    """Represents a tier list with metadata and card ratings."""

    meta: Meta = Meta()
    ratings: Dict[str, Rating] = {}

    @classmethod
    def from_api(cls, url: str):
        """Fetch a tier list from the 17Lands API."""
        try:
            if not url.startswith(TIER_URL_17LANDS):
                raise ValueError(f"URL must start with '{TIER_URL_17LANDS}'")
            code = url.split("/")[-1]
            api_url = f"https://www.17lands.com/data/tier_list/{code}"
            response = requests.get(api_url, timeout=10)
            response.raise_for_status()
            data = response.json()
            meta = Meta(
                collection_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                label=data.get("name", ""),
                set=data.get("expansion", ""),
                version=TIER_VERSION,
                url=url,
            )
            ratings = {}
            for card in data.get("ratings", []):
                name = card.get("name", "")
                tier = card.get("tier", "").ljust(2)
                if tier not in GRADE_ORDER_DICT:
                    tier = LETTER_GRADE_NA
                ratings[name] = Rating(rating=tier, comment=card.get("comment", ""))
            return cls(meta=meta, ratings=ratings)
        except (requests.RequestException, ValueError, KeyError, TypeError) as e:
            logger.error(f"Failed to fetch tier list from API: {e}")
            return None

    @classmethod
    def from_file(cls, file_path: str):
        """Load a tier list from a local file."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            meta = Meta(**data.get("meta", {}))
            ratings = {}
            for k, v in data.get("ratings", {}).items():
                rating_value = v.get("rating", "")
                if rating_value not in GRADE_ORDER_DICT:
                    rating_value = LETTER_GRADE_NA
                ratings[k] = Rating(rating=rating_value, comment=v.get("comment"))
            return cls(meta=meta, ratings=ratings)
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as e:
            logger.error(f"Failed to load tier list from {file_path}: {e}")
            return None

    def to_file(self, file_path: str):
        """Save the tier list to a file in JSON format."""
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(self.model_dump(), f, ensure_ascii=False, indent=4)
        except OSError as e:
            logger.error("Failed to save tier list to %s: %s", file_path, e)

    @classmethod
    def _get_all_files(cls):
        try:
            mtime = os.path.getmtime(TIER_FOLDER)
            file_names = sorted(os.listdir(TIER_FOLDER), reverse=True)
        except OSError:
            mtime = 0.0
            file_names = []

        if mtime != 0.0 and mtime == _TIER_CACHE["mtime"] and _TIER_CACHE["files"]:
            return _TIER_CACHE["files"]

        file_list = []
        for file in file_names:
            file_location = os.path.join(TIER_FOLDER, file)
            try:
                name_segments = file.split("_")
                if len(name_segments) != 3 or name_segments[0] != TIER_FILE_PREFIX:
                    continue

                result = TierList.from_file(file_location)
                if not result:
                    continue

                date_str = result.meta.collection_date
                try:
                    dt = datetime.strptime(date_str, "%m/%d/%Y %H:%M:%S")
                    date_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    pass

                file_list.append(
                    (result.meta.set, result.meta.label, date_str, file, result)
                )
            except Exception as error:
                logger.error(f"Failed to process tier list file {file}: {error}")

        _TIER_CACHE["mtime"] = mtime
        _TIER_CACHE["files"] = file_list
        return file_list

    @classmethod
    def retrieve_files(cls, code: str = "") -> List[Tuple[str, str, str, str]]:
        """
        Retrieve local tier list files, optionally filtered by set_code.
        Returns a list of tuples: (Set, Label, Date, Filename)
        """
        all_files = cls._get_all_files()
        filtered = []
        for f_set, f_label, f_date, f_name, _ in all_files:
            if code and code not in f_set:
                continue
            filtered.append((f_set, f_label, f_date, f_name))
        return filtered

    @classmethod
    def delete_file(cls, filename: str):
        """Deletes a tier list file and invalidates the cache."""
        file_path = os.path.join(TIER_FOLDER, filename)
        if os.path.exists(file_path):
            os.remove(file_path)
            _TIER_CACHE["mtime"] = 0.0

    @classmethod
    def retrieve_data(cls, code: str = ""):
        """
        Parse tier list files and return tier data and options dicts.
        Used by the main app to populate column options.
        """
        data = {}
        options = {}
        try:
            all_files = cls._get_all_files()
            for idx, (f_set, _, _, _, f_tier) in enumerate(all_files):
                # Filter by code AFTER getting the global index 'idx'
                # so that the 'TIER{idx}' column label stays consistent everywhere
                if code and code not in f_set:
                    continue

                label = f"TIER{idx}"
                display_name = f"TIER: {f_tier.meta.label} ({f_set})"
                options[display_name] = label
                data[label] = f_tier
        except Exception as error:
            logger.error(f"Error in retrieve_data: {error}")
        return data, options

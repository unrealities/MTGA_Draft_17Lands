import os
import json
import time
import requests
import logging
from server import config
from server.transform import parse_scryfall_types

logger = logging.getLogger(__name__)

# Ensure our persistent Scryfall cache directory exists
SCRYFALL_CACHE_DIR = os.path.join(config.OUTPUT_DIR, "scryfall_cache")
os.makedirs(SCRYFALL_CACHE_DIR, exist_ok=True)


def get_scheduled_events(calendar_path="calendar.json") -> dict:
    """
    Reads the manual calendar JSON and returns a dictionary of active events for TODAY.
    Format: { "TMNT": ["PremierDraft", "TradDraft"], "BLB": ["PremierDraft"] }
    """
    logger.info(f"Loading calendar from {calendar_path}...")

    try:
        with open(calendar_path, "r") as f:
            calendar = json.load(f)
    except FileNotFoundError:
        logger.error("calendar.json not found! Cannot determine active events.")
        return {}

    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    active_sets = {}

    for event in calendar.get("events", []):
        start = event.get("start_date")
        end = event.get("end_date")

        # String comparison works perfectly for YYYY-MM-DD
        if start <= today_str <= end:
            set_code = event["set_code"]
            formats = event["formats"]

            if set_code not in active_sets:
                active_sets[set_code] = set()

            active_sets[set_code].update(formats)

    # Convert sets back to lists for downstream compatibility
    return {k: list(v) for k, v in active_sets.items()}


def extract_scryfall_data(client, set_code: str) -> dict:
    """
    Fetches base card data. Cards don't change, so this is fetched ONCE
    and cached permanently on disk.
    """
    if "CUBE" in set_code.upper():
        return {}

    cache_filepath = os.path.join(SCRYFALL_CACHE_DIR, f"{set_code}_cards.json")

    # 1. Check if we already have this set permanently cached
    if os.path.exists(cache_filepath):
        logger.info(
            f"   [Scryfall] Loading {set_code} base cards from local repository (0 API calls)."
        )
        try:
            with open(cache_filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            logger.warning(
                f"   [Scryfall] Cache corrupted for {set_code}. Re-fetching."
            )

    # 2. If not cached, fetch from Scryfall
    logger.info(f"   [Scryfall] Fetching {set_code} base cards from API...")
    cards = {}
    query = f"set:{set_code} is:booster"
    url = f"https://api.scryfall.com/cards/search?q={requests.utils.quote(query)}"

    while url:
        resp = client.respectful_get(url, allow_404=True)
        if resp.status_code == 404:
            break

        try:
            data = resp.json()
        except json.JSONDecodeError as e:
            logger.warning(f"Non-JSON Scryfall response for {set_code} (page): {e}")
            break

        for c in data.get("data", []):
            arena_id = c.get("arena_id")
            if not arena_id:
                continue

            name = c.get("name", "").replace("///", "//")
            types, subtypes = parse_scryfall_types(c.get("type_line", ""))

            colors = c.get("colors", [])
            if not colors and "card_faces" in c:
                colors = c["card_faces"][0].get("colors", [])

            mana_cost = c.get("mana_cost", "")
            if not mana_cost and "card_faces" in c:
                mana_cost = c["card_faces"][0].get("mana_cost", "")

            images = []
            if "image_uris" in c:
                if img := c["image_uris"].get("large", ""):
                    images.append(img)
            elif "card_faces" in c:
                for face in c["card_faces"]:
                    if img := face.get("image_uris", {}).get("large", ""):
                        images.append(img)

            oracle_text = c.get("oracle_text", "")
            if not oracle_text and "card_faces" in c:
                oracle_text = " // ".join(
                    face.get("oracle_text", "") for face in c["card_faces"]
                )

            cards[name] = {
                "arena_id": arena_id,
                "name": name,
                "cmc": int(c.get("cmc", 0)),
                "mana_cost": mana_cost,
                "types": types,
                "subtypes": subtypes,
                "colors": colors,
                "color_identity": c.get("color_identity", []),
                "rarity": c.get("rarity", "common").capitalize(),
                "image": images,
                "keywords": c.get("keywords", []),
                "oracle_text": oracle_text,
            }

        url = data.get("next_page")

    # 3. Save permanently to disk
    if cards:
        with open(cache_filepath, "w", encoding="utf-8") as f:
            json.dump(cards, f, indent=2)

    return cards


def extract_scryfall_tags(client, set_code: str) -> dict:
    """
    Fetches community tags. Tags change, so we cache this with a 7-day TTL (Time To Live).
    """
    if "CUBE" in set_code.upper():
        return {}

    cache_filepath = os.path.join(SCRYFALL_CACHE_DIR, f"{set_code}_tags.json")

    # 1. Check if we have tags cached AND they are less than 7 days old
    if os.path.exists(cache_filepath):
        file_age_days = (time.time() - os.path.getmtime(cache_filepath)) / 86400
        if file_age_days < 7.0:
            logger.info(
                f"   [Scryfall] Loading {set_code} tags from local repository (Age: {file_age_days:.1f} days)."
            )
            try:
                with open(cache_filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                pass  # Corrupted, fall through to re-fetch
        else:
            logger.info(
                f"   [Scryfall] {set_code} tags are {file_age_days:.1f} days old. Refreshing from API..."
            )

    # 2. If missing or expired, fetch from Scryfall
    logger.info(f"   [Scryfall] Harvesting Scryfall tags for {set_code}...")
    tags_map = {}

    for tag_key, query_str in config.O_TAGS.items():
        query = f"set:{set_code} ({query_str})"
        url = f"https://api.scryfall.com/cards/search?q={requests.utils.quote(query)}"

        try:
            while url:
                resp = client.respectful_get(url, allow_404=True)
                if resp.status_code == 404:
                    break

                try:
                    data = resp.json()
                except json.JSONDecodeError as e:
                    logger.warning(
                        f"Non-JSON Scryfall response for tag '{tag_key}' ({set_code}): {e}"
                    )
                    break

                for c in data.get("data", []):
                    name = c.get("name", "").replace("///", "//")
                    tags_map.setdefault(name, [])
                    if tag_key not in tags_map[name]:
                        tags_map[name].append(tag_key)

                url = data.get("next_page")
        except Exception as e:
            logger.warning(
                f"Failed to fetch tag '{tag_key}' for {set_code}: {e}. Skipping tag."
            )

    # 3. Save to disk with updated modified time
    if tags_map:
        with open(cache_filepath, "w", encoding="utf-8") as f:
            json.dump(tags_map, f, indent=2)

    return tags_map


def extract_17lands_data(client, set_code: str, draft_format: str) -> dict:
    archetype_data = {}
    for i, color in enumerate(config.ARCHETYPES):
        logger.info(f"   [{i+1}/{len(config.ARCHETYPES)}] Fetching {color} stats...")
        url = f"https://www.17lands.com/card_ratings/data?expansion={set_code}&format={draft_format}"
        if color != "All Decks":
            url += f"&colors={color}"

        try:
            data = client.respectful_get(url).json()

            if color == "All Decks" and not data:
                logger.warning(
                    f"No baseline data for {set_code} {draft_format}. Aborting archetype fetch."
                )
                break

            archetype_data[color] = {}
            for card in data:
                name = card.get("name", "").replace("///", "//")
                archetype_data[color][name] = {
                    "gihwr": round(
                        float(card.get("ever_drawn_win_rate") or 0) * 100, 2
                    ),
                    "ohwr": round(
                        float(card.get("opening_hand_win_rate") or 0) * 100, 2
                    ),
                    "gpwr": round(float(card.get("win_rate") or 0) * 100, 2),
                    "gnswr": round(
                        float(card.get("never_drawn_win_rate") or 0) * 100, 2
                    ),
                    "gdwr": round(float(card.get("drawn_win_rate") or 0) * 100, 2),
                    "alsa": round(float(card.get("avg_seen") or 0), 2),
                    "ata": round(float(card.get("avg_pick") or 0), 2),
                    "iwd": round(
                        float(card.get("drawn_improvement_win_rate") or 0) * 100, 2
                    ),
                    "samples": int(card.get("ever_drawn_game_count") or 0),
                    "seen_count": card.get("seen_count", 0),
                    "pick_count": card.get("pick_count", 0),
                    "game_count": card.get("game_count", 0),
                    "pool_count": card.get("pool_count", 0),
                    "play_rate": round(float(card.get("play_rate") or 0) * 100, 2),
                    "opening_hand_game_count": card.get("opening_hand_game_count", 0),
                    "drawn_game_count": card.get("drawn_game_count", 0),
                    "never_drawn_game_count": card.get("never_drawn_game_count", 0),
                }

                if color == "All Decks":
                    imgs = []
                    for img_key in ("url", "url_back"):
                        if img := card.get(img_key, ""):
                            imgs.append(
                                f"https://www.17lands.com{img}"
                                if img.startswith("/static")
                                else img
                            )
                    archetype_data[color][name]["17lands_images"] = imgs

        except Exception as e:
            logger.warning(f"Failed to fetch {color} for {set_code}: {e}")

    return archetype_data


def extract_color_ratings(client, set_code: str, draft_format: str) -> dict:
    logger.info(f"Fetching color ratings for {set_code} {draft_format}...")
    url = f"https://www.17lands.com/color_ratings/data?expansion={set_code}&event_type={draft_format}&combine_splash=true"
    ratings = {}
    try:
        data = client.respectful_get(url).json()
        for entry in data:
            color_key = entry.get("short_name") or (
                "All Decks" if "All" in entry.get("color_name", "") else None
            )
            if color_key and (games := entry.get("games", 0)) > 0:
                ratings[color_key] = round((entry.get("wins", 0) / games) * 100, 1)
    except Exception as e:
        logger.warning(
            f"Failed to fetch color ratings for {set_code} {draft_format}: {e}"
        )

    return ratings

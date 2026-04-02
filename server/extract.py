import os
import json
import logging
import re
from datetime import datetime, timezone, timedelta
from server import config
from server.transform import parse_scryfall_types
from src.utils import normalize_color_string

logger = logging.getLogger(__name__)

SCRYFALL_CACHE_DIR = os.path.join(os.path.dirname(config.OUTPUT_DIR), ".scryfall_cache")
os.makedirs(SCRYFALL_CACHE_DIR, exist_ok=True)


def extract_scryfall_data(client, set_code: str) -> dict:
    if "CUBE" in set_code.upper() or "REMIX" in set_code.upper():
        return {}

    cache_filepath = os.path.join(SCRYFALL_CACHE_DIR, f"{set_code}_cards.json")

    if os.path.exists(cache_filepath):
        file_mod_time = datetime.fromtimestamp(
            os.path.getmtime(cache_filepath), tz=timezone.utc
        )
        age = datetime.now(timezone.utc) - file_mod_time

        if age < timedelta(days=7):
            logger.info(
                f"   [Scryfall] Loading {set_code} base cards from local repository."
            )
            try:
                with open(cache_filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                pass
        else:
            logger.info(
                f"   [Scryfall] {set_code} base cards expired. Refreshing from API..."
            )

    logger.info(f"   [Scryfall] Fetching {set_code} base cards from API...")
    cards = {}
    url = "https://api.scryfall.com/cards/search"
    params = {"q": f"set:{set_code}", "unique": "prints"}

    while url:
        resp = client.respectful_get(url, params=params, allow_404=True)
        if resp.status_code == 404:
            break

        try:
            data = resp.json()
        except json.JSONDecodeError as e:
            logger.warning(f"Non-JSON Scryfall response for {set_code}: {e}")
            break

        for c in data.get("data", []):
            name = c.get("name", "").replace("///", "//")
            if not name:
                continue

            arena_id = c.get("arena_id")

            types, subtypes = parse_scryfall_types(c.get("type_line", ""))

            colors = c.get("colors", [])
            mana_cost = c.get("mana_cost", "")
            oracle_text = c.get("oracle_text", "")
            images = []

            if "card_faces" in c:
                if not colors:
                    colors = c["card_faces"][0].get("colors", [])
                if not mana_cost:
                    mana_cost = c["card_faces"][0].get("mana_cost", "")
                if not oracle_text:
                    oracle_text = " // ".join(
                        face.get("oracle_text", "") for face in c["card_faces"]
                    )
                for face in c["card_faces"]:
                    if img := face.get("image_uris", {}).get("large", ""):
                        images.append(img)
            elif "image_uris" in c:
                if img := c["image_uris"].get("large", ""):
                    images.append(img)

            if name not in cards:
                cards[name] = {
                    "arena_ids": [arena_id] if arena_id else [],
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
            else:
                if arena_id and arena_id not in cards[name]["arena_ids"]:
                    cards[name]["arena_ids"].append(arena_id)

        url = data.get("next_page")
        params = None

    if cards:
        with open(cache_filepath, "w", encoding="utf-8") as f:
            json.dump(cards, f, indent=2)

    return cards


def extract_scryfall_tags(client, set_code: str) -> dict:
    if "CUBE" in set_code.upper() or "REMIX" in set_code.upper():
        return {}

    cache_filepath = os.path.join(SCRYFALL_CACHE_DIR, f"{set_code}_tags.json")

    if os.path.exists(cache_filepath):
        file_mod_time = datetime.fromtimestamp(
            os.path.getmtime(cache_filepath), tz=timezone.utc
        )
        age = datetime.now(timezone.utc) - file_mod_time

        if age < timedelta(days=7):
            try:
                with open(cache_filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                pass

    logger.info(f"   [Scryfall] Harvesting tags for {set_code}...")
    tags_map = {}

    for tag_key, query_str in config.O_TAGS.items():
        url = "https://api.scryfall.com/cards/search"
        params = {"q": f"set:{set_code} ({query_str})"}

        try:
            while url:
                resp = client.respectful_get(url, params=params, allow_404=True)
                if resp.status_code == 404:
                    break

                data = resp.json()
                for c in data.get("data", []):
                    name = c.get("name", "").replace("///", "//")
                    tags_map.setdefault(name, [])
                    if tag_key not in tags_map[name]:
                        tags_map[name].append(tag_key)

                url = data.get("next_page")
                params = None
        except Exception as e:
            logger.warning(f"Failed to fetch tag '{tag_key}' for {set_code}: {e}")

    if tags_map:
        with open(cache_filepath, "w", encoding="utf-8") as f:
            json.dump(tags_map, f, indent=2)

    return tags_map


def extract_17lands_data(
    client,
    set_code: str,
    draft_format: str,
    valid_archetypes: list,
    user_group: str,
    start_date: str,
    end_date: str,
) -> dict:
    archetype_data = {}
    base_url = "https://api.17lands.com/card_ratings/data"

    for i, color in enumerate(valid_archetypes):
        logger.info(
            f"   [{i+1}/{len(valid_archetypes)}] Fetching {color} stats ({user_group})..."
        )

        params = {
            "expansion": set_code,
            "format": draft_format,
            "start_date": start_date,
            "end_date": end_date,
        }
        if color != "All Decks":
            params["colors"] = color
        if user_group != "All":
            params["user_group"] = user_group.lower()

        try:
            data = client.respectful_get(base_url, params=params).json()
            if color == "All Decks" and not data:
                break

            archetype_data[color] = {}
            for card in data:
                name = card.get("name", "").replace("///", "//")
                mtga_id = card.get("mtga_id") or card.get("arena_id")
                if not mtga_id and "url" in card:
                    match = re.search(r"card_id=(\d+)", card.get("url", ""))
                    if match:
                        mtga_id = int(match.group(1))

                archetype_data[color][name] = {
                    "arena_id": mtga_id,
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
                    "play_rate": round(float(card.get("play_rate") or 0) * 100, 2),
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


def extract_color_ratings(
    client,
    set_code: str,
    draft_format: str,
    user_group: str,
    start_date: str,
    end_date: str,
) -> tuple[dict, dict, int]:
    logger.info(
        f"Fetching color ratings for {set_code} {draft_format} ({user_group})..."
    )

    params = {
        "expansion": set_code,
        "event_type": draft_format,
        "start_date": start_date,
        "end_date": end_date,
        "combine_splash": "true",
    }
    if user_group != "All":
        params["user_group"] = user_group.lower()

    url = "https://www.17lands.com/color_ratings/data"
    ratings, games_played = {}, {}
    total_games = 0

    try:
        data = client.respectful_get(url, params=params).json()
        for entry in data:
            if entry.get("is_summary"):
                if "All Decks" in entry.get("color_name", ""):
                    total_games = entry.get("games", 0)
                # Don't use 'continue' here, otherwise we skip saving the 'All Decks' win rate entirely!

            color_key = entry.get("short_name")
            if not color_key:
                color_name = entry.get("color_name", "")
                if "All" in color_name:
                    color_key = ""
                else:
                    match = re.search(r"\((.*?)\)", color_name)
                    if match:
                        color_key = match.group(1)

            if color_key in ["1", "2", "3", "4", "5"]:
                continue

            if color_key is not None:
                color_key = normalize_color_string(color_key)

            if color_key is not None and (games := entry.get("games", 0)) > 0:
                if games >= config.MIN_GAMES_THRESHOLD:
                    ratings[color_key] = round((entry.get("wins", 0) / games) * 100, 1)
                    games_played[color_key] = games

    except Exception as e:
        logger.warning(f"Failed to fetch color ratings: {e}")

    return ratings, games_played, total_games


def extract_scryfall_by_names(client, names: list) -> dict:
    cards = {}
    chunk_size = 20

    for i in range(0, len(names), chunk_size):
        chunk = names[i : i + chunk_size]
        query = " OR ".join([f'!"{n}"' for n in chunk])
        url = "https://api.scryfall.com/cards/search"
        params = {"q": query, "unique": "prints"}

        while url:
            resp = client.respectful_get(url, params=params, allow_404=True)
            if resp.status_code == 404:
                break

            try:
                data = resp.json()
            except Exception:
                break

            for c in data.get("data", []):
                name = c.get("name", "").replace("///", "//")
                if not name:
                    continue

                arena_id = c.get("arena_id")

                types, subtypes = parse_scryfall_types(c.get("type_line", ""))
                colors = c.get("colors", [])
                mana_cost = c.get("mana_cost", "")
                oracle_text = c.get("oracle_text", "")
                images = []

                if "card_faces" in c:
                    if not colors:
                        colors = c["card_faces"][0].get("colors", [])
                    if not mana_cost:
                        mana_cost = c["card_faces"][0].get("mana_cost", "")
                    if not oracle_text:
                        oracle_text = " // ".join(
                            face.get("oracle_text", "") for face in c["card_faces"]
                        )
                    for face in c["card_faces"]:
                        if img := face.get("image_uris", {}).get("large", ""):
                            images.append(img)
                elif "image_uris" in c:
                    if img := c["image_uris"].get("large", ""):
                        images.append(img)

                if name not in cards:
                    cards[name] = {
                        "arena_ids": [arena_id] if arena_id else [],
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
                else:
                    if arena_id and arena_id not in cards[name]["arena_ids"]:
                        cards[name]["arena_ids"].append(arena_id)

            url = data.get("next_page")
            params = None

    return cards


def get_historical_start_dates(client) -> dict:
    try:
        resp = client.respectful_get("https://api.17lands.com/data/filters")
        return resp.json().get("start_dates", {})
    except Exception as e:
        logger.warning(f"Could not fetch historical start dates: {e}")
        return {}

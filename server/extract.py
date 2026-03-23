import json
import time
import requests
import logging
from datetime import datetime, timezone, timedelta
from server import config
from server.transform import parse_scryfall_types

logger = logging.getLogger(__name__)


def extract_active_events(client) -> dict:
    logger.info("Detecting active formats and Flashback drafts...")
    url = "https://www.17lands.com/data/filters"
    data = client.respectful_get(url).json()

    active_events = {}
    formats_map = data.get("formats_by_expansion", {})
    sorted_dates = sorted(
        data.get("start_dates", {}).items(), key=lambda x: x[1], reverse=True
    )

    always_fetch = [s[0] for s in sorted_dates[:3]]
    for s in formats_map.keys():
        if "Cube" in s and s not in always_fetch:
            always_fetch.append(s)

    for s in always_fetch:
        active_events[s] = [f for f in formats_map.get(s, [])]

    seven_days_ago = (datetime.now(timezone.utc) - timedelta(days=7)).strftime(
        "%Y-%m-%d"
    )
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    older_sets = [s[0] for s in sorted_dates[3:] if "Cube" not in s[0]]

    no_activity_streak = 0
    for s in older_sets:
        if no_activity_streak >= 5:
            break

        formats_to_check = [
            f for f in formats_map.get(s, []) if "Draft" in f or "Sealed" in f
        ]
        active_formats_for_old_set = []

        for fmt in formats_to_check:
            check_url = (
                f"https://www.17lands.com/color_ratings/data?"
                f"expansion={s}&event_type={fmt}&start_date={seven_days_ago}"
                f"&end_date={today}&combine_splash=true"
            )
            try:
                rating_data = client.respectful_get(check_url).json()
                for entry in rating_data:
                    if entry.get("is_summary") and entry.get("games", 0) > 500:
                        active_formats_for_old_set.append(fmt)
                        break
            except Exception as e:
                logger.warning(f"Failed to check activity for {s} {fmt}: {e}")

        if active_formats_for_old_set:
            logger.info(
                f"Detected Active Flashback Event: {s} - {active_formats_for_old_set}"
            )
            active_events[s] = active_formats_for_old_set
            no_activity_streak = 0
        else:
            no_activity_streak += 1

    return active_events


def extract_scryfall_data(client, set_code: str) -> dict:
    logger.info(f"Fetching Scryfall base data for {set_code}...")
    cards = {}
    query = f"set:{set_code} is:booster"
    if "CUBE" in set_code.upper():
        return cards

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

    return cards


def extract_scryfall_tags(client, set_code: str) -> dict:
    logger.info(f"Harvesting Scryfall tags for {set_code}...")
    tags_map = {}
    if "CUBE" in set_code.upper():
        return tags_map

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
                    logger.warning(f"Non-JSON Scryfall response for tag '{tag_key}' ({set_code}): {e}")
                    break

                for c in data.get("data", []):
                    name = c.get("name", "").replace("///", "//")
                    tags_map.setdefault(name, [])
                    if tag_key not in tags_map[name]:
                        tags_map[name].append(tag_key)

                url = data.get("next_page")
        except Exception as e:
            logger.warning(f"Failed to fetch tag '{tag_key}' for {set_code}: {e}. Skipping tag.")

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
                logger.warning(f"No baseline data for {set_code} {draft_format}. Aborting archetype fetch.")
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

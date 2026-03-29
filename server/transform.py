import logging
from datetime import datetime, timezone
from server import config

logger = logging.getLogger(__name__)


def parse_scryfall_types(type_line: str):
    if not type_line:
        return [], []

    parts = type_line.split("—")
    base_str = parts[0].strip()
    sub_str = parts[1].strip() if len(parts) > 1 else ""

    allowed_types = {
        "Creature",
        "Enchantment",
        "Artifact",
        "Instant",
        "Sorcery",
        "Land",
        "Planeswalker",
        "Battle",
    }
    types = [t for t in base_str.split() if t in allowed_types]

    if "Creature" in types:
        types.remove("Creature")
        types.insert(0, "Creature")

    subtypes = sub_str.split() if sub_str else []
    return types, subtypes


def transform_payload(
    set_code,
    draft_format,
    scryfall_cards,
    seventeenlands_data,
    card_tags,
    color_ratings,
    start_date,
    end_date,
    total_games,
) -> dict:
    logger.info(f"Transforming payload for {set_code} {draft_format}...")

    if total_games == 0:
        total_games = max(
            (
                stats.get("samples", 0)
                for stats in seventeenlands_data.get("All Decks", {}).values()
            ),
            default=0,
        )

    payload = {
        "meta": {
            "collection_date": datetime.now(timezone.utc).strftime(
                "%Y-%m-%d %H:%M:%S.%f"
            ),
            "start_date": start_date,
            "end_date": end_date,
            "version": 3.0,
            "game_count": total_games,
        },
        "color_ratings": color_ratings or {},
        "card_ratings": {},
    }

    for name, sf_card in scryfall_cards.items():
        arena_ids = sf_card.get("arena_ids", [])
        if not arena_ids:
            arena_ids = [f"UNKNOWN_{name.replace(' ', '')}"]

        all_decks_stats = seventeenlands_data.get("All Decks", {}).get(name, {})

        card_obj = {
            "name": name,
            "cmc": sf_card.get("cmc", 0),
            "mana_cost": sf_card.get("mana_cost", ""),
            "isprimarycard": 1,
            "linkedfacetype": 0,
            "types": sf_card.get("types", ["Creature"]),
            "rarity": sf_card.get("rarity", "Common").lower(),
            "image": sf_card.get("image", [])
            or all_decks_stats.get("17lands_images", []),
            "subtypes": sf_card.get("subtypes", []),
            "colors": sf_card.get("colors", []),
            "set": set_code,
            "deck_colors": {},
            "tags": card_tags.get(name, []),
        }

        for extra_key in ["color_identity", "keywords", "oracle_text"]:
            if val := sf_card.get(extra_key):
                card_obj[extra_key] = val

        alsa = all_decks_stats.get("alsa", 0.0)
        ata = all_decks_stats.get("ata", 0.0)
        card_obj["deck_colors"][""] = {
            "gihwr": 0.0,
            "ohwr": 0.0,
            "gpwr": 0.0,
            "gnswr": 0.0,
            "gdwr": 0.0,
            "alsa": alsa,
            "ata": ata,
            "iwd": 0.0,
            "samples": 0,
        }

        for arch in config.ARCHETYPES:
            if arch_stats := seventeenlands_data.get(arch, {}).get(name):
                card_obj["deck_colors"][arch] = {
                    k: v
                    for k, v in arch_stats.items()
                    if k not in ("17lands_images", "arena_id")
                }

        for a_id in arena_ids:
            payload["card_ratings"][str(a_id)] = card_obj

    return payload

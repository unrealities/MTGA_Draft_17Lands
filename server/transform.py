import logging
from datetime import datetime, timezone
from server import config

logger = logging.getLogger(__name__)


def parse_scryfall_types(type_line: str):
    """Utility to clean up Scryfall type lines."""
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
) -> dict:
    """Merges all sources into a highly optimized JSON payload for the client."""
    logger.info(f"Transforming payload for {set_code} {draft_format}...")

    max_games = max(
        (
            stats.get("samples", 0)
            for stats in seventeenlands_data.get("All Decks", {}).values()
        ),
        default=0,
    )

    payload = {
        "meta": {
            "set": set_code,
            "format": draft_format,
            "game_count": max_games,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "version": 3.0,
        },
        "card_ratings": {},
    }

    for name, base_stats in seventeenlands_data.get("All Decks", {}).items():
        sf_card = scryfall_cards.get(name, {})
        arena_id = (
            str(sf_card.get("arena_id", "")) or f"UNKNOWN_{name.replace(' ', '')}"
        )

        card_obj = {
            "name": name,
            "arena_id": arena_id,
            "cmc": sf_card.get("cmc", 0),
            "mana_cost": sf_card.get("mana_cost", ""),
            "types": sf_card.get("types", ["Creature"]),
            "subtypes": sf_card.get("subtypes", []),
            "colors": sf_card.get("colors", []),
            "color_identity": sf_card.get("color_identity", []),
            "rarity": sf_card.get("rarity", "Common"),
            "tags": card_tags.get(name, []),
            "keywords": sf_card.get("keywords", []),
            "oracle_text": sf_card.get("oracle_text", ""),
            "image": sf_card.get("image", []) or base_stats.get("17lands_images", []),
            "deck_colors": {},
        }

        for arch in config.ARCHETYPES:
            if arch_stats := seventeenlands_data.get(arch, {}).get(name):
                card_obj["deck_colors"][arch] = {
                    k: v for k, v in arch_stats.items() if k != "17lands_images"
                }

        payload["card_ratings"][arena_id] = card_obj

    payload["color_ratings"] = color_ratings or {}
    return payload

import logging
from datetime import datetime, timezone
from server import config

logger = logging.getLogger(__name__)


def parse_scryfall_types(type_line: str):
    if not type_line:
        return [], []

    faces = type_line.split("//")

    types_list = []
    subtypes_list = []

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

    for face in faces:
        parts = face.split("—")
        base_str = parts[0].strip()
        sub_str = parts[1].strip() if len(parts) > 1 else ""

        for t in base_str.split():
            if t in allowed_types and t not in types_list:
                types_list.append(t)

        if sub_str:
            for st in sub_str.split():
                if st not in subtypes_list:
                    subtypes_list.append(st)

    if "Creature" in types_list:
        types_list.remove("Creature")
        types_list.insert(0, "Creature")

    return types_list, subtypes_list


BASIC_LANDS = {
    "Plains",
    "Island",
    "Swamp",
    "Mountain",
    "Forest",
    "Wastes",
    "Snow-Covered Plains",
    "Snow-Covered Island",
    "Snow-Covered Swamp",
    "Snow-Covered Mountain",
    "Snow-Covered Forest",
}


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

    safe_color_ratings = {
        arch: 0.0 for arch in config.ARCHETYPES if arch != "All Decks"
    }
    safe_color_ratings[""] = 0.0

    if color_ratings:
        for k, v in color_ratings.items():
            safe_color_ratings[k] = v

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
        "color_ratings": safe_color_ratings,
        "card_ratings": {},
    }

    all_decks_stats_map = seventeenlands_data.get("All Decks", {})

    for name, all_decks_stats in all_decks_stats_map.items():
        sf_card = scryfall_cards.get(name, {})

        l17_id = all_decks_stats.get("arena_id")
        sf_ids = sf_card.get("arena_ids", [])

        arena_ids_set = set()
        if l17_id:
            arena_ids_set.add(l17_id)
        if sf_ids:
            arena_ids_set.update(sf_ids)

        if not arena_ids_set:
            arena_ids_set.add(f"UNKNOWN_{name.replace(' ', '')}")

        arena_ids = list(arena_ids_set)

        card_obj = {
            "name": name,
            "cmc": sf_card.get("cmc", 0),
            "mana_cost": sf_card.get("mana_cost", ""),
            "isprimarycard": 1,
            "linkedfacetype": 0,
            "types": sf_card.get("types", ["Creature"]),
            "rarity": sf_card.get(
                "rarity", all_decks_stats.get("rarity", "common")
            ).lower(),
            "image": sf_card.get("image", [])
            or all_decks_stats.get("17lands_images", []),
            "subtypes": sf_card.get("subtypes", []),
            "colors": sf_card.get("color_identity", []),
            "set": set_code,
            "deck_colors": {},
            "tags": card_tags.get(name, []),
        }

        for extra_key in ["color_identity", "keywords", "oracle_text"]:
            if val := sf_card.get(extra_key):
                card_obj[extra_key] = val

        alsa = all_decks_stats.get("alsa", 0.0)
        ata = all_decks_stats.get("ata", 0.0)

        for arch in config.ARCHETYPES:
            card_obj["deck_colors"][arch] = {
                "gihwr": 0.0,
                "ohwr": 0.0,
                "gpwr": 0.0,
                "gnswr": 0.0,
                "gdwr": 0.0,
                "alsa": alsa if arch == "All Decks" else 0.0,
                "ata": ata if arch == "All Decks" else 0.0,
                "iwd": 0.0,
                "samples": 0,
                "seen_count": 0,
                "pick_count": 0,
                "game_count": 0,
                "play_rate": 0.0,
            }
            if arch_stats := seventeenlands_data.get(arch, {}).get(name):
                for k, v in arch_stats.items():
                    if k not in ("17lands_images", "arena_id", "rarity"):
                        card_obj["deck_colors"][arch][k] = v

        for a_id in arena_ids:
            payload["card_ratings"][str(a_id)] = card_obj

    for name in BASIC_LANDS:
        if name in scryfall_cards and name not in all_decks_stats_map:
            sf_card = scryfall_cards[name]
            sf_ids = sf_card.get("arena_ids", [])
            if not sf_ids:
                continue

            card_obj = {
                "name": name,
                "cmc": sf_card.get("cmc", 0),
                "mana_cost": sf_card.get("mana_cost", ""),
                "isprimarycard": 1,
                "linkedfacetype": 0,
                "types": sf_card.get("types", ["Land", "Basic"]),
                "rarity": "common",
                "image": sf_card.get("image", []),
                "subtypes": sf_card.get("subtypes", []),
                "colors": sf_card.get("color_identity", []),
                "set": set_code,
                "deck_colors": {},
                "tags": card_tags.get(name, []),
            }

            for arch in config.ARCHETYPES:
                card_obj["deck_colors"][arch] = {
                    "gihwr": 0.0,
                    "ohwr": 0.0,
                    "gpwr": 0.0,
                    "gnswr": 0.0,
                    "gdwr": 0.0,
                    "alsa": 0.0,
                    "ata": 0.0,
                    "iwd": 0.0,
                    "samples": 0,
                    "seen_count": 0,
                    "pick_count": 0,
                    "game_count": 0,
                    "play_rate": 0.0,
                }

            for a_id in sf_ids:
                payload["card_ratings"][str(a_id)] = card_obj

    return payload

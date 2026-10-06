"""
src/card_logic.py
The Pro Deck Construction Engine & UI Utilities.
Generates dynamic deck variants and handles data formatting for the UI.
"""

from itertools import combinations
from dataclasses import dataclass, field
import logging
import math
import copy
import io
import csv
import json
from src import constants
from src.logger import create_logger
from src.card_utils import get_functional_cmc, stack_cards  # noqa: F401 (re-exported)

logger = create_logger()

# --- HELPER CLASSES ---


def format_types_for_ui(types_array):
    """Extracts supertypes from a raw types array, guaranteeing 'Creature' is always first."""
    if not types_array:
        return ""

    allowed = {
        "Creature",
        "Enchantment",
        "Land",
        "Artifact",
        "Planeswalker",
        "Instant",
        "Sorcery",
        "Battle",
    }
    filtered = [t for t in types_array if t in allowed]

    if "Creature" in filtered:
        filtered.remove("Creature")
        filtered.insert(0, "Creature")

    return " ".join(filtered)


@dataclass
class DeckMetrics:
    cmc_average: float = 0.0
    creature_count: int = 0
    noncreature_count: int = 0
    total_cards: int = 0
    total_non_land_cards: int = 0
    distribution_all: list = field(default_factory=lambda: [0] * 8)
    distribution_creatures: list = field(default_factory=lambda: [0] * 8)
    distribution_noncreatures: list = field(default_factory=lambda: [0] * 8)
    pip_counts: dict = field(default_factory=dict)
    fixing_sources: dict = field(default_factory=dict)


# --- UI UTILITIES ---


def filter_options(deck, option_selection, metrics, configuration):
    """
    Returns the active color filter for the dashboard.
    Handles 'Auto' by detecting the top color pair in the pool.
    """
    if constants.FILTER_OPTION_AUTO not in option_selection:
        return [option_selection]

    # Auto Logic: Identify top 2 colors
    try:
        # Don't auto-switch until we have enough data (e.g. pick 5)
        if len(deck) < 5:
            return [constants.FILTER_OPTION_ALL_DECKS]

        top_pair = identify_top_pairs(deck, metrics)
        if top_pair and top_pair[0]:
            from src.utils import normalize_color_string

            # Convert ["U", "B"] -> "UB" in strict WUBRG order
            pair_str = normalize_color_string("".join(top_pair[0]))

            # Check if we actually have data for this archetype
            if pair_str:
                mean, std = metrics.get_metrics(pair_str, constants.DATA_FIELD_GIHWR)
                if mean > 0.0:
                    return [pair_str]

    except Exception as e:
        logger.error(f"Auto filter error: {e}")

    return [constants.FILTER_OPTION_ALL_DECKS]


def get_deck_metrics(deck):
    """Calculates distribution and average CMC."""
    metrics = DeckMetrics()
    cmc_total = 0
    try:
        metrics.total_cards = len(deck)
        for card in deck:
            c_types = card.get(constants.DATA_FIELD_TYPES, [])
            c_cmc = get_functional_cmc(card)

            if constants.CARD_TYPE_LAND not in c_types:
                cmc_total += c_cmc
                metrics.total_non_land_cards += 1

                idx = min(c_cmc, 7)
                metrics.distribution_all[idx] += 1

                if constants.CARD_TYPE_CREATURE in c_types:
                    metrics.creature_count += 1
                    metrics.distribution_creatures[idx] += 1
                else:
                    metrics.noncreature_count += 1
                    metrics.distribution_noncreatures[idx] += 1

        metrics.cmc_average = (
            cmc_total / metrics.total_non_land_cards
            if metrics.total_non_land_cards
            else 0.0
        )
    except Exception as error:
        logger.error(f"get_deck_metrics error: {error}")
    return metrics


def get_card_colors(mana_cost):
    """
    Parses a mana cost string (e.g., "{1}{W}{U}") and returns a dictionary
    of color counts (e.g., {'W': 1, 'U': 1}).
    """
    colors = {}
    try:
        if not mana_cost:
            return colors
        for color in constants.CARD_COLORS:
            count = mana_cost.count(color)
            if count > 0:
                colors[color] = count
    except Exception as error:
        logger.error(f"get_card_colors error: {error}")
    return colors


def row_color_tag(mana_cost):
    """Selects the color tag for a table row based on mana cost."""
    if not mana_cost:
        return constants.CARD_ROW_COLOR_COLORLESS_TAG

    colors = set()
    for c in constants.CARD_COLORS:
        if c in mana_cost:
            colors.add(c)

    if len(colors) > 1:
        return constants.CARD_ROW_COLOR_GOLD_TAG
    elif constants.CARD_COLOR_SYMBOL_RED in colors:
        return constants.CARD_ROW_COLOR_RED_TAG
    elif constants.CARD_COLOR_SYMBOL_BLUE in colors:
        return constants.CARD_ROW_COLOR_BLUE_TAG
    elif constants.CARD_COLOR_SYMBOL_BLACK in colors:
        return constants.CARD_ROW_COLOR_BLACK_TAG
    elif constants.CARD_COLOR_SYMBOL_WHITE in colors:
        return constants.CARD_ROW_COLOR_WHITE_TAG
    elif constants.CARD_COLOR_SYMBOL_GREEN in colors:
        return constants.CARD_ROW_COLOR_GREEN_TAG

    return constants.CARD_ROW_COLOR_COLORLESS_TAG


def field_process_sort(field_value):
    """Helper for treeview sorting."""
    try:
        if isinstance(field_value, str):
            val = field_value.replace("*", "").replace("%", "").strip()
            if val in ["NA", "-", ""]:
                return (0, 0.0)

            for k, v in constants.GRADE_ORDER_DICT.items():
                if k.strip() == val:
                    return (1, float(v))

            return (1, float(val))

        elif field_value is None:
            return (0, 0.0)

        return (1, float(field_value))
    except (ValueError, TypeError):
        return (2, str(field_value).lower())


def copy_deck(deck, sideboard):
    """Formats deck for Clipboard."""
    output = "Deck\n"
    for c in deck:
        count = c.get("count", 1)
        name = c.get("name", "Unknown")
        output += f"{count} {name}\n"

    if sideboard:
        output += "\nSideboard\n"
        for c in sideboard:
            count = c.get("count", 1)
            name = c.get("name", "Unknown")
            output += f"{count} {name}\n"
    return output


def export_draft_to_csv(history, dataset, picked_cards_map):
    import io, csv

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "Pack",
            "Pick",
            "Picked",
            "Name",
            "Colors",
            "CMC",
            "Type",
            "GIHWR",
            "ALSA",
            "ATA",
            "IWD",
        ]
    )
    if not history:
        return output.getvalue()
    user_picks = picked_cards_map[0] if picked_cards_map else []

    for entry in history:
        for cid in entry["Cards"]:
            c_list = dataset.get_data_by_id([cid])
            if not c_list:
                continue
            c = c_list[0]
            stats = c.get("deck_colors", {}).get("All Decks", {})
            writer.writerow(
                [
                    entry["Pack"],
                    entry["Pick"],
                    "1" if str(cid) in user_picks else "0",
                    c.get("name", ""),
                    "".join(c.get("colors", [])),
                    str(c.get("cmc", "")),
                    " ".join(c.get("types", [])),
                    stats.get("gihwr", ""),
                    stats.get("alsa", ""),
                    stats.get("ata", ""),
                    stats.get("iwd", ""),
                ]
            )
    return output.getvalue()


def export_draft_to_json(history, dataset, picked_cards_map):
    import json

    output = []
    user_picks = picked_cards_map[0] if picked_cards_map else []
    for entry in history:
        pack_data = {"Pack": entry["Pack"], "Pick": entry["Pick"], "Cards": []}
        for cid in entry["Cards"]:
            c_list = dataset.get_data_by_id([cid])
            if not c_list:
                continue
            c = c_list[0]
            pack_data["Cards"].append(
                {
                    "Name": c.get("name", ""),
                    "Picked": (str(cid) in user_picks),
                    "Colors": c.get("colors", []),
                    "CMC": c.get("cmc", 0),
                    "Type": c.get("types", []),
                }
            )
        output.append(pack_data)
    return json.dumps(output, indent=4)


def format_win_rate(val, color, field, metrics, result_format):
    from src import constants

    if val == 0.0 or val == "-":
        return "-"

    if (
        not metrics
        or result_format == constants.RESULT_FORMAT_WIN_RATE
        or field not in constants.WIN_RATE_OPTIONS
    ):
        return f"{val:.1f}" if isinstance(val, float) else str(val)

    mean, std = metrics.get_metrics(color, field)
    if std == 0:
        return f"{val:.1f}" if isinstance(val, float) else str(val)

    z_score = (val - mean) / std

    if result_format == constants.RESULT_FORMAT_GRADE:
        for grade, limit in constants.GRADE_DEVIATION_DICT.items():
            if z_score >= limit:
                return grade.strip()
        return "F"
    elif result_format == constants.RESULT_FORMAT_RATING:
        upper, lower = mean + (2.0 * std), mean - (1.67 * std)
        if upper == lower:
            return "2.5"
        rating = ((val - lower) / (upper - lower)) * 5.0
        return f"{max(0.0, min(5.0, rating)):.1f}"

    return f"{val:.1f}" if isinstance(val, float) else str(val)


class CardResult:
    """Processes lists for UI Tables (Dashboard/Overlay)."""

    def __init__(self, set_metrics, tier_data, configuration, pick_number):
        self.metrics = set_metrics
        self.tier_data = tier_data
        self.configuration = configuration
        self.pick_number = pick_number

    def return_results(self, card_list, colors, fields):
        return_list = []
        for card in card_list:
            try:
                selected_card = copy.deepcopy(card)
                selected_card["results"] = ["NA"] * len(fields)
                primary_color = (
                    colors[0] if colors else constants.FILTER_OPTION_ALL_DECKS
                )

                for count, option in enumerate(fields):
                    if option in constants.WIN_RATE_OPTIONS or option in [
                        "alsa",
                        "iwd",
                        "ata",
                        "ohwr",
                        "gpwr",
                        "gdwr",
                        "gnswr",
                    ]:
                        stats = card.get("deck_colors", {}).get(primary_color, {})
                        val = stats.get(option, 0.0)

                        if (
                            option in constants.WIN_RATE_OPTIONS
                            and self.configuration.settings.result_format
                            != constants.RESULT_FORMAT_WIN_RATE
                        ):
                            val = self._format_win_rate(val, primary_color, option)

                        selected_card["results"][count] = val if val != 0.0 else "-"
                    elif option == "name":
                        selected_card["results"][count] = card.get("name", "Unknown")
                    elif option == "colors":
                        selected_card["results"][count] = "".join(
                            card.get("colors", [])
                        )
                    elif "TIER" in option:
                        if self.tier_data and option in self.tier_data:
                            tier_list = self.tier_data[option]
                            card_name = card.get(constants.DATA_FIELD_NAME, "")
                            if card_name in tier_list.ratings:
                                selected_card["results"][count] = tier_list.ratings[
                                    card_name
                                ].rating
                            else:
                                selected_card["results"][count] = "NA"
                        else:
                            selected_card["results"][count] = "NA"
                    elif option == "value":
                        selected_card["results"][count] = 0

                return_list.append(selected_card)
            except Exception as e:
                logger.error(f"CardResult error: {e}")
        return return_list

    def _format_win_rate(self, val, color, field):
        """Converts raw winrate to Grade (A+) or Rating (0-5.0) based on set metrics."""
        if not self.metrics:
            return val
        mean, std = self.metrics.get_metrics(color, field)
        if std == 0:
            return val
        z_score = (val - mean) / std

        if self.configuration.settings.result_format == constants.RESULT_FORMAT_GRADE:
            for grade, limit in constants.GRADE_DEVIATION_DICT.items():
                if z_score >= limit:
                    return grade
            return constants.LETTER_GRADE_F
        elif (
            self.configuration.settings.result_format == constants.RESULT_FORMAT_RATING
        ):
            upper, lower = mean + (2.0 * std), mean - (1.67 * std)
            if upper == lower:
                return 2.5
            rating = ((val - lower) / (upper - lower)) * 5.0
            return round(max(0.0, min(5.0, rating)), 1)
        return val


# === EXTRACTED LOGIC IMPORTS ===
# Re-exported so existing callers can keep importing the advisor API from
# src.card_logic. The advisor modules never import src.card_logic at module
# level (shared helpers live in src.card_utils), so there is no import cycle.
from src.advisor.simulator import simulate_deck
from src.advisor.mana_base import (
    calculate_dynamic_mana_base,
    create_basic_lands,
    is_castable,
    ManaSourceAnalyzer,
    count_fixing,
    get_strict_colors,
    select_useful_lands,
)
from src.advisor.deck_scorer import (
    TIER_TO_GIHWR,
    get_card_rating,
    identify_top_pairs,
    calculate_holistic_score,
    estimate_record,
)
from src.advisor.deck_builder import (
    GLOBAL_DECK_CACHE,
    clear_deck_cache,
    get_sideboard,
    optimize_deck,
    suggest_deck,
    build_variant_consistency,
    build_variant_greedy,
    build_variant_curve,
    build_variant_soup,
)

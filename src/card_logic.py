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
import re
import numpy
import io
import csv
import json
from src import constants
from src.logger import create_logger

logger = create_logger()

# --- HELPER CLASSES ---


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
    # Pro Metrics
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
    if not configuration.settings.auto_highest_enabled:
        return [constants.FILTER_OPTION_ALL_DECKS]

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
                    mean, std = metrics.get_metrics(
                        pair_str, constants.DATA_FIELD_GIHWR
                    )
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
            c_cmc = int(card.get(constants.DATA_FIELD_CMC, 0))

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
    Used by Signal Calculator and UI.
    """
    colors = {}
    try:
        if not mana_cost:
            return colors

        for color in constants.CARD_COLORS:
            # Count occurrences of the color symbol in the string
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

    # Extract symbols {R}, {U} etc.
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
            # Sanitize styling characters before parsing
            val = field_value.replace("*", "").replace("%", "").strip()

            if val in ["NA", "-", ""]:
                return (0, 0.0)  # Bottom priority

            # Cross-reference with the GRADE dictionary via stripped keys
            for k, v in constants.GRADE_ORDER_DICT.items():
                if k.strip() == val:
                    return (1, float(v))

            return (1, float(val))

        elif field_value is None:
            return (0, 0.0)

        return (1, float(field_value))
    except (ValueError, TypeError):
        # Top priority fallback for valid strings (Names, Colors, etc)
        return (2, str(field_value).lower())


def stack_cards(cards):
    """Consolidates duplicates for UI display."""
    stacked = {}
    for c in cards:
        name = c.get(constants.DATA_FIELD_NAME, "Unknown")
        if name not in stacked:
            stacked[name] = copy.deepcopy(c)
            stacked[name]["count"] = 1
        else:
            stacked[name]["count"] += 1
    return list(stacked.values())


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


# --- LEGACY CLASS FOR DASHBOARD COMPATIBILITY ---


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

                # Default filter color
                primary_color = (
                    colors[0] if colors else constants.FILTER_OPTION_ALL_DECKS
                )

                for count, option in enumerate(fields):
                    # Handle Win Rates
                    if option in constants.WIN_RATE_OPTIONS or option in [
                        "alsa",
                        "iwd",
                        "ata",
                        "ohwr",
                        "gpwr",
                        "gdwr",
                        "gnswr",
                    ]:
                        # Deep lookup
                        stats = card.get("deck_colors", {}).get(primary_color, {})
                        val = stats.get(option, 0.0)

                        # Handle Formatting (Grade/Rating)
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
                    # Handle Tier Lists
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
            upper = mean + (2.0 * std)
            lower = mean - (1.67 * std)
            if upper == lower:
                return 2.5
            rating = ((val - lower) / (upper - lower)) * 5.0
            return round(max(0.0, min(5.0, rating)), 1)

        return val


# --- UNIVERSAL DECK BUILDER & LIQUID SCORING ENGINE ---


def suggest_deck(taken_cards, metrics, configuration, event_type="PremierDraft"):
    """
    Entry point. Generates multiple distinct deck variants based on the pool.
    Evaluates them using a universal, holistic scoring engine and returns the best options.
    """
    sorted_decks = {}
    pool_size = len(taken_cards)
    is_bo3 = "Trad" in event_type

    if not taken_cards or len(taken_cards) < 12:
        return sorted_decks

    try:
        color_options = identify_top_pairs(taken_cards, metrics)
        all_variants = []

        for main_colors in color_options:
            # 1. Variant: Consistency (Strictly 2 colors)
            con_deck = build_variant_consistency(taken_cards, main_colors, metrics)
            if con_deck:
                score, breakdown = calculate_holistic_score(
                    con_deck, main_colors, pool_size, metrics
                )
                # THE EXECUTIONER: Do not display incomplete decks
                if "Incomplete Deck" not in breakdown:
                    all_variants.append(
                        {
                            "label_prefix": "Consistent",
                            "type": "Midrange / Standard",
                            "rating": score,
                            "record": estimate_record(score, is_bo3),
                            "deck_cards": con_deck,
                            "sideboard_cards": [],
                            "colors": main_colors,
                            "breakdown": breakdown,
                        }
                    )

            # 2. Variant: Greedy (Splash bombs/synergy)
            greedy_deck, splash_color = build_variant_greedy(
                taken_cards, main_colors, metrics
            )
            if greedy_deck:
                target_colors = main_colors + [splash_color]
                score, breakdown = calculate_holistic_score(
                    greedy_deck, target_colors, pool_size, metrics
                )
                if "Incomplete Deck" not in breakdown:
                    all_variants.append(
                        {
                            "label_prefix": f"Splash {splash_color}",
                            "type": "Power / Domain",
                            "rating": score,
                            "record": estimate_record(score, is_bo3),
                            "deck_cards": greedy_deck,
                            "sideboard_cards": [],
                            "colors": target_colors,
                            "breakdown": breakdown,
                        }
                    )

            # 3. Variant: Tempo (Low curve, aggro)
            tempo_deck = build_variant_curve(taken_cards, main_colors, metrics)
            if tempo_deck:
                score, breakdown = calculate_holistic_score(
                    tempo_deck, main_colors, pool_size, metrics
                )
                if "Incomplete Deck" not in breakdown:
                    all_variants.append(
                        {
                            "label_prefix": "Tempo",
                            "type": "Aggro",
                            "rating": score,
                            "record": estimate_record(score, is_bo3),
                            "deck_cards": tempo_deck,
                            "sideboard_cards": [],
                            "colors": main_colors,
                            "breakdown": breakdown,
                        }
                    )

        # Sort all generated variants by their holistic score
        all_variants.sort(key=lambda x: x["rating"], reverse=True)

        # Filter out duplicates (e.g. if Tempo and Consistent generated the exact same 40 cards)
        seen_signatures = set()
        for variant in all_variants:
            # Create a unique signature for the deck based on card names and counts
            sig = tuple(
                sorted(
                    [
                        f"{c.get('name')}:{c.get('count', 1)}"
                        for c in variant["deck_cards"]
                    ]
                )
            )
            if sig in seen_signatures:
                continue
            seen_signatures.add(sig)

            pair_key = "".join(sorted(variant["colors"][:2]))
            label = f"{pair_key} {variant['label_prefix']}"
            sorted_decks[label] = variant

            # Limit to top 5 unique options so we don't overwhelm the UI
            if len(sorted_decks) >= 5:
                break

    except Exception as e:
        logger.error(f"Deck builder failure: {e}", exc_info=True)
        return {}

    return sorted_decks


def identify_top_pairs(pool, metrics):
    """Returns top 2-color pairs based on playability and raw power."""
    global_mean, global_std = metrics.get_metrics("All Decks", "gihwr")
    if global_mean == 0.0:
        global_mean = 54.0
    if global_std == 0.0:
        global_std = 4.0

    playable_baseline = global_mean - (global_std * 0.5)

    scores = {c: 0.0 for c in constants.CARD_COLORS}
    for card in pool:
        colors = card.get(constants.DATA_FIELD_COLORS, [])
        stats = card.get("deck_colors", {}).get("All Decks", {})
        wr = float(stats.get(constants.DATA_FIELD_GIHWR, 0.0))

        if wr > playable_baseline:
            points = (wr - playable_baseline) / global_std
            for c in colors:
                scores[c] += points

    sorted_c = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    # Return the absolute best pair
    top_pairs = [[sorted_c[0][0], sorted_c[1][0]]]

    # ONLY return the 3rd best color if it has at least 25% of the power points of your main color.
    # This prevents the builder from generating options for a color you only picked 2 cards for.
    if len(sorted_c) > 2 and sorted_c[2][1] > (sorted_c[0][1] * 0.25):
        top_pairs.append([sorted_c[0][0], sorted_c[2][0]])
        top_pairs.append([sorted_c[1][0], sorted_c[2][0]])

    return top_pairs


# --- UNIVERSAL LIQUID SCORING ENGINE ---


def calculate_holistic_score(deck, colors, pool_size, metrics):
    """
    Evaluates a deck on a 0-100 Power Level scale.
    Universally applicable to any MTG set by analyzing mechanical structures.
    """
    if not deck:
        return 0.0, ""

    global_mean, global_std = metrics.get_metrics("All Decks", "gihwr")
    if global_mean == 0.0:
        global_mean = 54.0
    if global_std == 0.0:
        global_std = 4.0

    spells = [c for c in deck if constants.CARD_TYPE_LAND not in c.get("types", [])]
    spell_count = sum(c.get("count", 1) for c in spells)

    if spell_count == 0:
        return 0.0, ""

    # 1. BASE POWER
    arch_key = (
        "".join(sorted(colors)) if len(colors) <= 2 else "".join(sorted(colors[:2]))
    )

    # Weight the ratings by the number of copies
    valid_ratings = []
    for c in spells:
        rating = get_card_rating(c, [arch_key], metrics)
        if rating > 0.0:
            valid_ratings.extend([rating] * c.get("count", 1))

    if not valid_ratings:
        avg_gihwr = global_mean - global_std
    else:
        avg_gihwr = sum(valid_ratings) / len(valid_ratings)

    # Convert to z_score of the deck average.
    z_score = (avg_gihwr - global_mean) / global_std
    power_level = 60.0 + (z_score * 16.67)
    breakdown_notes = []

    # 2. FLUID CURVE & MANA VELOCITY
    cmcs = []
    for c in spells:
        cmcs.extend([int(c.get("cmc", 0))] * c.get("count", 1))

    avg_cmc = sum(cmcs) / spell_count

    # Calculate Lands and Sources
    analyzer = ManaSourceAnalyzer(deck)
    land_count = sum(c.get("count", 1) for c in deck if "Land" in c.get("types", []))
    total_mana_sources = (
        land_count + analyzer.any_color_sources + sum(analyzer.sources.values())
    )

    mana_deficit = (avg_cmc * 5.5) - total_mana_sources
    if mana_deficit > 1.5:
        penalty = mana_deficit * 3.0
        power_level -= penalty
        breakdown_notes.append(f"Clunky Mana Velocity (-{penalty:.1f})")
    elif mana_deficit < -1.0 and avg_cmc < 2.8:
        power_level += 5.0
        breakdown_notes.append("Excellent Aggro Velocity (+5.0)")

    # 3. UNIVERSAL SYNERGY MATRIX
    supertypes = {
        "Creature",
        "Instant",
        "Sorcery",
        "Enchantment",
        "Artifact",
        "Planeswalker",
        "Land",
        "Legendary",
        "Basic",
        "Snow",
        "World",
        "Tribal",
        "Kindred",
    }
    subtypes = {}
    changeling_count = 0
    for c in spells:
        text = str(c.get("text", "")).lower()
        count = c.get("count", 1)
        if "changeling" in text:
            changeling_count += count
        for t in c.get("types", []):
            if t not in supertypes:
                subtypes[t] = subtypes.get(t, 0) + count

    if subtypes:
        top_tribe, tribe_count = max(subtypes.items(), key=lambda x: x[1])
        total_tribe_density = tribe_count + changeling_count
        payoff_count = sum(
            c.get("count", 1)
            for c in spells
            if "chosen type" in str(c.get("text", "")).lower()
            or top_tribe.lower() in str(c.get("text", "")).lower()
        )

        if total_tribe_density >= 6 and payoff_count >= 2:
            bonus = (total_tribe_density * 0.5) + (payoff_count * 1.5)
            power_level += bonus
            breakdown_notes.append(f"{top_tribe} Synergy (+{bonus:.1f})")

    if len(colors) >= 3:
        domain_payoffs = sum(
            c.get("count", 1)
            for c in spells
            if "colors among" in str(c.get("text", "")).lower()
            or "basic land types" in str(c.get("text", "")).lower()
        )
        fixing_count = sum(analyzer.sources.values()) + analyzer.any_color_sources

        if domain_payoffs >= 2 and fixing_count >= 4:
            power_level += 6.0
            breakdown_notes.append("Supported Domain/Soup (+6.0)")
        elif fixing_count < len(colors) + 1:
            penalty = (len(colors) + 1 - fixing_count) * 6.0
            power_level -= penalty
            breakdown_notes.append(f"Greedy Mana Strain (-{penalty:.1f})")

    evasion_count = sum(
        c.get("count", 1)
        for c in spells
        if any(
            kw in str(c.get("text", "")).lower()
            for kw in [
                "flying",
                "trample",
                "menace",
                "can't be blocked",
                "deals damage to any target",
            ]
        )
    )
    if evasion_count < 3 and avg_cmc > 2.5:
        power_level -= 5.0
        breakdown_notes.append("Lacks Evasion/Reach (-5.0)")

    # 4. DECK SIZE & PLAYABLES DEFICIT
    expected_spells = int(23 * (min(42, pool_size) / 42.0))
    if spell_count < expected_spells - 1:
        shortfall = (expected_spells - 1) - spell_count
        penalty = shortfall * 10.0
        power_level -= penalty
        breakdown_notes.append(f"Incomplete Deck (-{penalty:.1f})")

    return max(0.0, power_level), ", ".join(breakdown_notes)


def estimate_record(power_level, is_bo3=False):
    """Maps the unbounded Power Level to an expected record."""
    if is_bo3:
        if power_level < 50:
            return "0-2 / 1-2"
        if power_level < 75:
            return "2-1"
        return "3-0 (Trophy!)"
    else:
        if power_level < 40:
            return "0-3 / 1-3"
        if power_level < 55:
            return "2-3 / 3-3"
        if power_level < 75:
            return "4-3 / 5-3"
        if power_level < 90:
            return "6-3"
        return "7-x (Trophy!)"


# --- HEURISTIC BUILDERS ---


def build_variant_consistency(pool, colors, metrics):
    candidates = [
        c
        for c in pool
        if is_castable(c, colors, strict=True) and "Land" not in c.get("types", [])
    ]
    candidates.sort(key=lambda x: get_card_rating(x, colors, metrics), reverse=True)
    spells = candidates[:23]  # Caps at 23 spells max
    non_basic_lands = select_useful_lands(pool, colors)

    # GUARANTEE EXACTLY 40 CARDS
    total_lands_needed = 40 - len(spells)
    needed_basics = max(0, total_lands_needed - len(non_basic_lands))
    basics = calculate_dynamic_mana_base(spells, colors, forced_count=needed_basics)

    return stack_cards(spells + non_basic_lands + basics)


def build_variant_greedy(pool, colors, metrics):
    global_mean, global_std = metrics.get_metrics("All Decks", "gihwr")
    if global_mean == 0.0:
        global_mean = 54.0
    if global_std == 0.0:
        global_std = 4.0

    fixing_sources = count_fixing(pool)
    best_splash = None
    best_rating = global_mean - (global_std * 0.5)

    for card in pool:
        card_colors = card.get("colors", [])
        if (
            not card_colors
            or any(c in colors for c in card_colors)
            or len(card_colors) > 1
        ):
            continue
        splash_col = card_colors[0]
        pips = sum(1 for c in card.get("mana_cost", "") if c == splash_col)
        if pips > 1:
            continue

        rating = get_card_rating(card, ["All Decks"], metrics)
        if rating > best_rating and fixing_sources.get(splash_col, 0) >= 1:
            best_rating = rating
            best_splash = (card, splash_col)

    if not best_splash:
        return None, ""

    main_spells = [
        c
        for c in pool
        if is_castable(c, colors, strict=True) and "Land" not in c.get("types", [])
    ]
    main_spells.sort(key=lambda x: get_card_rating(x, colors, metrics), reverse=True)
    deck_spells = main_spells[:22] + [best_splash[0]]

    target_colors = colors + [best_splash[1]]
    non_basic_lands = select_useful_lands(pool, target_colors)

    # GUARANTEE EXACTLY 40 CARDS
    total_lands_needed = 40 - len(deck_spells)
    needed_basics = max(0, total_lands_needed - len(non_basic_lands))
    basics = calculate_dynamic_mana_base(
        deck_spells, target_colors, forced_count=needed_basics
    )

    return stack_cards(deck_spells + non_basic_lands + basics), best_splash[1]


def build_variant_curve(pool, colors, metrics):
    candidates = [
        c
        for c in pool
        if is_castable(c, colors, strict=True) and "Land" not in c.get("types", [])
    ]

    def tempo_rating(card):
        base = get_card_rating(card, colors, metrics)
        cmc = int(card.get("cmc", 0))
        if cmc <= 2:
            return base + 4.0
        if cmc >= 5:
            return base - 8.0
        return base

    candidates.sort(key=tempo_rating, reverse=True)
    spells = candidates[:24]  # Caps at 24 spells max for aggro
    non_basic_lands = select_useful_lands(pool, colors)

    # GUARANTEE EXACTLY 40 CARDS
    total_lands_needed = 40 - len(spells)
    needed_basics = max(0, total_lands_needed - len(non_basic_lands))
    basics = calculate_dynamic_mana_base(spells, colors, forced_count=needed_basics)

    return stack_cards(spells + non_basic_lands + basics)


# --- UTILITIES ---


def select_useful_lands(pool, target_colors):
    useful_lands = []
    for card in pool:
        if "Land" not in card.get("types", []) or "Basic" in card.get("types", []):
            continue
        name, text, card_colors = (
            card.get("name", "").lower(),
            str(card.get("text", "")).lower(),
            card.get("colors", []),
        )
        if (
            any(fn in name for fn in constants.FIXING_NAMES)
            or "search your library for a basic land" in text
        ):
            useful_lands.append(card)
        elif card_colors and any(c in target_colors for c in card_colors):
            useful_lands.append(card)
    return useful_lands


def calculate_dynamic_mana_base(spells, colors, forced_count=17):
    """
    Advanced Mana Base algorithm. Uses proportional division but enforces
    strict minimums to prevent color screw (e.g. 10/7 split instead of 13/4).
    """
    if forced_count <= 0:
        return []

    pips = {c: 0 for c in constants.CARD_COLORS}
    for card in spells:
        cost = card.get("mana_cost") or ""
        for char in cost:
            if char in pips:
                pips[char] += 1

    active_pips = {c: p for c, p in pips.items() if c in colors and p > 0}
    total_pips = sum(active_pips.values())
    lands = []

    # Fallback if no colored pips exist (e.g., all artifacts)
    if total_pips == 0:
        for c in colors[:2]:
            lands.extend(create_basic_lands(c, forced_count // max(1, len(colors))))
        rem = forced_count - len(lands)
        if rem > 0 and colors:
            lands.extend(create_basic_lands(colors[0], rem))
        return lands

    allocations = {c: 0 for c in active_pips}
    remaining = forced_count

    # Step 1: Assign Safety Floors
    for c, p in active_pips.items():
        if p >= 4:
            # Secondary color requires at least 6-7 sources. We guarantee 6 basics if possible.
            minimum = min(6, remaining)
        else:
            # Light splash requires at least 3 sources
            minimum = min(3, remaining)

        allocations[c] += minimum
        remaining -= minimum

    # Step 2: Distribute the remaining lands proportionally
    if remaining > 0:
        for c in active_pips:
            extra = int(round(remaining * (active_pips[c] / total_pips)))
            allocations[c] += extra

        # Handle floating point rounding overflow/underflow
        current_total = sum(allocations.values())
        diff = forced_count - current_total

        if diff > 0:
            # Give to the color with the most pips
            top_color = max(active_pips, key=active_pips.get)
            allocations[top_color] += diff
        elif diff < 0:
            # Take away from the color with the least pips (without violating math)
            bottom_color = min(active_pips, key=active_pips.get)
            allocations[bottom_color] += diff

    # Step 3: Generate the actual cards
    for c, count in allocations.items():
        if count > 0:
            lands.extend(create_basic_lands(c, count))

    # Final failsafe in case of weird pip dictionaries
    final_diff = forced_count - len(lands)
    if final_diff > 0 and colors:
        lands.extend(create_basic_lands(colors[0], final_diff))

    return lands


def create_basic_lands(color, count):
    if count <= 0:
        return []
    map_name = {
        "W": "Plains",
        "U": "Island",
        "B": "Swamp",
        "R": "Mountain",
        "G": "Forest",
    }
    return [
        {
            "name": map_name.get(color, "Wastes"),
            "cmc": 0,
            "types": ["Land", "Basic"],
            "colors": [color],
            "count": 1,
        }
    ] * count


def is_castable(card, colors, strict=True):
    card_colors = card.get("colors", [])
    if not card_colors:
        return True
    if strict:
        return all(c in colors for c in card_colors)
    return any(c in colors for c in card_colors)


def get_card_rating(card, colors, metrics=None):
    """
    Synthesizes Archetype data with Global data.
    Ensures that universally good cards (Bombs) are always valued highly,
    even if data is sparse in a specific color pairing.
    """
    global_mean = 54.0
    if metrics:
        mean_val, _ = metrics.get_metrics("All Decks", "gihwr")
        if mean_val > 0:
            global_mean = mean_val

    stats = card.get("deck_colors", {})

    # 1. Always get the Global baseline first
    global_stats = stats.get("All Decks", {})
    global_wr = float(global_stats.get("gihwr", 0.0))

    # 2. Try to get the specific archetype data
    arch_key = (
        "".join(sorted(colors)) if len(colors) <= 2 else "".join(sorted(colors[:2]))
    )
    arch_stats = stats.get(arch_key, {})
    arch_wr = float(arch_stats.get("gihwr", 0.0))

    # 3. Blending Logic
    if arch_wr > 30.0 and global_wr > 30.0:
        # If we have valid data for both, blend them.
        # 70% weight to the specific archetype, 30% weight to the global power of the card.
        return (arch_wr * 0.7) + (global_wr * 0.3)
    elif global_wr > 30.0:
        # If the archetype data is missing or 0.0 (data sparsity), rely 100% on global stats.
        return global_wr
    else:
        # If the card is completely unknown, assume baseline filler relative to the set
        return global_mean - 4.0


class ManaSourceAnalyzer:
    def __init__(self, pool):
        self.pool = pool
        self.sources = {c: 0 for c in constants.CARD_COLORS}
        self.any_color_sources = 0
        for card in self.pool:
            self._evaluate(card)

    def _evaluate(self, card):
        count = card.get("count", 1)
        types, text, name = (
            card.get("types", []),
            str(card.get("text", "")).lower(),
            card.get("name", "").lower(),
        )
        if "Land" in types and "Basic" not in types:
            for c in card.get("colors", []):
                self.sources[c] += count
            if any(fn in name for fn in constants.FIXING_NAMES) or "any color" in text:
                self.any_color_sources += count
        elif (
            "Artifact" in types
            and not any(c in card.get("mana_cost", "") for c in "WUBRG")
            and card.get("colors")
        ):
            for c in card.get("colors", []):
                self.sources[c] += count
        elif (
            "treasure" in text
            or "search your library for a basic land" in text
            or "basic landcycling" in text
        ):
            self.any_color_sources += count
        elif "Creature" in types and "G" in card.get("colors", []) and "add {" in text:
            for c in card.get("colors", []):
                self.sources[c] += count


def count_fixing(pool):
    analyzer = ManaSourceAnalyzer(pool)
    res = {
        c: analyzer.sources[c] + analyzer.any_color_sources
        for c in constants.CARD_COLORS
    }
    return res


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

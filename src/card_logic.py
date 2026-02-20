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


# --- UI UTILITIES (Restored) ---


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
            # Convert ["U", "B"] -> "UB"
            pair_str = "".join(sorted(top_pair[0]))

            # Check if this pair exists in known deck colors (it should)
            # We also return All Decks as a fallback/context
            return [pair_str] if pair_str else [constants.FILTER_OPTION_ALL_DECKS]

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
            field_value = field_value.replace("*", "").strip()
        if field_value in constants.GRADE_ORDER_DICT:
            return constants.GRADE_ORDER_DICT[field_value]
        return float(field_value)
    except (ValueError, TypeError):
        return 0


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


# --- CORE DECK BUILDER LOGIC (Pro Tour) ---


def suggest_deck(taken_cards, metrics, configuration):
    """
    Entry point. Generates 3 distinct deck variants based on the pool.
    """
    sorted_decks = {}

    try:
        # 1. Identify Top Color Pairs
        # We look for the strongest 2-color combinations in the pool
        color_options = identify_top_pairs(taken_cards, metrics)

        for main_colors in color_options:
            pair_key = "".join(sorted(main_colors))

            # --- VARIANT A: The Rock (Consistency) ---
            rock_deck, rock_score = build_variant_consistency(
                taken_cards, main_colors, metrics
            )
            if rock_deck:
                label = f"{pair_key} Consistent"
                sorted_decks[label] = {
                    "type": "Midrange",
                    "rating": rock_score,
                    "deck_cards": rock_deck,
                    "sideboard_cards": [],  # Simplified
                    "colors": main_colors,
                }

            # --- VARIANT B: The Greedy (Splash) ---
            greedy_deck, greedy_score, splash_color = build_variant_greedy(
                taken_cards, main_colors, metrics
            )
            # Only suggest greedy if it's actually stronger or we have a bomb
            if greedy_deck and greedy_score > rock_score:
                label = f"{pair_key} Splash {splash_color}"
                sorted_decks[label] = {
                    "type": "Bomb Splash",
                    "rating": greedy_score,
                    "deck_cards": greedy_deck,
                    "sideboard_cards": [],
                    "colors": main_colors + [splash_color],
                }

            # --- VARIANT C: The Curve (Aggro) ---
            curve_deck, curve_score = build_variant_curve(
                taken_cards, main_colors, metrics
            )
            if curve_deck:
                label = f"{pair_key} Tempo"
                sorted_decks[label] = {
                    "type": "Aggro",
                    "rating": curve_score,
                    "deck_cards": curve_deck,
                    "sideboard_cards": [],
                    "colors": main_colors,
                }

    except Exception as e:
        logger.error(f"Deck builder failure: {e}", exc_info=True)
        return {}

    return sorted_decks


def identify_top_pairs(pool, metrics):
    """Returns top color pair based on card count and quality."""
    scores = {c: 0 for c in constants.CARD_COLORS}

    for card in pool:
        colors = card.get(constants.DATA_FIELD_COLORS, [])
        # Get GIHWR
        stats = card.get("deck_colors", {}).get(constants.FILTER_OPTION_ALL_DECKS, {})
        wr = float(stats.get(constants.DATA_FIELD_GIHWR, 0.0))

        # Simple points: WR - 50. (55% = 5 points). Only count playables.
        if wr > 50:
            points = wr - 50
            for c in colors:
                scores[c] += points

    # Sort colors
    sorted_c = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    # Take top 2
    top_2 = [x[0] for x in sorted_c[:2]]

    return [top_2]


# --- BUILDER VARIANTS ---


def build_variant_consistency(pool, colors, metrics):
    """
    Builds the best deck using ONLY the main colors.
    Target: 23 Spells, 17 Lands (Baseline).
    """
    candidates = [
        c
        for c in pool
        if is_castable(c, colors, strict=True)
        and constants.CARD_TYPE_LAND not in c.get(constants.DATA_FIELD_TYPES, [])
    ]

    # Sort by Power (GIHWR)
    candidates.sort(key=lambda x: get_card_rating(x, colors), reverse=True)

    # Select Spells
    spells = candidates[:23]

    # Select Useful Lands (Evolving Wilds, Duals, etc.)
    non_basic_lands = select_useful_lands(pool, colors)

    # Calculate Mana Base
    land_count_needed = 17 - len(non_basic_lands)
    basics = calculate_dynamic_mana_base(spells, colors, forced_count=land_count_needed)

    deck = stack_cards(spells + non_basic_lands + basics)
    score = calculate_deck_score(spells)

    return deck, score


def build_variant_greedy(pool, colors, metrics):
    """
    Tries to splash high-power cards.
    """
    # 1. Find Splash Candidates (Bombs, Single Pip, Off-Color)
    splash_candidates = []
    fixing_sources = count_fixing(pool)

    for card in pool:
        card_colors = card.get(constants.DATA_FIELD_COLORS, [])
        if not card_colors or any(c in colors for c in card_colors):
            continue  # Already in color

        # Must be single color splash for simplicity
        if len(card_colors) > 1:
            continue
        splash_col = card_colors[0]

        # Check Pips
        mana_cost = card.get(constants.DATA_FIELD_MANA_COST, "")
        pips = sum(1 for c in mana_cost if c == splash_col)

        if pips > 1:
            continue  # No double pip splashes

        # Check Power (Must be better than average ~55%)
        rating = get_card_rating(card, ["All Decks"])
        if rating < 58.0:
            continue

        # Check Fixing
        # Need basic land + sources
        if fixing_sources.get(splash_col, 0) >= 1:
            splash_candidates.append((card, splash_col, rating))

    if not splash_candidates:
        return None, 0, ""

    # Sort candidates
    splash_candidates.sort(key=lambda x: x[2], reverse=True)
    best_splash = splash_candidates[0]

    splash_card = best_splash[0]
    splash_color = best_splash[1]

    # Build Deck
    main_spells = [
        c
        for c in pool
        if is_castable(c, colors, strict=True)
        and constants.CARD_TYPE_LAND not in c.get(constants.DATA_FIELD_TYPES, [])
    ]
    main_spells.sort(key=lambda x: get_card_rating(x, colors), reverse=True)

    # 22 Main + 1 Splash
    deck_spells = main_spells[:22] + [splash_card]

    # Select Useful Lands (Including the splash color)
    target_colors = colors + [splash_color]
    non_basic_lands = select_useful_lands(pool, target_colors)

    # Mana Base (Include Splash Basic)
    land_count_needed = 17 - len(non_basic_lands)
    basics = calculate_dynamic_mana_base(
        deck_spells, target_colors, forced_count=land_count_needed
    )

    deck = stack_cards(deck_spells + non_basic_lands + basics)
    score = calculate_deck_score(deck_spells) + 50  # Bonus for hitting the splash

    return deck, score, splash_color


def build_variant_curve(pool, colors, metrics):
    """
    Prioritizes low CMC. Forces 16 Lands.
    """
    candidates = [
        c
        for c in pool
        if is_castable(c, colors, strict=True)
        and constants.CARD_TYPE_LAND not in c.get(constants.DATA_FIELD_TYPES, [])
    ]

    # Custom Sort: Penalize High CMC
    def tempo_rating(card):
        base = get_card_rating(card, colors)
        cmc = int(card.get(constants.DATA_FIELD_CMC, 0))
        if cmc <= 2:
            return base * 1.1  # Boost cheap stuff
        if cmc >= 5:
            return base * 0.7  # Penalty
        return base

    candidates.sort(key=tempo_rating, reverse=True)
    spells = candidates[:24]  # 24 Spells, 16 Lands

    # Select Useful Lands
    non_basic_lands = select_useful_lands(pool, colors)

    # Force 16 Lands total
    land_count_needed = max(0, 16 - len(non_basic_lands))
    basics = calculate_dynamic_mana_base(spells, colors, forced_count=land_count_needed)

    deck = stack_cards(spells + non_basic_lands + basics)
    score = calculate_deck_score(spells)

    return deck, score


# --- UTILITIES ---


def select_useful_lands(pool, target_colors):
    """
    Filters the card pool for non-basic lands that are useful for the target deck colors.
    Includes Dual Lands, Fetch Lands (Evolving Wilds), and Utility Lands.
    """
    useful_lands = []

    for card in pool:
        if constants.CARD_TYPE_LAND not in card.get(constants.DATA_FIELD_TYPES, []):
            continue

        # Ignore Basics (handled by calculator)
        if "Basic" in card.get(constants.DATA_FIELD_TYPES, []):
            continue

        name = card.get(constants.DATA_FIELD_NAME, "")
        text = card.get("text", "")
        card_colors = card.get(constants.DATA_FIELD_COLORS, [])

        # 1. "Any Color" Fetch/Fixers (Evolving Wilds, etc.)
        if any(fn in name for fn in constants.FIXING_NAMES):
            useful_lands.append(card)
            continue

        # 2. Dual/Tri Lands matching identity
        # If the land has colors, they must match our target colors
        # e.g. If we are UB, we take UB lands. We usually ignore GW lands.
        if card_colors:
            # Check if land shares ANY color with our targets (Loose check for now)
            # Better check: Does it produce ONLY colors we need?
            # Or at least one?
            if any(c in target_colors for c in card_colors):
                useful_lands.append(card)
                continue

    return useful_lands


def calculate_dynamic_mana_base(spells, colors, forced_count=None):
    """
    Frank-Karsten Logic:
    1. Calculate Avg CMC of spells.
    2. Determine total land count.
    3. Calculate color ratio based on Pips.
    """
    # 1. Total Count
    if forced_count is not None:
        total_lands = forced_count
    else:
        total_cmc = sum(int(c.get(constants.DATA_FIELD_CMC, 0)) for c in spells)
        avg_cmc = total_cmc / len(spells) if spells else 3.0
        total_lands = 17 + round((avg_cmc - 3.0))
        total_lands = max(15, min(18, total_lands))

    if total_lands <= 0:
        return []

    # 2. Pip Counts
    pips = {c: 0 for c in constants.CARD_COLORS}
    for card in spells:
        cost = card.get(constants.DATA_FIELD_MANA_COST, "")
        if cost:
            for char in cost:
                if char in pips:
                    pips[char] += 1
        else:
            # Fallback for cards without mana cost field (should be rare)
            for c in card.get("colors", []):
                if c in pips:
                    pips[c] += 1

    # 3. Allocate Basics
    active_pips = {c: p for c, p in pips.items() if c in colors and p > 0}
    total_pips = sum(active_pips.values())

    lands = []

    if total_pips == 0:
        # Fallback distribution
        for c in colors[:2]:
            count = total_lands // max(1, len(colors))
            lands.extend(create_basic_lands(c, count))
        return lands

    remaining_lands = total_lands

    # Allocate based on ratio
    for color in active_pips:
        ratio = active_pips[color] / total_pips
        count = int(round(total_lands * ratio))
        # Ensure minimums for splash
        if count < 3 and color in colors and len(colors) > 2:
            count = 3

        count = min(count, remaining_lands)
        if count > 0:
            lands.extend(create_basic_lands(color, count))
            remaining_lands -= count

    # Dump remainder into primary color
    if remaining_lands > 0 and colors:
        lands.extend(create_basic_lands(colors[0], remaining_lands))

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
            constants.DATA_FIELD_NAME: map_name.get(color, "Wastes"),
            constants.DATA_FIELD_CMC: 0,
            constants.DATA_FIELD_TYPES: [constants.CARD_TYPE_LAND, "Basic"],
            constants.DATA_FIELD_COLORS: [color],
            "count": 1,
        }
    ] * count


def is_castable(card, colors, strict=True):
    card_colors = card.get(constants.DATA_FIELD_COLORS, [])
    if not card_colors:
        return True  # Artifact
    if strict:
        return all(c in colors for c in card_colors)
    return any(c in colors for c in card_colors)


def get_card_rating(card, colors):
    """Safe accessor for GIHWR."""
    key = "".join(sorted(colors))
    stats = card.get("deck_colors", {})
    val = stats.get(key, {}).get(constants.DATA_FIELD_GIHWR, 0.0)
    if val == 0.0:
        val = stats.get("All Decks", {}).get(constants.DATA_FIELD_GIHWR, 0.0)
    return float(val)


class ManaSourceAnalyzer:
    """
    Advanced heuristic engine to identify mana sources in a card pool.
    Distinguishes between Lands, Dorks, Rocks, and Treasures.
    """

    def __init__(self, pool):
        self.pool = pool
        self.sources = {c: 0 for c in constants.CARD_COLORS}  # W, U, B, R, G
        self.any_color_sources = 0
        self.treasure_sources = 0
        self._analyze()

    def _analyze(self):
        for card in self.pool:
            self._evaluate_card(card)

    def _evaluate_card(self, card):
        name = card.get(constants.DATA_FIELD_NAME, "")
        types = card.get(constants.DATA_FIELD_TYPES, [])
        text = card.get("text", "")  # Assuming text might be populated

        # 1. LANDS
        if constants.CARD_TYPE_LAND in types:
            # Basic Lands don't count as "Fixing" (they are the baseline)
            # We look for Non-Basics
            if "Basic" not in types:
                self._process_dual_land(card)
                self._check_text_fixing(name, text)
            return

        # 2. ARTIFACTS (Rocks)
        if constants.CARD_TYPE_ARTIFACT in types:
            # Heuristic: If Identity has colors but Cost is colorless = Signet/Rock
            if self._is_colored_rock(card):
                self._add_identity_sources(card)
            # Check for "Any Color" rocks (Prism, etc)
            elif self._check_text_fixing(name, text):
                pass
            return

        # 3. SPELLS / CREATURES (Dorks/Treasures/Ramp)
        # Check for Treasure generation
        if "Treasure" in name or "Treasure" in text:
            self.treasure_sources += 1
            self.any_color_sources += 1  # Treasures fix anything once

        # Check for "Search Library" (Rampant Growth)
        if "Search your library" in text and "land" in text:
            self.any_color_sources += 1  # Effectively fixes any color

        # Check for Landcyclers (e.g. Basic Landcycling, Swampcycling)
        if "cycling" in text and (
            "Basic" in text
            or "land" in text
            or any(
                c in text for c in ["Plains", "Island", "Swamp", "Mountain", "Forest"]
            )
        ):
            self.any_color_sources += 1

        # Check for Mana Dorks (Green creatures usually)
        if "Creature" in types and "Green" in card.get(constants.DATA_FIELD_COLORS, []):
            if "Add {" in text:
                self._add_identity_sources(card)

    def _process_dual_land(self, card):
        """
        If a land has multiple colors in identity, it fixes those colors.
        Colorless lands must be checked via text/name analysis elsewhere.
        """
        colors = card.get(constants.DATA_FIELD_COLORS, [])
        if len(colors) > 1:
            for c in colors:
                self.sources[c] += 1

    def _is_colored_rock(self, card):
        """Returns True if card costs generic mana but produces colored mana."""
        mana_cost = card.get(constants.DATA_FIELD_MANA_COST, "")
        colors = card.get(constants.DATA_FIELD_COLORS, [])

        # No colored pips in cost
        if not any(c in mana_cost for c in "WUBRG"):
            # But has color identity (e.g. Commander identity logic applies to limited rocks often)
            if len(colors) > 0:
                return True
        return False

    def _add_identity_sources(self, card):
        for c in card.get(constants.DATA_FIELD_COLORS, []):
            self.sources[c] += 1

    def _check_text_fixing(self, name, text):
        """Scans name and text for known fixing phrases (Case Insensitive)."""
        is_fixer = False

        # Enforce Case Insensitivity
        name_lower = name.lower()
        text_lower = text.lower()

        # Check Name List
        if any(fn in name_lower for fn in constants.FIXING_NAMES):
            self.any_color_sources += 1
            is_fixer = True

        # Check Text Keywords
        elif any(kw in text_lower for kw in constants.FIXING_KEYWORDS):
            # Keyword matched (e.g. "search your library", "create a treasure")
            # We assume this provides generic fixing capability
            self.any_color_sources += 1
            is_fixer = True

        # Check Direct Mana Symbols (e.g. "Add {G}")
        # We explicitly iterate valid colors to avoid catching "{C}" or "{1}"
        else:
            for color in constants.CARD_COLORS:
                # Look for symbol with braces: "{g}" or "{r}"
                symbol = "{" + color.lower() + "}"
                if symbol in text_lower:
                    self.sources[color] += 1
                    is_fixer = True

        return is_fixer

    def get_fixing_for_color(self, color):
        """Returns total sources for a specific splash color."""
        return self.sources.get(color, 0) + self.any_color_sources


# --- UPDATED HELPER FUNCTIONS ---


def count_fixing(pool):
    """
    Replacement for the old simple counter.
    Returns a dictionary of extra sources provided by the pool.
    """
    analyzer = ManaSourceAnalyzer(pool)

    results = {c: analyzer.sources[c] for c in constants.CARD_COLORS}

    # Add 'Any' sources to all colors
    for c in results:
        results[c] += analyzer.any_color_sources

    return results


def calculate_deck_score(deck):
    return sum(get_card_rating(c, ["All Decks"]) for c in deck)


def export_draft_to_csv(history, dataset, picked_cards_map):
    output = io.StringIO()
    writer = csv.writer(output)

    # Headers match test expectation (Picked must be index 2)
    headers = [
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
    writer.writerow(headers)

    if not history:
        return output.getvalue()

    # Determine user's picked cards flat list for checking
    # picked_cards_map is list of lists, index 0 is user's seat
    user_picks = picked_cards_map[0] if picked_cards_map else []

    for entry in history:
        pack = entry["Pack"]
        pick = entry["Pick"]
        card_ids = entry["Cards"]

        for cid in card_ids:
            card_obj_list = dataset.get_data_by_id([cid])
            if not card_obj_list:
                continue
            card = card_obj_list[0]

            picked_flag = "1" if str(cid) in user_picks else "0"

            # Stats (default to empty string if missing)
            stats = card.get("deck_colors", {}).get("All Decks", {})

            row = [
                pack,
                pick,
                picked_flag,
                card.get("name", "Unknown"),
                "".join(card.get("colors", [])),
                str(card.get("cmc", "")),
                " ".join(card.get("types", [])),
                stats.get("gihwr", ""),
                stats.get("alsa", ""),
                stats.get("ata", ""),
                stats.get("iwd", ""),
            ]
            writer.writerow(row)

    return output.getvalue()


def export_draft_to_json(history, dataset, picked_cards_map):
    output = []
    user_picks = picked_cards_map[0] if picked_cards_map else []

    for entry in history:
        pack_data = {"Pack": entry["Pack"], "Pick": entry["Pick"], "Cards": []}

        for cid in entry["Cards"]:
            card_obj_list = dataset.get_data_by_id([cid])
            if not card_obj_list:
                continue
            card = card_obj_list[0]

            card_entry = {
                "Name": card.get("name", "Unknown"),
                "Picked": (str(cid) in user_picks),
                "Colors": card.get("colors", []),
                "CMC": card.get("cmc", 0),
                "Type": card.get("types", []),
            }
            pack_data["Cards"].append(card_entry)

        output.append(pack_data)

    return json.dumps(output, indent=4)

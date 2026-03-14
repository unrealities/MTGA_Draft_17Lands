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
            upper = mean + (2.0 * std)
            lower = mean - (1.67 * std)
            if upper == lower:
                return 2.5
            rating = ((val - lower) / (upper - lower)) * 5.0
            return round(max(0.0, min(5.0, rating)), 1)

        return val


# --- UNIVERSAL DECK BUILDER & LIQUID SCORING ENGINE ---


def get_sideboard(pool, deck_stacked):
    """Calculates sideboard by subtracting drafted deck from raw pool."""
    pool_stacked = stack_cards(pool)
    sideboard = []
    deck_counts = {c.get("name"): c.get("count", 1) for c in deck_stacked}
    for c in pool_stacked:
        name = c.get("name")
        total_count = c.get("count", 1)
        used_count = deck_counts.get(name, 0)
        sb_count = total_count - used_count
        if sb_count > 0:
            import copy

            sb_card = copy.deepcopy(c)
            sb_card["count"] = sb_count
            sideboard.append(sb_card)
    return sideboard


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
        incomplete_variants = []

        for main_colors in color_options:
            # 1. Variant: Consistency (Strictly 2 colors)
            con_deck = build_variant_consistency(taken_cards, main_colors, metrics)
            if con_deck:
                score, breakdown = calculate_holistic_score(
                    con_deck, main_colors, pool_size, metrics
                )
                variant_data = {
                    "label_prefix": "Consistent",
                    "type": "Midrange / Standard",
                    "rating": score,
                    "record": estimate_record(score, is_bo3),
                    "deck_cards": con_deck,
                    "sideboard_cards": get_sideboard(taken_cards, con_deck),
                    "colors": main_colors,
                    "breakdown": breakdown,
                }
                if "Incomplete Deck" not in breakdown:
                    all_variants.append(variant_data)
                else:
                    incomplete_variants.append(variant_data)

            # 2. Variant: Greedy (Splash bombs/synergy)
            greedy_deck, splash_color = build_variant_greedy(
                taken_cards, main_colors, metrics
            )
            if greedy_deck:
                target_colors = main_colors + [splash_color]
                score, breakdown = calculate_holistic_score(
                    greedy_deck, target_colors, pool_size, metrics
                )
                variant_data = {
                    "label_prefix": f"Splash {splash_color}",
                    "type": "Power / Domain",
                    "rating": score,
                    "record": estimate_record(score, is_bo3),
                    "deck_cards": greedy_deck,
                    "sideboard_cards": get_sideboard(taken_cards, greedy_deck),
                    "colors": target_colors,
                    "breakdown": breakdown,
                }
                if "Incomplete Deck" not in breakdown:
                    all_variants.append(variant_data)
                else:
                    incomplete_variants.append(variant_data)

            # 3. Variant: Tempo (Low curve, aggro)
            tempo_deck = build_variant_curve(taken_cards, main_colors, metrics)
            if tempo_deck:
                score, breakdown = calculate_holistic_score(
                    tempo_deck, main_colors, pool_size, metrics
                )
                variant_data = {
                    "label_prefix": "Tempo",
                    "type": "Aggro",
                    "rating": score,
                    "record": estimate_record(score, is_bo3),
                    "deck_cards": tempo_deck,
                    "sideboard_cards": get_sideboard(taken_cards, tempo_deck),
                    "colors": main_colors,
                    "breakdown": breakdown,
                }
                if "Incomplete Deck" not in breakdown:
                    all_variants.append(variant_data)
                else:
                    incomplete_variants.append(variant_data)

        # 4. Variant: Good Stuff Soup (Fallback for disjointed drafts)
        soup_deck, soup_colors = build_variant_soup(taken_cards, metrics)
        if soup_deck:
            score, breakdown = calculate_holistic_score(
                soup_deck, soup_colors, pool_size, metrics
            )
            variant_data = {
                "label_prefix": "Good Stuff (Soup)",
                "type": "Domain / 4+ Colors",
                "rating": score,
                "record": estimate_record(score, is_bo3),
                "deck_cards": soup_deck,
                "sideboard_cards": get_sideboard(taken_cards, soup_deck),
                "colors": soup_colors[:3] if soup_colors else ["All Decks"],
                "breakdown": breakdown,
            }
            if "Incomplete Deck" not in breakdown:
                all_variants.append(variant_data)
            else:
                incomplete_variants.append(variant_data)

        if not all_variants and incomplete_variants:
            all_variants = incomplete_variants

        all_variants.sort(key=lambda x: x["rating"], reverse=True)

        seen_signatures = set()
        for variant in all_variants:
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

            pair_key = "".join(sorted(variant["colors"]))
            label = f"{pair_key} {variant['label_prefix']}"
            sorted_decks[label] = variant

            if len(sorted_decks) >= 10:
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

    top_pairs = []
    top_4_colors = [c[0] for c in sorted_c[:4]]

    from itertools import combinations

    for pair in combinations(top_4_colors, 2):
        top_pairs.append(list(pair))

    return top_pairs


# --- UNIVERSAL LIQUID SCORING ENGINE ---


def calculate_holistic_score(deck, colors, pool_size, metrics):
    """
    Evaluates a deck on a 0-100 Power Level scale.
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

    valid_ratings = []
    for c in spells:
        rating = get_card_rating(c, [arch_key], metrics)
        if rating > 0.0:
            valid_ratings.extend([rating] * c.get("count", 1))

    if not valid_ratings:
        avg_gihwr = global_mean - global_std
    else:
        avg_gihwr = sum(valid_ratings) / len(valid_ratings)

    z_score = (avg_gihwr - global_mean) / global_std
    power_level = 60.0 + (z_score * 16.67)
    breakdown_notes = []

    # 2. FLUID CURVE & MANA VELOCITY
    cmcs = []
    for c in spells:
        cmcs.extend([int(c.get("cmc", 0))] * c.get("count", 1))

    avg_cmc = sum(cmcs) / spell_count

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

        fixing_count = analyzer.total_fixing_cards

        if domain_payoffs >= 2 and fixing_count >= 4:
            power_level += 6.0
            breakdown_notes.append("Supported Domain/Soup (+6.0)")
        elif fixing_count < len(colors) - 1:
            penalty = (len(colors) - 1 - fixing_count) * 6.0
            power_level -= penalty
            breakdown_notes.append(f"Greedy Mana Strain (-{penalty:.1f})")

    evasion_count = sum(
        c.get("count", 1)
        for c in spells
        if "evasion" in c.get("tags", [])
        or any(
            kw in str(c.get("text", "")).lower()
            for kw in [
                "flying",
                "trample",
                "menace",
                "can't be blocked",
                "unblockable",
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
    spells = candidates[:23]
    non_basic_lands = select_useful_lands(pool, colors)

    total_lands_needed = 40 - len(spells)
    needed_basics = max(0, total_lands_needed - len(non_basic_lands))
    basics = calculate_dynamic_mana_base(
        spells, non_basic_lands, colors, forced_count=needed_basics
    )

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
        mana_cost = card.get("mana_cost", "")

        if is_castable(card, colors, strict=True):
            continue

        if not card_colors or len(card_colors) > 1:
            continue

        splash_col = card_colors[0]

        pips = re.findall(r"\{(.*?)\}", mana_cost)
        off_color_pips = 0
        for pip in pips:
            options = [c for c in pip.split("/") if c in constants.CARD_COLORS]
            if not options:
                continue
            if not any(opt in colors for opt in options):
                off_color_pips += 1

        if off_color_pips > 1:
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

    total_lands_needed = 40 - len(deck_spells)
    needed_basics = max(0, total_lands_needed - len(non_basic_lands))
    basics = calculate_dynamic_mana_base(
        deck_spells, non_basic_lands, target_colors, forced_count=needed_basics
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
    spells = candidates[:24]
    non_basic_lands = select_useful_lands(pool, colors)

    total_lands_needed = 40 - len(spells)
    needed_basics = max(0, total_lands_needed - len(non_basic_lands))
    basics = calculate_dynamic_mana_base(
        spells, non_basic_lands, colors, forced_count=needed_basics
    )

    return stack_cards(spells + non_basic_lands + basics)


def get_strict_colors(spells):
    """Determines true deck colors by evaluating strict pip requirements, discarding unneeded hybrid halves."""
    pips = {c: 0 for c in constants.CARD_COLORS}
    hybrid_pips_list = []

    for card in spells:
        cost = card.get("mana_cost", "")
        if not cost:
            for c in card.get("colors", []):
                if c in pips:
                    pips[c] += 1
            continue

        pip_matches = re.findall(r"\{(.*?)\}", cost)
        for pip in pip_matches:
            if any(ch.isdigit() or ch in ["X", "C"] for ch in pip.split("/")):
                continue
            options = [c for c in pip.split("/") if c in constants.CARD_COLORS]
            if not options:
                continue
            if len(options) == 1:
                pips[options[0]] += 1
            else:
                hybrid_pips_list.append(options)

    strict_colors = {c for c, p in pips.items() if p > 0}
    for options in hybrid_pips_list:
        # If a hybrid pip cannot be paid by our strict colors, we must adopt one of its colors
        if not any(opt in strict_colors for opt in options):
            strict_colors.add(options[0])

    sorted_strict = [c for c in constants.CARD_COLORS if c in strict_colors]
    return sorted_strict


def build_variant_soup(pool, metrics):
    """Builds a 'Good Stuff' deck strictly prioritizing global power, but forces fixing into the top 23."""
    candidates = [c for c in pool if "Land" not in c.get("types", [])]

    def soup_rating(card):
        base = get_card_rating(card, ["All Decks"], metrics)
        tags = card.get("tags", [])
        text = str(card.get("text", "")).lower()
        name = str(card.get("name", "")).lower()

        is_fixer = "fixing_ramp" in tags or any(
            fn in name for fn in constants.FIXING_NAMES
        )
        if not is_fixer:
            universal_phrases = [
                "any color",
                "any one color",
                "any type",
                "chosen color",
                "{w}, {u}, {b}, {r}, or {g}",
                "search your library for a basic",
                "create a treasure",
                "treasure token",
                "basic landcycling",
            ]
            if any(phrase in text for phrase in universal_phrases):
                is_fixer = True

        # Massive priority boost for fixers to ensure they aren't cut for random 2-drops
        if is_fixer:
            return base + 5.0

        return base

    candidates.sort(key=soup_rating, reverse=True)
    spells = candidates[:23]

    if not spells:
        return None, []

    soup_colors = get_strict_colors(spells)
    if not soup_colors:
        soup_colors = ["W", "U", "B", "R", "G"]

    non_basic_lands = select_useful_lands(pool, soup_colors)

    total_lands_needed = 40 - len(spells)
    needed_basics = max(0, total_lands_needed - len(non_basic_lands))
    basics = calculate_dynamic_mana_base(
        spells, non_basic_lands, soup_colors, forced_count=needed_basics
    )

    return stack_cards(spells + non_basic_lands + basics), soup_colors


# --- UTILITIES ---


def select_useful_lands(pool, target_colors):
    useful_lands = []
    for card in pool:
        name = card.get("name", "")
        types = card.get("types", [])

        # Explicitly reject true basic lands that might be missing internal tags
        if name in constants.BASIC_LANDS:
            continue

        if "Land" not in types or "Basic" in types:
            continue

        text = str(card.get("text", "")).lower()
        card_colors = card.get("colors", [])

        is_universal = False
        universal_phrases = [
            "any color",
            "any one color",
            "any type",
            "chosen color",
            "{w}, {u}, {b}, {r}, or {g}",
            "search your library for a basic",
        ]
        if any(phrase in text for phrase in universal_phrases) or any(
            fn in name.lower() for fn in constants.FIXING_NAMES
        ):
            useful_lands.append(card)
        # To prevent useless tap-lands, a dual land MUST have ALL its colors in our strict target colors
        elif card_colors and all(c in target_colors for c in card_colors):
            useful_lands.append(card)

    return useful_lands


def calculate_dynamic_mana_base(spells, non_basic_lands, colors, forced_count=17):
    """
    Pro-Tour Caliber Mana Base algorithm.
    1. Calculates Exact Pip Requirements (Frank Karsten math).
    2. Identifies Core vs Splash colors based on Pip Volume and Early Curve.
    3. Analyzes existing dual lands and universal fixers (Treasure, Any-Color Dorks).
    4. Prioritizes fixing the exact deficits for all colors.
    5. Fills remaining slots with primary colors.
    """
    if forced_count <= 0:
        return []

    strict_pips = {c: 0 for c in constants.CARD_COLORS}
    max_pip_in_single_card = {c: 0 for c in constants.CARD_COLORS}
    lowest_cmc = {c: 99 for c in constants.CARD_COLORS}
    hybrid_pips = []

    analyzer = ManaSourceAnalyzer(spells + non_basic_lands)
    existing_sources = analyzer.sources
    any_color = analyzer.any_color_sources
    any_color_enabler_pips = analyzer.any_color_enabler_pips

    for card in spells:
        cost = card.get("mana_cost", "")
        raw_cmc = card.get("cmc")
        cmc = int(raw_cmc) if raw_cmc is not None else 99

        if cost:
            pips = re.findall(r"\{(.*?)\}", cost)
            card_color_pips = {c: 0 for c in constants.CARD_COLORS}
            for pip in pips:
                opts = pip.split("/")
                if any(opt.isdigit() or opt in ["X", "C"] for opt in opts):
                    continue

                valid_opts = [
                    opt
                    for opt in opts
                    if opt in constants.CARD_COLORS and opt in colors
                ]
                if not valid_opts:
                    valid_opts = [opt for opt in opts if opt in constants.CARD_COLORS]

                if len(valid_opts) == 1:
                    card_color_pips[valid_opts[0]] += 1
                elif len(valid_opts) > 1:
                    hybrid_pips.append((valid_opts, cmc))

            for c, count in card_color_pips.items():
                if count > 0:
                    strict_pips[c] += count
                    if count > max_pip_in_single_card[c]:
                        max_pip_in_single_card[c] = count
                    if cmc < lowest_cmc[c]:
                        lowest_cmc[c] = cmc
        else:
            for c in card.get("colors", []):
                if c in colors:
                    strict_pips[c] += 1
                    if 1 > max_pip_in_single_card[c]:
                        max_pip_in_single_card[c] = 1
                    if cmc < lowest_cmc[c]:
                        lowest_cmc[c] = cmc

    # Resolve Hybrid Pips intelligently towards core colors
    for opts, cmc in hybrid_pips:
        valid_opts = [opt for opt in opts if opt in colors]
        if not valid_opts:
            valid_opts = opts
        best_opt = max(valid_opts, key=lambda o: strict_pips[o])
        strict_pips[best_opt] += 1
        if 1 > max_pip_in_single_card[best_opt]:
            max_pip_in_single_card[best_opt] = 1
        if cmc < lowest_cmc[best_opt]:
            lowest_cmc[best_opt] = cmc

    active_colors = [c for c in colors if strict_pips[c] > 0]

    if not active_colors:
        active_colors = [c for c in colors]
        if not active_colors:
            active_colors = ["W", "U", "B", "R", "G"]

    sorted_active = sorted(active_colors, key=lambda c: strict_pips[c], reverse=True)

    targets = {}
    for c in sorted_active:
        pips = strict_pips.get(c, 0)
        max_pip = max_pip_in_single_card.get(c, 0)

        if max_pip >= 3:
            target = 9
        elif max_pip == 2:
            if pips <= 3:
                target = 6
            elif pips <= 5:
                target = 7
            else:
                target = 8
        else:
            if pips == 0:
                target = 0
            elif pips == 1:
                target = 3
            elif pips <= 3:
                target = 4
            elif pips <= 5:
                target = 5
            elif pips <= 8:
                target = 7
            else:
                target = 8

        if lowest_cmc.get(c, 99) <= 1 and target > 0:
            target = max(target, 8)
        elif lowest_cmc.get(c, 99) == 2 and target > 0:
            target = max(target, 7)

        if any_color_enabler_pips.get(c, 0) > 0:
            target = max(target, 8)

        targets[c] = target

    allocations = {c: 0 for c in sorted_active}

    for c in sorted_active:
        effective_any = max(0, any_color - any_color_enabler_pips.get(c, 0))
        provided = existing_sources.get(c, 0) + effective_any

        deficit = targets[c] - provided

        if c not in sorted_active[:2]:
            if max_pip >= 2:
                max_basics = 4
            else:
                max_basics = 2
            allocations[c] = max(0, min(deficit, max_basics))
        else:
            allocations[c] = max(0, deficit)

    total_allocated = sum(allocations.values())

    if total_allocated > forced_count:
        diff = total_allocated - forced_count
        trim_order = list(reversed(sorted_active))

        while diff > 0:
            for c in trim_order:
                if allocations[c] > 0 and diff > 0:
                    if (
                        allocations[c] == 1
                        and c not in sorted_active[:2]
                        and any(allocations[k] > 1 for k in trim_order)
                    ):
                        continue
                    allocations[c] -= 1
                    diff -= 1

    elif total_allocated < forced_count:
        diff = forced_count - total_allocated
        core_colors = sorted_active[:2]

        while diff > 0:
            for c in core_colors:
                if diff > 0:
                    allocations[c] += 1
                    diff -= 1

    lands = []
    for c, count in allocations.items():
        if count > 0:
            lands.extend(create_basic_lands(c, count))

    final_diff = forced_count - len(lands)
    if final_diff > 0:
        fallback_color = sorted_active[0] if sorted_active else "W"
        lands.extend(create_basic_lands(fallback_color, final_diff))

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
        for _ in range(count)
    ]


def is_castable(card, colors, strict=True):
    """
    Determines if a card can be cast natively by the target deck colors.
    """
    card_colors = card.get("colors", [])
    mana_cost = card.get("mana_cost", "")

    if not card_colors:
        return True

    if strict:
        if mana_cost:
            pips = re.findall(r"\{(.*?)\}", mana_cost)
            for pip in pips:
                options = pip.split("/")

                if any(opt.isdigit() or opt in ["X", "C"] for opt in options):
                    continue

                valid_mana_options = [opt for opt in options if opt in "WUBRGP"]

                if not valid_mana_options:
                    continue

                if not any(opt in colors or opt == "P" for opt in valid_mana_options):
                    return False
            return True
        else:
            return all(c in colors for c in card_colors)
    else:
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
        self.any_color_enabler_pips = {c: 0 for c in constants.CARD_COLORS}
        self.total_fixing_cards = 0
        for card in self.pool:
            self._evaluate(card)

    def _evaluate(self, card):
        count = card.get("count", 1)
        types = card.get("types", [])
        text = str(card.get("text", "")).lower()
        name = card.get("name", "").lower()
        card_colors = card.get("colors", [])
        tags = card.get("tags", [])

        is_land = "Land" in types
        is_basic = "Basic" in types

        is_universal = False
        universal_phrases = [
            "any color",
            "any one color",
            "any type",
            "chosen color",
            "{w}, {u}, {b}, {r}, or {g}",
            "search your library for a basic",
            "search your library for a land",
            "create a treasure",
            "treasure token",
            "gold token",
            "basic landcycling",
        ]
        if any(phrase in text for phrase in universal_phrases) or any(
            fn in name for fn in constants.FIXING_NAMES
        ):
            is_universal = True

        # Protect against missing card text in new sets. If it's tagged as a fixer and it's a spell (like a dork or fetch), assume it's universal
        if "fixing_ramp" in tags and not is_land:
            is_universal = True

        if is_universal:
            self.any_color_sources += count
            self.total_fixing_cards += count
            for c in card_colors:
                if c in self.any_color_enabler_pips:
                    self.any_color_enabler_pips[c] += count
            return

        if is_land and not is_basic:
            # Colorless fetching lands without text (e.g., Evolving Wilds in an incomplete dataset)
            if not card_colors and "fixing_ramp" in tags:
                self.any_color_sources += count
                self.total_fixing_cards += count
                return

            for c in card_colors:
                if c in self.sources:
                    self.sources[c] += count
            if len(card_colors) > 1 or "fixing_ramp" in tags:
                self.total_fixing_cards += count


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


def format_win_rate(val, color, field, metrics, result_format):
    """Converts raw winrate to Grade (A+) or Rating (0-5.0) based on set metrics."""
    from src import constants

    if val == 0.0 or val == "-":
        return "-"

    # If format is percentage or the field isn't a win rate (like ALSA), just return the number
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
                # Strip trailing spaces used for sorting (e.g. "A " -> "A")
                return grade.strip()
        return "F"

    elif result_format == constants.RESULT_FORMAT_RATING:
        upper = mean + (2.0 * std)
        lower = mean - (1.67 * std)
        if upper == lower:
            return "2.5"
        rating = ((val - lower) / (upper - lower)) * 5.0
        return f"{max(0.0, min(5.0, rating)):.1f}"

    return f"{val:.1f}" if isinstance(val, float) else str(val)

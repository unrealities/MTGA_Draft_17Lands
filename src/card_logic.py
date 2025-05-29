"""This module contains the functions that are used for processing the collected cards"""
from itertools import combinations
from dataclasses import dataclass, field
import logging
import math
import copy
import numpy
from src import constants
from src.logger import create_logger

logger = create_logger()

@dataclass
class DeckMetrics:
    cmc_average: float = 0.0
    creature_count: int = 0
    noncreature_count: int = 0
    total_cards: int = 0
    total_non_land_cards: int = 0
    distribution_creatures: list = field(
        default_factory=lambda: [0, 0, 0, 0, 0, 0, 0])
    distribution_noncreatures: list = field(
        default_factory=lambda: [0, 0, 0, 0, 0, 0, 0])
    distribution_all: list = field(
        default_factory=lambda: [0, 0, 0, 0, 0, 0, 0])

class CardResult:
    """This class processes a card list and produces results based on a list of fields (i.e., ALSA, GIHWR, COLORS, etc.)"""

    def __init__(self, set_metrics, tier_data, configuration, pick_number):
        self.metrics = set_metrics
        self.tier_data = tier_data
        self.configuration = configuration
        self.pick_number = pick_number

    def return_results(self, card_list, colors, fields):
        """This function processes a card list and returns a list with the requested field results"""
        return_list = []
        wheel_sum = 0
        if constants.DATA_FIELD_WHEEL in fields:
            wheel_sum = self.__retrieve_wheel_sum(card_list)

        for card in card_list:
            try:
                selected_card = copy.deepcopy(card)
                selected_card["results"] = ["NA"] * len(fields)

                for count, option in enumerate(fields):
                    if constants.FILTER_OPTION_TIER in option:
                        selected_card["results"][count] = self.__process_tier(
                            card, option)
                    elif option == constants.DATA_FIELD_COLORS:
                        selected_card["results"][count] = self.__process_colors(
                            card)
                    elif option == constants.DATA_FIELD_WHEEL:
                        selected_card["results"][count] = self.__process_wheel_normalized(
                            card, wheel_sum)
                    elif option in card:
                        selected_card["results"][count] = card[option]
                    else:
                        selected_card["results"][count] = self.__process_filter_fields(
                            card, option, colors)

                return_list.append(selected_card)
            except Exception as error:
                logger.error(error)
        return return_list

    def __process_tier(self, card, option):
        """Retrieve tier list rating for this card"""
        result = "NA"
        try:
            card_name = card[constants.DATA_FIELD_NAME].replace('///', '//')
            if card_name in self.tier_data[option].ratings:
                tier_data = self.tier_data[option].ratings[card_name]
                result = tier_data.rating
                # Append an asterisk to denote a comment
                result = "*" + result if tier_data.comment else result
        except Exception as error:
            logger.error(error)

        return result

    def __process_colors(self, card):
        """Retrieve card colors based on color identity (includes kicker, abilities, etc.) or mana cost"""
        try:
            # Use color identity if enabled or handle lands (mana cost cannot determine colors)
            if self.configuration.settings.color_identity_enabled or constants.CARD_TYPE_LAND in card[constants.DATA_FIELD_TYPES]:
                return "".join(sorted(
                    card[constants.DATA_FIELD_COLORS],
                    key=constants.CARD_COLORS.index
                ))

            # Fallback: determine colors based on mana cost
            return "".join(get_card_colors(card[constants.DATA_FIELD_MANA_COST]).keys())
        
        except Exception as error:
            logger.error(error)
            return "NA"

    def __retrieve_wheel_sum(self, card_list):
        """Calculate the sum of all wheel percentage values for the card list"""
        total_sum = 0

        for card in card_list:
            total_sum += self.__process_wheel(card)

        return total_sum

    def __process_wheel(self, card):
        """Calculate wheel percentage"""
        result = constants.RESULT_UNKNOWN_VALUE

        try:
            # TODO: Adjust this if pack is a play booster and/or contains basic lands
            # Only calculate if there is a possibility that you may see playable cards from this pack again
            if self.pick_number <= len(constants.WHEEL_COEFFICIENTS):
                # 0 is treated as pick 1 for PremierDraft P1P1
                self.pick_number = max(self.pick_number, 1)
                alsa = card[constants.DATA_FIELD_DECK_COLORS][constants.FILTER_OPTION_ALL_DECKS][constants.DATA_FIELD_ALSA]
                
                # TODO: How are these coefficients derived/useful?
                coefficients = constants.WHEEL_COEFFICIENTS[self.pick_number - 1]
                # Exclude ALSA values below 2. These should not be assumed to wheel
                result = round(numpy.polyval(coefficients, alsa),
                               1) if alsa >= 2 else constants.RESULT_UNKNOWN_VALUE
                result = max(result, constants.RESULT_UNKNOWN_VALUE)
        except Exception as error:
            logger.error(error)

        return result

    def __process_wheel_normalized(self, card, total_sum):
        """Calculate the normalized wheel percentage using the sum of all percentages within the card list"""
        result = constants.RESULT_UNKNOWN_VALUE

        try:
            result = self.__process_wheel(card)

            result = round((result / total_sum)*100, 1) if total_sum > 0 else 0
        except Exception as error:
            logger.error(error)

        return result

    def __process_filter_fields(self, card, option, colors):
        """Retrieve win rate result based on the application settings"""
        result = "NA"

        try:
            rated_colors = []
            for color in colors:
                if constants.DATA_FIELD_DECK_COLORS in card \
                        and color in card[constants.DATA_FIELD_DECK_COLORS] \
                        and option in card[constants.DATA_FIELD_DECK_COLORS][color]:
                    if option in constants.WIN_RATE_OPTIONS:
                        rating_data = self.__format_win_rate(card,
                                                             option,
                                                             constants.WIN_RATE_FIELDS_DICT[option],
                                                             color)
                        rated_colors.append(rating_data)
                    else:  # Field that's not a win rate (ALSA, IWD, etc)
                        result = card[constants.DATA_FIELD_DECK_COLORS][color][option]
                        result = constants.RESULT_UNKNOWN_STRING if result == 0.0 else result
            if rated_colors:
                result = sorted(
                    rated_colors, key=field_process_sort, reverse=True)[0]
        except Exception as error:
            logger.error(error)

        return result

    def __format_win_rate(self, card, winrate_field, winrate_count, color):
        """The function will return a grade, rating, or win rate depending on the application's Result Format setting"""
        result = 0
        # Produce a result that matches the Result Format setting
        if self.configuration.settings.result_format == constants.RESULT_FORMAT_RATING:
            result = self.__card_rating(
                card, winrate_field, winrate_count, color)
        elif self.configuration.settings.result_format == constants.RESULT_FORMAT_GRADE:
            result = self.__card_grade(
                card, winrate_field, winrate_count, color)
        else:
            result = card[constants.DATA_FIELD_DECK_COLORS][color][winrate_field]
        result = constants.RESULT_UNKNOWN_STRING if result == constants.RESULT_UNKNOWN_VALUE else result

        return result

    def __card_rating(self, card, winrate_field, winrate_count, color):
        """The function will take a card's win rate and calculate a 5-point rating"""
        result = constants.RESULT_UNKNOWN_VALUE
        try:
            winrate = card[constants.DATA_FIELD_DECK_COLORS][color][winrate_field]

            mean, std = self.metrics.get_metrics(color, winrate_field)
            deviation_list = list(constants.GRADE_DEVIATION_DICT.values())
            upper_limit = mean + \
                std * deviation_list[0]
            lower_limit = mean + \
                std * deviation_list[-1]

            if (winrate != 0) and (upper_limit != lower_limit):
                result = round(
                    ((winrate - lower_limit) / (upper_limit - lower_limit)) * 5.0, 1)
                result = min(result, 5.0)
                result = max(result, 0.1)

        except Exception as error:
            logger.error(error)
        return result

    def __card_grade(self, card, winrate_field, winrate_count, color):
        """The function will take a card's win rate and assign a letter grade based on the number of standard deviations from the mean"""
        result = constants.LETTER_GRADE_NA
        try:
            winrate = card[constants.DATA_FIELD_DECK_COLORS][color][winrate_field]
            
            mean, std = self.metrics.get_metrics(color, winrate_field)
            if ((winrate != 0) and (std != 0)):
                result = constants.LETTER_GRADE_F
                for grade, deviation in constants.GRADE_DEVIATION_DICT.items():
                    standard_score = (winrate - mean) / std
                    if standard_score >= deviation:
                        result = grade
                        break

        except Exception as error:
            logger.error(error)
        return result

def field_process_sort(field_value):
    """This function collects the numeric order of a letter grade for the purpose of sorting"""
    processed_value = field_value

    try:
        # Remove the tier asterisks before sorting
        if isinstance(field_value, str):
            field_value = field_value.replace('*', '')
        if field_value in constants.GRADE_ORDER_DICT:
            processed_value = constants.GRADE_ORDER_DICT[field_value]
        elif field_value == constants.RESULT_UNKNOWN_STRING:
            processed_value = constants.RESULT_UNKNOWN_VALUE
    except ValueError:
        pass
    return processed_value


def format_tier_results(value, old_format, new_format):
    """This function converts the tier list ratings, from old tier lists, back to letter grades"""
    new_value = value
    try:
        # ratings to grades
        if (old_format == constants.RESULT_FORMAT_RATING) and (new_format == constants.RESULT_FORMAT_GRADE):
            new_value = constants.LETTER_GRADE_NA
            for grade, threshold in constants.TIER_CONVERSION_RATINGS_GRADES_DICT.items():
                if value > threshold:
                    new_value = grade
                    break
    except Exception as error:
        logger.error(error)

    return new_value


def deck_card_search(deck, search_colors, card_types, include_types, include_colorless, include_partial):
    """This function retrieves a subset of cards that meet certain criteria (type, color, etc.)"""
    card_color_sorted = {}
    main_color = ""
    combined_cards = []
    for card in deck:
        try:
            colors = list(get_card_colors(
                card[constants.DATA_FIELD_MANA_COST]).keys())

            if constants.CARD_TYPE_LAND in card[constants.DATA_FIELD_TYPES]:
                colors = card[constants.DATA_FIELD_COLORS]

            if colors and (set(colors) <= set(search_colors)):
                main_color = colors[0]

                if ((include_types and any(x in card[constants.DATA_FIELD_TYPES] for x in card_types)) or
                   (not include_types and not any(x in card[constants.DATA_FIELD_TYPES] for x in card_types))):

                    if main_color not in card_color_sorted:
                        card_color_sorted[main_color] = []

                    card_color_sorted[main_color].append(card)

            elif set(search_colors).intersection(colors) and include_partial:
                for color in colors:
                    if ((include_types and any(x in card[constants.DATA_FIELD_TYPES] for x in card_types)) or
                       (not include_types and not any(x in card[constants.DATA_FIELD_TYPES] for x in card_types))):

                        if color not in card_color_sorted:
                            card_color_sorted[color] = []

                        card_color_sorted[color].append(card)

            if not colors and include_colorless:

                if ((include_types and any(x in card[constants.DATA_FIELD_TYPES] for x in card_types)) or
                   (not include_types and not any(x in card[constants.DATA_FIELD_TYPES] for x in card_types))):

                    combined_cards.append(card)
        except Exception as error:
            logger.error(error)

    for key, value in card_color_sorted.items():
        if key in search_colors:
            combined_cards.extend(value)

    return combined_cards


def get_deck_metrics(deck):
    """This function determines the total CMC, count, and distribution of a collection of cards"""
    metrics = DeckMetrics()
    cmc_total = 0
    try:

        metrics.total_cards = len(deck)

        for card in deck:
            if any(x in [constants.CARD_TYPE_CREATURE]
                   for x in card[constants.DATA_FIELD_TYPES]):
                metrics.creature_count += 1
                metrics.total_non_land_cards += 1
                cmc_total += card[constants.DATA_FIELD_CMC]

                index = int(
                    min(card[constants.DATA_FIELD_CMC],
                        len(metrics.distribution_creatures) - 1))
                metrics.distribution_creatures[index] += 1
            else:
                if constants.CARD_TYPE_LAND not in card[constants.DATA_FIELD_TYPES]:
                    cmc_total += card[constants.DATA_FIELD_CMC]
                    metrics.total_non_land_cards += 1
                    index = int(
                        min(card[constants.DATA_FIELD_CMC],
                            len(metrics.distribution_noncreatures) - 1))
                    metrics.distribution_noncreatures[index] += 1
                metrics.noncreature_count += 1

            index = int(
                min(card[constants.DATA_FIELD_CMC],
                    len(metrics.distribution_all) - 1))
            metrics.distribution_all[index] += 1

        metrics.cmc_average = (cmc_total / metrics.total_non_land_cards
                               if metrics.total_non_land_cards
                               else 0.0)

    except Exception as error:
        logger.error(error)

    return metrics


def filter_options(deck, option_selection, metrics, configuration):
    """This function returns a list of colors based on the deck filter option"""
    filtered_color_list = [option_selection]
    try:
        if constants.FILTER_OPTION_AUTO in option_selection:
            filtered_color_list = auto_colors(deck, 5, metrics, configuration)
        else:
            filtered_color_list = [option_selection]
    except Exception as error:
        logger.error(error)
    return filtered_color_list


def deck_colors(deck, colors_max, metrics, configuration):
    """This function determines the prominent colors for a collection of cards"""
    colors_result = {}
    try:
        mean, std = metrics.get_metrics(constants.FILTER_OPTION_ALL_DECKS, constants.DATA_FIELD_GIHWR)
        threshold = mean - 0.33 * std
        colors = calculate_color_affinity(
            deck, constants.FILTER_OPTION_ALL_DECKS, threshold, configuration)

        # Modify the dictionary to include ratings
        color_list = list(
            map((lambda x: {"color": x, "rating": colors[x]}), colors.keys()))

        # Sort the list by decreasing ratings
        color_list = sorted(
            color_list, key=lambda k: k["rating"], reverse=True)

        # Remove extra colors beyond limit
        color_list = color_list[0:colors_max]

        # Return colors
        sorted_colors = list(map((lambda x: x["color"]), color_list))

        # Create color permutation
        color_combination = []

        for count in range(colors_max + 1):
            if count > 1:
                color_combination.extend(combinations(sorted_colors, count))
            else:
                color_combination.extend((sorted_colors))

        # Convert tuples to list of strings
        color_strings = [''.join(tups) for tups in color_combination]
        color_strings = [x for x in color_strings if len(x) <= colors_max]

        color_strings = list(set(color_strings))

        color_dict = {}
        for color_string in color_strings:
            for color in color_string:
                if color_string not in color_dict:
                    color_dict[color_string] = 0
                color_dict[color_string] += colors[color]

        for color_option in constants.DECK_COLORS:
            for key, value in color_dict.items():
                if (len(key) == len(color_option)) and set(key).issubset(color_option):
                    colors_result[color_option] = value

        # Recalculate values based on the filtered win rates
        for color in colors_result:
            base_rating = calculate_color_rating(deck,
                                                 color,
                                                 threshold,
                                                 configuration)
            curve_factor = calculate_curve_factor(deck,
                                                  color,
                                                  configuration)
            colors_result[color] = base_rating * curve_factor

        # Add All Decks as a baseline
        colors_result[constants.FILTER_OPTION_ALL_DECKS] = calculate_color_rating(deck,
                                                                                  constants.FILTER_OPTION_ALL_DECKS,
                                                                                  mean,
                                                                                  configuration)
        colors_result = dict(
            sorted(colors_result.items(), key=lambda item: item[1], reverse=True))
    except Exception as error:
        logger.error(error)

    return colors_result


def auto_colors(deck, colors_max, metrics, configuration):
    """When the Auto deck filter is selected, this function identifies the prominent color pairs from the collected cards"""
    try:
        deck_colors_list = [constants.FILTER_OPTION_ALL_DECKS]
        colors_dict = {}
        deck_length = len(deck)
        if deck_length > 15:
            colors_dict = deck_colors(deck, colors_max, metrics, configuration)
            colors = list(colors_dict.keys())
            auto_select_threshold = max(70 - deck_length, 25)
            if len(colors) >= 2:
                if (colors_dict[colors[0]] - colors_dict[colors[1]]) > auto_select_threshold:
                    deck_colors_list = colors[0:1]
                elif configuration.settings.auto_highest_enabled:
                    deck_colors_list = colors[0:2]

    except Exception as error:
        logger.error(error)

    return deck_colors_list


def calculate_color_rating(cards, color_filter, threshold, configuration):
    """This function identifies the main deck colors based on the GIHWR of the collected cards"""
    rating = 0

    for card in cards:
        try:
            if color_filter in card[constants.DATA_FIELD_DECK_COLORS]:
                gihwr = card[constants.DATA_FIELD_DECK_COLORS][color_filter][constants.DATA_FIELD_GIHWR]
                if gihwr > threshold:
                    rating += gihwr - threshold
        except Exception as error:
            logger.error(error)
    return rating


def sort_cards_win_rate(cards, filter_order):
    """This function will acquire a non-zero win rate for each card and sort the cards by the win rate (highest to lowest)"""
    for card in cards:
        card["results"] = [0]
        try:
            for color_filter in filter_order:
                win_rate = card[constants.DATA_FIELD_DECK_COLORS][color_filter][constants.DATA_FIELD_GIHWR]
                if win_rate:
                    card["results"] = [win_rate]
                    break

        except Exception as error:
            logger.error(error)

    sorted_cards = sorted(
        cards, key=lambda k: k["results"][0], reverse=True)

    return sorted_cards


def calculate_curve_factor(deck, color_filter, configuration):
    """This function will assign a rating to a collection of cards based on how well they meet the deck building requirements"""
    curve_levels = [.10, .10, .10, .10, .15,
                    .15, .15, .20, .20, .20,
                    .25, .25, .25, .30, .30,
                    .30, .30, .40, .40, .40]

    curve_start = 15
    pick_number = len(deck)
    index = max(pick_number - curve_start, 0)
    curve_level = 0.0
    curve_factor = 0.0
    base_curve_factor = 1.0
    minimum_creature_count = configuration.card_logic.minimum_creatures

    try:
        filtered_cards = deck_card_search(
            deck,
            color_filter,
            constants.CARD_TYPE_DICT[constants.CARD_TYPE_SELECTION_NON_LANDS][0],
            True,
            True,
            False)
        deck_info = get_deck_metrics(filtered_cards)
        curve_level = curve_levels[int(
            min(index, len(curve_levels) - 1))]

        if deck_info.total_cards < configuration.card_logic.deck_control.maximum_card_count:
            curve_factor -= ((configuration.card_logic.deck_control.maximum_card_count - deck_info.creature_count)
                             / configuration.card_logic.deck_control.maximum_card_count) * curve_level
        elif deck_info.creature_count < minimum_creature_count:
            curve_factor = (deck_info.creature_count
                            / minimum_creature_count) * curve_level
        else:
            curve_factor = curve_level

    except Exception as error:
        logger.error(error)

    return base_curve_factor + curve_factor


def calculate_color_affinity(deck_cards, color_filter, threshold, configuration):
    """This function identifies the main deck colors based on the GIHWR of the collected cards"""
    colors = {}

    for card in deck_cards:
        try:
            if color_filter in card[constants.DATA_FIELD_DECK_COLORS]:
                gihwr = card[constants.DATA_FIELD_DECK_COLORS][color_filter][constants.DATA_FIELD_GIHWR]
                if gihwr > threshold:
                    mana_colors = get_card_colors(card[constants.DATA_FIELD_MANA_COST])
                    for color in mana_colors:
                        if color not in colors:
                            colors[color] = 0
                        colors[color] += (gihwr - threshold)
        except Exception as error:
            logger.error(error)
    return colors


def row_color_tag(mana_cost):
    """This function selects the color tag for a table row based on a card's mana cost"""
    colors = list(get_card_colors(mana_cost).keys())

    row_tag = constants.CARD_ROW_COLOR_COLORLESS_TAG
    if len(colors) > 1:
        row_tag = constants.CARD_ROW_COLOR_GOLD_TAG
    elif constants.CARD_COLOR_SYMBOL_RED in colors:
        row_tag = constants.CARD_ROW_COLOR_RED_TAG
    elif constants.CARD_COLOR_SYMBOL_BLUE in colors:
        row_tag = constants.CARD_ROW_COLOR_BLUE_TAG
    elif constants.CARD_COLOR_SYMBOL_BLACK in colors:
        row_tag = constants.CARD_ROW_COLOR_BLACK_TAG
    elif constants.CARD_COLOR_SYMBOL_WHITE in colors:
        row_tag = constants.CARD_ROW_COLOR_WHITE_TAG
    elif constants.CARD_COLOR_SYMBOL_GREEN in colors:
        row_tag = constants.CARD_ROW_COLOR_GREEN_TAG
    return row_tag

def ratings_limits(cards):
    """The function identifies the upper and lower win rates from a collection of cards"""
    upper_limit = 0
    lower_limit = 100

    for card in cards:
        for color in constants.DECK_COLORS:
            try:
                if color in cards[card][constants.DATA_FIELD_DECK_COLORS]:
                    gihwr = cards[card][constants.DATA_FIELD_DECK_COLORS][color][constants.DATA_FIELD_GIHWR]
                    if gihwr > upper_limit:
                        upper_limit = gihwr
                    if gihwr < lower_limit and gihwr != 0:
                        lower_limit = gihwr
            except Exception as error:
                logger.error(error)

    return upper_limit, lower_limit

def deck_color_stats(deck, color):
    """The function will identify the number of creature and noncreature cards in a collection of cards"""
    creature_count = 0
    noncreature_count = 0

    try:
        creature_cards = deck_card_search(
            deck, color, [constants.CARD_TYPE_CREATURE], True, True, False)
        noncreature_cards = deck_card_search(
            deck, color, [constants.CARD_TYPE_CREATURE], False, True, False)
        noncreature_cards = deck_card_search(
            noncreature_cards, color,
            [constants.CARD_TYPE_INSTANT,
             constants.CARD_TYPE_SORCERY,
             constants.CARD_TYPE_ARTIFACT,
             constants.CARD_TYPE_ENCHANTMENT,
             constants.CARD_TYPE_PLANESWALKER], True, True, False)

        creature_count = len(creature_cards)
        noncreature_count = len(noncreature_cards)

    except Exception as error:
        logger.error(error)

    return creature_count, noncreature_count


def card_cmc_search(deck, offset, starting_cmc, cmc_limit, remaining_count):
    """The function will use recursion to search through a collection of cards and produce a list of cards with a mean CMC that is below a specific limit"""
    cards = []
    unused = []
    try:
        for count, card in enumerate(deck[offset:]):
            card_cmc = card[constants.DATA_FIELD_CMC]

            if card_cmc + starting_cmc <= cmc_limit:
                card_cmc += starting_cmc
                current_offset = offset + count
                current_remaining = int(max(remaining_count - 1, 0))
                if current_remaining == 0:
                    cards.append(card)
                    unused.extend(deck[current_offset + 1:])
                    break
                elif current_offset > (len(deck) - remaining_count):
                    unused.extend(deck[current_offset:])
                    break
                else:
                    current_offset += 1
                    cards, skipped = card_cmc_search(
                        deck, current_offset, card_cmc, cmc_limit, current_remaining)
                    if cards:
                        cards.append(card)
                        unused.extend(skipped)
                        break
                    else:
                        unused.append(card)
            else:
                unused.append(card)
    except Exception as error:
        logger.error(error)

    return cards, unused


def deck_rating(deck, deck_type, color, threshold):
    """The function will produce a deck rating based on the combined GIHWR value for each card with a GIHWR value above a certain threshold"""
    rating = 0
    try:
        # Combined GIHWR of the cards
        for card in deck:
            try:
                gihwr = card[constants.DATA_FIELD_DECK_COLORS][color][constants.DATA_FIELD_GIHWR]
                if gihwr > threshold:
                    rating += gihwr
            except Exception:
                pass

        # Deck contains the recommended number of creatures
        recommended_creature_count = deck_type.recommended_creature_count
        filtered_cards = deck_card_search(
            deck, color, [constants.CARD_TYPE_CREATURE], True, True, False)

        if len(filtered_cards) < recommended_creature_count:
            rating -= (recommended_creature_count - len(filtered_cards)) * 10

        # Average CMC of the creatures is below the ideal cmc average
        cmc_average = deck_type.cmc_average
        total_cards = len(filtered_cards)
        total_cmc = 0

        for card in filtered_cards:
            total_cmc += card[constants.DATA_FIELD_CMC]

        cmc = total_cmc / total_cards

        if cmc > cmc_average:
            rating -= 50

        # Cards fit distribution
        minimum_distribution = deck_type.distribution
        distribution = [0, 0, 0, 0, 0, 0, 0]
        for card in filtered_cards:
            index = int(min(card[constants.DATA_FIELD_CMC],
                        len(minimum_distribution) - 1))
            distribution[index] += 1

    except Exception as error:
        logger.error(error)

    rating = int(rating)

    return rating


def copy_deck(deck, sideboard):
    """The function will produce a deck/sideboard list that is formatted in such a way that it can be copied to Arena and Sealdeck.tech"""
    deck_copy = ""
    try:
        # Copy Deck
        deck_copy = "Deck\n"
        # identify the arena_id for the cards
        for card in deck:
            deck_copy += f"{card[constants.DATA_FIELD_COUNT]} {card[constants.DATA_FIELD_NAME]}\n"

        # Copy sideboard
        if sideboard is not None:
            deck_copy += "\nSideboard\n"
            for card in sideboard:
                deck_copy += f"{card[constants.DATA_FIELD_COUNT]} {card[constants.DATA_FIELD_NAME]}\n"

    except Exception as error:
        logger.error(error)

    return deck_copy


def stack_cards(cards):
    """The function will produce a list consisting of unique cards and the number of copies of each card"""
    deck = {}
    deck_list = []
    for card in cards:
        try:
            name = card[constants.DATA_FIELD_NAME]
            if name not in deck:
                deck[name] = {constants.DATA_FIELD_COUNT: 1}
                for data_field in constants.DATA_SET_FIELDS:
                    if data_field in card:
                        deck[name][data_field] = card[data_field]
            else:
                deck[name][constants.DATA_FIELD_COUNT] += 1
        except Exception as error:
            logger.error(error)
    # Convert to list format
    deck_list = list(deck.values())

    return deck_list


def get_card_colors(mana_cost):
    """The function parses a mana cost string and returns a list of mana symbols"""
    colors = {}
    try:
        for color in constants.CARD_COLORS:
            if color in mana_cost:
                if color not in colors:
                    colors[color] = 1
                else:
                    colors[color] += 1

    except Exception as error:
        logger.error(error)
    return colors


def color_splash(cards, colors, splash_threshold, configuration):
    """The function will parse a list of cards to determine if there are any cards that might justify a splash"""
    color_affinity = {}
    splash_color = ""
    try:
        # Calculate affinity to rank colors based on splash threshold (minimum GIHWR)
        color_affinity = calculate_color_affinity(
            cards, colors, splash_threshold, configuration)

        # Modify the dictionary to include ratings
        color_affinity = list(
            map((lambda x: {"color": x, "rating": color_affinity[x]}), color_affinity.keys()))
        # Remove the current colors
        filtered_colors = color_affinity[:]
        for color in color_affinity:
            if color["color"] in colors:
                filtered_colors.remove(color)
        # Sort the list by decreasing ratings
        filtered_colors = sorted(
            filtered_colors, key=lambda k: k["rating"], reverse=True)

        if filtered_colors:
            splash_color = filtered_colors[0]["color"]
    except Exception as error:
        logger.error(error)
    return splash_color


def mana_base(deck):
    """The function will identify the number of lands that are needed to fill out a deck"""
    maximum_deck_size = 40
    combined_deck = []
    mana_types = {"Swamp": {"color": constants.CARD_COLOR_SYMBOL_BLACK, constants.DATA_FIELD_COUNT: 0},
                  "Forest": {"color": constants.CARD_COLOR_SYMBOL_GREEN, constants.DATA_FIELD_COUNT: 0},
                  "Mountain": {"color": constants.CARD_COLOR_SYMBOL_RED, constants.DATA_FIELD_COUNT: 0},
                  "Island": {"color": constants.CARD_COLOR_SYMBOL_BLUE, constants.DATA_FIELD_COUNT: 0},
                  "Plains": {"color": constants.CARD_COLOR_SYMBOL_WHITE, constants.DATA_FIELD_COUNT: 0}}
    total_count = 0
    try:
        number_of_lands = 0 if maximum_deck_size < len(
            deck) else maximum_deck_size - len(deck)

        # Go through the cards and count the mana types
        for card in deck:
            if constants.CARD_TYPE_LAND in card[constants.DATA_FIELD_TYPES]:
                # Subtract symbol for lands
                for mana_type in mana_types.values():
                    mana_type[constants.DATA_FIELD_COUNT] -= (1 if (mana_type["color"] in card[constants.DATA_FIELD_COLORS])
                                                              else 0)
            else:
                # Increase count for abilities that are not part of the mana cost
                mana_count = get_card_colors(card[constants.DATA_FIELD_MANA_COST])
                # for color in card[constants.DATA_FIELD_COLORS]:
                #    mana_count[color] = (
                #        mana_count[color] + 1) if color in mana_count else 1

                for mana_type in mana_types.values():
                    color = mana_type["color"]
                    mana_type[constants.DATA_FIELD_COUNT] += mana_count[color] if color in mana_count else 0

        for land in mana_types.values():
            land[constants.DATA_FIELD_COUNT] = max(
                land[constants.DATA_FIELD_COUNT], 0)
            total_count += land[constants.DATA_FIELD_COUNT]

        # Sort by lowest count
        mana_types = dict(
            sorted(mana_types.items(), key=lambda t: t[1][constants.DATA_FIELD_COUNT]))
        # Add x lands with a distribution set by the mana types
        total_lands = number_of_lands
        for land in mana_types:
            if not total_lands or not mana_types[land][constants.DATA_FIELD_COUNT]:
                continue

            land_count = int(math.ceil(
                (mana_types[land][constants.DATA_FIELD_COUNT] / total_count) * number_of_lands))

            land_count = min(land_count, total_lands)
            total_lands -= land_count

            if land_count:
                card = {constants.DATA_FIELD_COLORS: mana_types[land]["color"],
                        constants.DATA_FIELD_TYPES: constants.CARD_TYPE_LAND,
                        constants.DATA_FIELD_CMC: 0,
                        constants.DATA_FIELD_NAME: land,
                        constants.DATA_FIELD_MANA_COST: mana_types[land]["color"],
                        constants.DATA_FIELD_COUNT: land_count}
                combined_deck.append(card)

    except Exception as error:
        logger.error(error)
    return combined_deck


def suggest_deck(taken_cards, metrics, configuration):
    """The function will analyze the list of taken cards and produce several viable decks based on specific criteria"""
    colors_max = 5
    maximum_card_count = 22
    sorted_decks = {}
    try:
        deck_types = {"Mid": configuration.card_logic.deck_mid,
                      "Aggro": configuration.card_logic.deck_aggro,
                      "Control": configuration.card_logic.deck_control}
        # Identify the top color combinations
        colors = deck_colors(taken_cards, colors_max, metrics, configuration)
        filtered_colors = []

        colors.pop(constants.FILTER_OPTION_ALL_DECKS, None)

        # Collect color stats and remove colors that don't meet the minimum requirements
        for color in colors:
            creature_count, noncreature_count = deck_color_stats(
                taken_cards, color)
            if ((creature_count >= configuration.card_logic.minimum_creatures) and
               (noncreature_count >= configuration.card_logic.minimum_noncreatures) and
               (creature_count + noncreature_count >= maximum_card_count)):
                filtered_colors.append(color)

        decks = {}
        mean, std = metrics.get_metrics(constants.FILTER_OPTION_ALL_DECKS, constants.DATA_FIELD_GIHWR)
        threshold = mean - 0.33 * std
        for color in filtered_colors:
            for key, value in deck_types.items():
                deck, sideboard_cards = build_deck(
                    value, taken_cards, color, metrics, configuration)
                rating = deck_rating(deck, value, color, threshold)
                if rating >= configuration.card_logic.ratings_threshold:

                    if ((color not in decks) or
                            (color in decks and rating > decks[color]["rating"])):
                        decks[color] = {}
                        decks[color]["deck_cards"] = stack_cards(deck)
                        decks[color]["sideboard_cards"] = stack_cards(
                            sideboard_cards)
                        decks[color]["rating"] = rating
                        decks[color]["type"] = key
                        decks[color]["deck_cards"].extend(mana_base(deck))

        sorted_colors = sorted(
            decks, key=lambda x: decks[x]["rating"], reverse=True)
        for color in sorted_colors:
            sorted_decks[color] = decks[color]
    except Exception as error:
        logger.error(error)

    return sorted_decks


def build_deck(deck_type, cards, color, metrics, configuration):
    """The function will build a deck list that meets specific criteria"""
    minimum_distribution = deck_type.distribution
    maximum_card_count = deck_type.maximum_card_count
    maximum_deck_size = 40
    cmc_average = deck_type.cmc_average
    recommended_creature_count = deck_type.recommended_creature_count
    deck_list = []
    unused_creature_list = []
    sideboard_list = cards[:]  # Copy by value
    try:
        for card in cards:
            card["results"] = [card[constants.DATA_FIELD_DECK_COLORS][color][constants.DATA_FIELD_GIHWR]]

        # identify a splashable color
        mean, std = metrics.get_metrics(constants.FILTER_OPTION_ALL_DECKS, constants.DATA_FIELD_GIHWR)
        splash_threshold = mean + 2.33 * std
        color += (color_splash(cards, color, splash_threshold, configuration))

        card_colors_sorted = deck_card_search(
            cards, color, [constants.CARD_TYPE_CREATURE], True, True, False)
        card_colors_sorted = sorted(
            card_colors_sorted, key=lambda k: k["results"][0], reverse=True)

        # Identify creatures that fit distribution
        distribution = [0, 0, 0, 0, 0, 0, 0]
        used_count = 0
        used_cmc_combined = 0
        for card in card_colors_sorted:
            index = int(min(card[constants.DATA_FIELD_CMC],
                        len(minimum_distribution) - 1))
            if distribution[index] < minimum_distribution[index]:
                deck_list.append(card)
                sideboard_list.remove(card)
                distribution[index] += 1
                used_count += 1
                used_cmc_combined += card[constants.DATA_FIELD_CMC]
            else:
                unused_creature_list.append(card)

        # Go back and identify remaining creatures that have the highest base rating but don't push average above the threshold
        unused_cmc_combined = cmc_average * recommended_creature_count - used_cmc_combined

        unused_creature_list.sort(key=lambda x: x["results"][0], reverse=True)

        # Identify remaining cards that won't exceed recommeneded CMC average
        cmc_cards, unused_creature_list = card_cmc_search(
            unused_creature_list, 0, 0, unused_cmc_combined, recommended_creature_count - used_count)

        for card in cmc_cards:
            deck_list.append(card)
            sideboard_list.remove(card)

        total_card_count = len(deck_list)

        if len(cmc_cards) == 0:
            for card in unused_creature_list:
                if total_card_count >= recommended_creature_count:
                    break

                deck_list.append(card)
                sideboard_list.remove(card)
                total_card_count += 1

        card_colors_sorted = deck_card_search(sideboard_list, color, [
            constants.CARD_TYPE_CREATURE,
            constants.CARD_TYPE_INSTANT,
            constants.CARD_TYPE_SORCERY,
            constants.CARD_TYPE_ENCHANTMENT,
            constants.CARD_TYPE_ARTIFACT,
            constants.CARD_TYPE_PLANESWALKER], True, True, False)

        card_colors_sorted = sorted(
            card_colors_sorted, key=lambda k: k["results"][0], reverse=True)

        # Add remaining non-land cards
        for card in card_colors_sorted:
            if total_card_count >= maximum_card_count:
                break

            deck_list.append(card)
            sideboard_list.remove(card)
            total_card_count += 1

        # Add in special lands if they have a win rate that is at least 0.33 standard deviations from the mean (C-)
        land_cards = deck_card_search(
            sideboard_list, color, [constants.CARD_TYPE_LAND], True, True, False)
        land_cards = [
            x for x in land_cards if x[constants.DATA_FIELD_NAME] not in constants.BASIC_LANDS]
        land_cards = sorted(
            land_cards, key=lambda k: k["results"][0], reverse=True)
        for card in land_cards:
            if total_card_count >= maximum_deck_size:
                break

            if card["results"][0] >= mean - 0.33 * std:
                deck_list.append(card)
                sideboard_list.remove(card)
                total_card_count += 1

    except Exception as error:
        logger.error(error)
    return deck_list, sideboard_list

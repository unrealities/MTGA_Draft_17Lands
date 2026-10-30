"""
src/advisor/deck_scorer.py
Evaluates pool strength, calculates holistic power scores, and identifies top lanes.
"""

from math import comb, exp

from src import constants
from src.advisor.mana_base import ManaSourceAnalyzer
from src.utils import normalize_color_string
from src.sealed_logic import HeuristicEvaluator

TIER_TO_GIHWR = {
    "A+": 68.0,
    "A ": 66.0,
    "A-": 64.0,
    "B+": 62.0,
    "B ": 60.0,
    "B-": 58.0,
    "C+": 56.0,
    "C ": 54.0,
    "C-": 52.0,
    "D+": 50.0,
    "D ": 48.0,
    "D-": 46.0,
    "F ": 40.0,
    "SB": 40.0,
    "NA": 0.0,
}


def get_card_rating(card, colors, metrics=None, tier_data=None):
    global_mean = 54.0
    set_has_data = False
    if metrics:
        mean_val, _ = metrics.get_metrics("All Decks", "gihwr")
        if mean_val > 0:
            global_mean = mean_val
            set_has_data = True

    stats = card.get("deck_colors", {})
    global_wr = float(stats.get("All Decks", {}).get("gihwr") or 0.0)

    # Dataset deck_colors keys are WUBRG-ordered ("UB", not "BU").
    arch_key = normalize_color_string(
        "".join(colors) if len(colors) <= 2 else "".join(colors[:2])
    )
    arch_wr = float(stats.get(arch_key, {}).get("gihwr") or 0.0)

    if arch_wr > 30.0 and global_wr > 30.0:
        return (arch_wr * 0.7) + (global_wr * 0.3)
    elif global_wr > 30.0:
        return global_wr
    elif arch_wr > 30.0:
        return arch_wr

    if tier_data:
        name, tier_scores = card.get("name", ""), []
        for tier_obj in tier_data.values():
            if name in tier_obj.ratings:
                grade = tier_obj.ratings[name].rating
                score = TIER_TO_GIHWR.get(grade, 0.0)
                if score > 0.0:
                    tier_scores.append(score)
        if tier_scores:
            return sum(tier_scores) / len(tier_scores)

    # In an established format (the set already has win-rate data), a card with
    # no data of its own is one nobody drafts or plays — effectively unplayable
    # (e.g. Worlds Within Worlds). Don't invent a generous score from a metadata
    # heuristic; that fallback is only for Day 1 before any data exists.
    if set_has_data:
        return 0.0

    return HeuristicEvaluator.evaluate(card)


def identify_top_pairs(pool, metrics, tier_data=None):
    global_mean, global_std = (
        metrics.get_metrics("All Decks", "gihwr") if metrics else (54.0, 4.0)
    )
    if global_mean == 0.0:
        global_mean = 54.0
    if global_std == 0.0:
        global_std = 4.0

    playable_baseline = global_mean - (global_std * 0.5)
    scores = {c: 0.0 for c in constants.CARD_COLORS}

    for card in pool:
        colors = card.get(constants.DATA_FIELD_COLORS, [])
        wr = get_card_rating(card, ["All Decks"], metrics, tier_data)
        if wr > playable_baseline:
            points = (wr - playable_baseline) / global_std
            for c in colors:
                scores[c] += points

    sorted_c = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    if sorted_c[0][1] <= 0.0:
        return []

    top_4_colors = [c[0] for c in sorted_c[:4]]
    from itertools import combinations

    return [list(pair) for pair in combinations(top_4_colors, 2)]


# The deck score is BASE_SCORE plus each feature times its weight. Twelve points
# are one standard deviation of card quality, so the other weights are in the
# same units: what the feature is worth, measured in card quality.
#
# The weights were fit to game results: about 480,000 17Lands Premier Draft
# decks over ten sets, controlling for the player (Tools/DeckScoreFit). Curve,
# evasion and tribal adjustments were fit at about zero once card quality was
# counted, so the score leaves them out.
BASE_SCORE = 75.0
WEIGHTS = {
    # Mean rating of the deck's spells, in standard deviations from the format mean.
    "card_quality": 12.0,
    # 1 if the deck has two colors or fewer.
    "two_colors": 3.5,
    # 1 if a deck of 3+ colors has 2+ domain payoffs and 4+ fixing cards.
    "domain_supported": 3.2,
    # For a deck of 3+ colors that isn't a supported domain deck, fixing cards
    # short of one per color beyond the first. Players rarely build such decks,
    # so game results can't fit it; this is fit instead to which of the deck
    # builder's candidate builds drafters chose (see
    # docs/logs/deck-builder-before-after.md).
    "missing_fixing": -2.5,
    # Spells short of a full deck for the pool size, less one. Not fitted:
    # finished decks are never short.
    "missing_spells": -10.0,
}

# How each feature's adjustment is named in the deck's notes. Card quality is
# the base of the score, so it gets no note.
NOTES = {
    "two_colors": "Rock-Solid Mana",
    "domain_supported": "Supported Domain/Soup",
    "missing_fixing": "Greedy Mana Strain",
    "missing_spells": "Incomplete Deck",
}

# The log-odds of winning a game, for a deck of BASE_SCORE and per point
# above it, fit to the same games (Tools/DeckScoreFit).
WIN_LOG_ODDS_AT_BASE = 0.0364
WIN_LOG_ODDS_PER_POINT = 0.03871


def _text(card):
    return str(card.get("oracle_text", card.get("text", ""))).lower()


def deck_features(deck, colors, pool_size, metrics, tier_data=None):
    """The deck's value for each feature in WEIGHTS, or None if it has no spells."""
    global_mean, global_std = metrics.get_metrics("All Decks", "gihwr")
    if global_mean == 0.0:
        global_mean = 54.0
    if global_std == 0.0:
        global_std = 4.0

    spells = [c for c in deck if constants.CARD_TYPE_LAND not in c.get("types", [])]
    spell_count = sum(c.get("count", 1) for c in spells)
    if spell_count == 0:
        return None
    features = dict.fromkeys(WEIGHTS, 0.0)

    # Dataset deck_colors keys are WUBRG-ordered ("UB", not "BU").
    arch_key = normalize_color_string(
        "".join(colors) if len(colors) <= 2 else "".join(colors[:2])
    )
    valid_ratings = [
        get_card_rating(c, [arch_key], metrics)
        for c in spells
        for _ in range(c.get("count", 1))
        if get_card_rating(c, [arch_key], metrics) > 0.0
    ]
    avg_gihwr = (
        sum(valid_ratings) / len(valid_ratings)
        if valid_ratings
        else global_mean - global_std
    )
    features["card_quality"] = (avg_gihwr - global_mean) / global_std

    if len(colors) <= 2:
        features["two_colors"] = 1.0
    else:
        domain_payoffs = sum(
            c.get("count", 1)
            for c in spells
            if "colors among" in _text(c) or "basic land types" in _text(c)
        )
        fixing_count = ManaSourceAnalyzer(deck).total_fixing_cards

        if domain_payoffs >= 2 and fixing_count >= 4:
            features["domain_supported"] = 1.0
        else:
            features["missing_fixing"] = max(0, len(colors) - 1 - fixing_count)

    expected_spells = int(23 * (min(42, pool_size) / 42.0))
    if spell_count < expected_spells - 1:
        features["missing_spells"] = (expected_spells - 1) - spell_count

    return features


def calculate_holistic_score(deck, colors, pool_size, metrics, tier_data=None):
    if not deck:
        return 0.0, ""
    features = deck_features(deck, colors, pool_size, metrics, tier_data)
    if features is None:
        return 0.0, ""

    power_level = BASE_SCORE
    breakdown_notes = []
    for name, weight in WEIGHTS.items():
        points = weight * features[name]
        power_level += points
        if points and name in NOTES:
            breakdown_notes.append(
                f"{NOTES[name]} ({'+' if points > 0 else '-'}{abs(points):.1f})"
            )

    return max(0.0, power_level), ", ".join(breakdown_notes)


def expected_wins(game_win_rate, max_wins, max_losses):
    """Expected wins in an event that ends at max_wins wins or max_losses losses."""
    p, q = game_win_rate, 1 - game_win_rate
    # Ending on a loss after w wins, for each w short of the cap...
    total = sum(
        w * comb(w + max_losses - 1, w) * p**w * q**max_losses for w in range(max_wins)
    )
    # ...or reaching the cap with fewer than max_losses losses.
    reach = sum(
        comb(max_wins - 1 + losses, losses) * p**max_wins * q**losses
        for losses in range(max_losses)
    )
    return total + max_wins * reach


def estimate_record(power_level, is_bo3=False):
    """Expected wins for a deck of this score, as text.

    Premier Draft (Bo1) runs to 7 wins or 3 losses; Traditional Draft (Bo3)
    is always three matches. The game win rate is that of 17Lands users' decks
    of this score.
    """
    log_odds = WIN_LOG_ODDS_AT_BASE + WIN_LOG_ODDS_PER_POINT * (
        power_level - BASE_SCORE
    )
    p = 1 / (1 + exp(-log_odds))
    if is_bo3:
        match = p * p * (3 - 2 * p)  # two games out of three
        return f"{3 * match:.1f} wins"
    return f"{expected_wins(p, 7, 3):.1f} wins"

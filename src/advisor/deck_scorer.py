"""
src/advisor/deck_scorer.py
Evaluates pool strength, calculates holistic power scores, and identifies top lanes.
"""

from src import constants
from src.card_utils import get_functional_cmc
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
BASE_SCORE = 75.0
WEIGHTS = {
    # Mean rating of the deck's spells, in standard deviations from the format mean.
    "card_quality": 12.0,
    # The mana deficit (5.5 lands per point of average mana value, less lands
    # and ramp), when it is over 1.5.
    "high_curve": -3.0,
    # 1 if the mana deficit is under -1 and the average mana value under 2.8.
    "aggro_curve": 5.0,
    # 1 if the deck has two colors or fewer.
    "two_colors": 2.5,
    # The tribal bonus: half a point per card of the main creature type, and 1.5
    # per payoff, with 6+ cards of the type and 2+ payoffs.
    "tribal_synergy": 1.0,
    # 1 if a deck of 3+ colors has 2+ domain payoffs and 4+ fixing cards.
    "domain_supported": 6.0,
    # Fixing cards short of one per color past the first, in a deck of 3+ colors
    # that isn't a supported domain deck.
    "missing_fixing": -6.0,
    # 1 if the deck has fewer than three evasive spells and an average mana
    # value over 2.5.
    "lacks_evasion": -5.0,
    # Spells short of a full deck for the pool size, less one.
    "missing_spells": -10.0,
}

# How each feature's adjustment is named in the deck's notes. Card quality is
# the base of the score, so it gets no note.
NOTES = {
    "high_curve": "High Curve / Needs Lands",
    "aggro_curve": "Excellent Aggro Curve",
    "two_colors": "Rock-Solid Mana",
    "tribal_synergy": "{tribe} Synergy",
    "domain_supported": "Supported Domain/Soup",
    "missing_fixing": "Greedy Mana Strain",
    "lacks_evasion": "Lacks Evasion/Reach",
    "missing_spells": "Incomplete Deck",
}

SUPERTYPES = {
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

EVASION_WORDS = [
    "flying",
    "trample",
    "menace",
    "can't be blocked",
    "unblockable",
    "deals damage to any target",
]


def _text(card):
    return str(card.get("oracle_text", card.get("text", ""))).lower()


def deck_features(deck, colors, pool_size, metrics, tier_data=None):
    """The deck's value for each feature in WEIGHTS, and its main creature type.

    Returns (None, None) for a deck with no spells.
    """
    global_mean, global_std = metrics.get_metrics("All Decks", "gihwr")
    if global_mean == 0.0:
        global_mean = 54.0
    if global_std == 0.0:
        global_std = 4.0

    spells = [c for c in deck if constants.CARD_TYPE_LAND not in c.get("types", [])]
    spell_count = sum(c.get("count", 1) for c in spells)
    if spell_count == 0:
        return None, None
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

    cmcs = [get_functional_cmc(c) for c in spells for _ in range(c.get("count", 1))]
    avg_cmc = sum(cmcs) / spell_count

    land_count = sum(c.get("count", 1) for c in deck if "Land" in c.get("types", []))
    ramp_count = min(
        3,
        sum(
            c.get("count", 1)
            for c in deck
            if (
                "fixing_ramp" in c.get("tags", [])
                or "treasure" in _text(c)
                or "add {" in _text(c)
                or "adds {" in _text(c)
            )
            and "Land" not in c.get("types", [])
        ),
    )

    mana_deficit = (avg_cmc * 5.5) - (land_count + ramp_count)
    if mana_deficit > 1.5:
        features["high_curve"] = mana_deficit
    elif mana_deficit < -1.0 and avg_cmc < 2.8:
        features["aggro_curve"] = 1.0

    if len(colors) <= 2:
        features["two_colors"] = 1.0

    subtypes, changeling_count, top_tribe = {}, 0, None
    for c in spells:
        count = c.get("count", 1)
        if "changeling" in _text(c):
            changeling_count += count
        for t in c.get("types", []):
            if t not in SUPERTYPES:
                subtypes[t] = subtypes.get(t, 0) + count

    if subtypes:
        top_tribe, tribe_count = max(subtypes.items(), key=lambda x: x[1])
        total_tribe_density = tribe_count + changeling_count
        payoff_count = sum(
            c.get("count", 1)
            for c in spells
            if "chosen type" in _text(c) or top_tribe.lower() in _text(c)
        )
        if total_tribe_density >= 6 and payoff_count >= 2:
            features["tribal_synergy"] = (total_tribe_density * 0.5) + (
                payoff_count * 1.5
            )

    if len(colors) >= 3:
        domain_payoffs = sum(
            c.get("count", 1)
            for c in spells
            if "colors among" in _text(c) or "basic land types" in _text(c)
        )
        fixing_count = ManaSourceAnalyzer(deck).total_fixing_cards

        if domain_payoffs >= 2 and fixing_count >= 4:
            features["domain_supported"] = 1.0
        elif fixing_count < len(colors) - 1:
            features["missing_fixing"] = len(colors) - 1 - fixing_count

    evasion_count = sum(
        c.get("count", 1)
        for c in spells
        if "evasion" in c.get("tags", []) or any(kw in _text(c) for kw in EVASION_WORDS)
    )
    if evasion_count < 3 and avg_cmc > 2.5:
        features["lacks_evasion"] = 1.0

    expected_spells = int(23 * (min(42, pool_size) / 42.0))
    if spell_count < expected_spells - 1:
        features["missing_spells"] = (expected_spells - 1) - spell_count

    return features, top_tribe


def calculate_holistic_score(deck, colors, pool_size, metrics, tier_data=None):
    if not deck:
        return 0.0, ""
    features, tribe = deck_features(deck, colors, pool_size, metrics, tier_data)
    if features is None:
        return 0.0, ""

    power_level = BASE_SCORE
    breakdown_notes = []
    for name, weight in WEIGHTS.items():
        points = weight * features[name]
        power_level += points
        if points and name in NOTES:
            label = NOTES[name].format(tribe=tribe)
            breakdown_notes.append(
                f"{label} ({'+' if points > 0 else '-'}{abs(points):.1f})"
            )

    return max(0.0, power_level), ", ".join(breakdown_notes)


def estimate_record(power_level, is_bo3=False):
    if is_bo3:
        if power_level < 65:
            return "0-2 / 1-2"
        if power_level < 78:
            return "2-1"
        return "3-0"
    else:
        if power_level < 60:
            return "0-3 / 1-3"
        if power_level < 70:
            return "2-3 / 3-3"
        if power_level < 80:
            return "4-3 / 5-3"
        if power_level < 88:
            return "6-3"
        return "7-x"

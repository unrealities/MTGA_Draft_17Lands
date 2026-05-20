"""
src/advisor/mana_base.py
Frank Karsten mathematically-optimized mana base generation and source analysis.
"""

import itertools
import re
from src import constants


def calculate_dynamic_mana_base(spells, non_basic_lands, colors, forced_count=17):
    if forced_count <= 0:
        return []

    strict_pips, max_pip_in_single_card = (
        {c: 0 for c in constants.CARD_COLORS},
        {c: 0 for c in constants.CARD_COLORS},
    )
    lowest_cmc = {c: 99 for c in constants.CARD_COLORS}
    hybrid_pips = []

    analyzer = ManaSourceAnalyzer(spells + non_basic_lands)
    existing_sources, any_color = analyzer.sources, analyzer.any_color_sources
    any_color_enabler_pips = analyzer.any_color_enabler_pips

    for card in spells:
        cost, cmc = card.get("mana_cost", ""), int(card.get("cmc", 99) or 99)

        if cost:
            pips = re.findall(r"\{(.*?)\}", cost)
            card_color_pips = {c: 0 for c in constants.CARD_COLORS}
            for pip in pips:
                opts = pip.split("/")
                if all(opt.isdigit() or opt in ["X", "C"] for opt in opts):
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
                    max_pip_in_single_card[c] = max(1, max_pip_in_single_card[c])
                    lowest_cmc[c] = min(cmc, lowest_cmc[c])

    for opts, cmc in hybrid_pips:
        valid_opts = [opt for opt in opts if opt in colors]
        if not valid_opts:
            valid_opts = opts
        best_opt = max(valid_opts, key=lambda o: strict_pips[o])
        strict_pips[best_opt] += 1
        max_pip_in_single_card[best_opt] = max(1, max_pip_in_single_card[best_opt])
        lowest_cmc[best_opt] = min(cmc, lowest_cmc[best_opt])

    active_colors = [c for c in colors if strict_pips[c] > 0]
    if not active_colors:
        active_colors = [c for c in colors] if colors else ["W", "U", "B", "R", "G"]
    sorted_active = sorted(active_colors, key=lambda c: strict_pips[c], reverse=True)

    targets = {}
    for c in sorted_active:
        pips, max_pip = strict_pips.get(c, 0), max_pip_in_single_card.get(c, 0)
        if max_pip >= 3:
            target = 9
        elif max_pip == 2:
            target = 6 if pips <= 3 else (7 if pips <= 5 else 8)
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
            allocations[c] = max(0, min(deficit, 4 if max_pip >= 2 else 2))
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
        for c in sorted_active[:2]:
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
    card_colors, mana_cost = card.get("colors", []), card.get("mana_cost", "")
    if not card_colors:
        return True
    if strict:
        if mana_cost:
            for pip in re.findall(r"\{(.*?)\}", mana_cost):
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
        count, types, tags = (
            card.get("count", 1),
            card.get("types", []),
            card.get("tags", []),
        )
        text, name = (
            str(card.get("oracle_text", card.get("text", ""))).lower(),
            card.get("name", "").lower(),
        )
        card_colors, is_land = card.get("colors", []), "Land" in types

        specific_fixing_map = {
            "plainscycling": "W",
            "search your library for a plains": "W",
            "islandcycling": "U",
            "search your library for an island": "U",
            "swampcycling": "B",
            "search your library for a swamp": "B",
            "mountaincycling": "R",
            "search your library for a mountain": "R",
            "forestcycling": "G",
            "search your library for a forest": "G",
        }

        specific_match_found = False
        for phrase, color_sym in specific_fixing_map.items():
            if phrase in text:
                self.sources[color_sym] += count
                self.total_fixing_cards += count
                specific_match_found = True

        is_universal = any(
            phrase in text for phrase in constants.FIXING_KEYWORDS
        ) or any(fn in name for fn in constants.FIXING_NAMES)

        if (
            "fixing_ramp" in tags
            and not is_land
            and not specific_match_found
            and not is_universal
        ):
            produces_specific = False
            for c_sym in constants.CARD_COLORS:
                if (
                    f"add {{{c_sym.lower()}}}" in text
                    or f"adds {{{c_sym.lower()}}}" in text
                ):
                    self.sources[c_sym] += count
                    produces_specific = True
            if produces_specific:
                self.total_fixing_cards += count
            else:
                is_universal = True

        if is_universal and not specific_match_found:
            self.any_color_sources += count
            self.total_fixing_cards += count
            for c in card_colors:
                if c in self.any_color_enabler_pips:
                    self.any_color_enabler_pips[c] += count
            return

        if is_land and "Basic" not in types:
            if not card_colors and "fixing_ramp" in tags and not specific_match_found:
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
    return {
        c: analyzer.sources[c] + analyzer.any_color_sources
        for c in constants.CARD_COLORS
    }


def get_strict_colors(spells):
    pips, hybrid_pips_list = {c: 0 for c in constants.CARD_COLORS}, []
    for card in spells:
        cost = card.get("mana_cost", "")
        if not cost:
            for c in card.get("colors", []):
                if c in pips:
                    pips[c] += 1
            continue
        for pip in re.findall(r"\{(.*?)\}", cost):
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
        if not any(opt in strict_colors for opt in options):
            strict_colors.add(options[0])

    return [c for c in constants.CARD_COLORS if c in strict_colors]


def select_useful_lands(pool, target_colors, metrics=None):
    useful_lands = []
    baseline_wr = 54.0
    if metrics:
        b, _ = metrics.get_metrics("All Decks", "gihwr")
        if b > 0:
            baseline_wr = b

    for card in pool:
        name, types = card.get("name", ""), card.get("types", [])
        if name in constants.BASIC_LANDS or "Land" not in types or "Basic" in types:
            continue

        text, card_colors = (
            str(card.get("oracle_text", card.get("text", ""))).lower(),
            card.get("colors", []),
        )
        is_universal = any(
            phrase in text for phrase in constants.FIXING_KEYWORDS
        ) or any(fn in name.lower() for fn in constants.FIXING_NAMES)
        gihwr = float(
            card.get("deck_colors", {}).get("All Decks", {}).get("gihwr", 0.0)
        )

        if (
            is_universal
            or (card_colors and all(c in target_colors for c in card_colors))
            or not card_colors
        ):
            if gihwr >= (baseline_wr - 2.0) or gihwr == 0.0:
                useful_lands.append(card)

    colorless_lands = [
        c
        for c in useful_lands
        if not c.get("colors")
        and not any(fn in c.get("name", "").lower() for fn in constants.FIXING_NAMES)
    ]
    if len(colorless_lands) > 2:
        colorless_lands.sort(
            key=lambda x: float(
                x.get("deck_colors", {}).get("All Decks", {}).get("gihwr", 0.0)
            ),
            reverse=True,
        )
        for c in colorless_lands[2:]:
            useful_lands.remove(c)

    return useful_lands


def brute_force_mana_base(spells, non_basic_lands, colors, forced_count=17):
    """
    Finds the absolute optimal mana base by simulating dozens of permutations
    around the mathematical baseline.
    """
    if forced_count <= 0:
        return []

    # 1. Get the heuristic baseline
    baseline_basics = calculate_dynamic_mana_base(
        spells, non_basic_lands, colors, forced_count
    )

    base_counts = {c: 0 for c in colors}
    for b in baseline_basics:
        col = b["colors"][0]
        if col in base_counts:
            base_counts[col] += 1

    # 2. Generate Neighborhood Permutations (+/- 2 lands per color)
    tolerance = 2
    ranges = []

    # Only test permutations for colors we actually want to cast
    active_colors = [c for c in colors if base_counts.get(c, 0) > 0]
    if not active_colors:
        return baseline_basics

    for c in active_colors:
        base = base_counts[c]
        min_val = max(0, base - tolerance)
        max_val = base + tolerance
        ranges.append(range(min_val, max_val + 1))

    valid_permutations = []
    for combo in itertools.product(*ranges):
        if sum(combo) == forced_count:
            valid_permutations.append(dict(zip(active_colors, combo)))

    if not valid_permutations:
        return baseline_basics

    # 3. Simulate all valid permutations
    from src.advisor.simulator import simulate_deck  # Local import to prevent loops

    best_score = -9999
    best_perm = valid_permutations[0]
    base_deck = spells + non_basic_lands

    for perm in valid_permutations:
        temp_lands = []
        for c, count in perm.items():
            if count > 0:
                temp_lands.extend(create_basic_lands(c, count))

        test_deck = base_deck + temp_lands

        # We only need 2000 iterations to accurately sort permutations
        stats = simulate_deck(test_deck, iterations=2000)
        if not stats:
            continue

        # Fitness Function: Maximize playing on curve, TRIPLE penalty for color screw
        score = (
            stats["cast_t2"]
            + stats["cast_t3"]
            + stats["cast_t4"]
            + (stats["curve_out"] * 2.0)
            - (stats["mulligans"] * 1.5)
            - (stats["screw_t3"] * 1.5)
            - (stats["color_screw_t3"] * 3.0)
        )

        if score > best_score:
            best_score = score
            best_perm = perm

    # 4. Return the absolute best one
    final_lands = []
    for c, count in best_perm.items():
        if count > 0:
            final_lands.extend(create_basic_lands(c, count))

    return final_lands

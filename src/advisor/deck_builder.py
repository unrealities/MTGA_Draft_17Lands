"""
src/advisor/deck_builder.py
AI Deck Suggester and Auto-Optimizer. Generates distinct archetype variants.
"""

import copy
import logging
import re
import itertools
from src import constants
from src.card_logic import get_functional_cmc, stack_cards
from src.advisor.mana_base import (
    is_castable,
    select_useful_lands,
    calculate_dynamic_mana_base,
    count_fixing,
    get_strict_colors,
    create_basic_lands,
)
from src.advisor.deck_scorer import (
    get_card_rating,
    identify_top_pairs,
    calculate_holistic_score,
    estimate_record,
)
from src.advisor.simulator import simulate_deck

logger = logging.getLogger(__name__)
GLOBAL_DECK_CACHE = {}


def clear_deck_cache():
    GLOBAL_DECK_CACHE.clear()


def get_sideboard(pool, deck_stacked):
    pool_stacked = stack_cards(pool)
    sideboard = []
    deck_counts = {c.get("name"): c.get("count", 1) for c in deck_stacked}
    for c in pool_stacked:
        name = c.get("name")
        total_count = c.get("count", 1)
        used_count = deck_counts.get(name, 0)
        sb_count = total_count - used_count
        if sb_count > 0:
            sb_card = copy.deepcopy(c)
            sb_card["count"] = sb_count
            sideboard.append(sb_card)
    return sideboard


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


def optimize_deck(base_deck, base_sb, archetype_key, colors):
    total_cards = sum(c.get("count", 1) for c in base_deck)
    if total_cards != 40:
        return (
            base_deck,
            base_sb,
            None,
            f"Error: Deck must be exactly 40 cards to optimize (currently {total_cards}).",
        )

    spells = [c for c in base_deck if "Land" not in c.get("types", [])]
    lands = [c for c in base_deck if "Land" in c.get("types", [])]
    sb_spells = [
        c
        for c in base_sb
        if "Land" not in c.get("types", []) and is_castable(c, colors, strict=True)
    ]

    def get_wr(c):
        return float(
            c.get("deck_colors", {}).get(archetype_key, {}).get("gihwr")
            or c.get("deck_colors", {}).get("All Decks", {}).get("gihwr", 0.0)
        )

    spells.sort(key=get_wr)
    sb_spells.sort(key=get_wr, reverse=True)

    worst_spell = spells[0] if spells else None
    best_sb_spell = sb_spells[0] if sb_spells else None

    highest_cmc_spell = (
        max(spells, key=lambda c: get_functional_cmc(c)) if spells else None
    )
    cheap_sb_spells = [c for c in sb_spells if get_functional_cmc(c) <= 2]
    best_cheap_sb = cheap_sb_spells[0] if cheap_sb_spells else None

    basic_lands = [
        c
        for c in lands
        if "Basic" in c.get("types", []) or c.get("name") in constants.BASIC_LANDS
    ]
    cuttable_land = basic_lands[0] if basic_lands else None
    colorless_utility_lands = [
        c
        for c in lands
        if not c.get("colors")
        and not any(fn in c.get("name", "").lower() for fn in constants.FIXING_NAMES)
    ]
    worst_colorless_land = (
        min(colorless_utility_lands, key=get_wr) if colorless_utility_lands else None
    )

    permutations = [("Base Deck", base_deck, base_sb)]

    def swap_cards(deck, sb, out_card, in_card):
        new_deck = []
        new_sb = list(sb)
        removed = False

        for c in deck:
            if not removed and c["name"] == out_card["name"]:
                if c.get("count", 1) > 1:
                    new_c = dict(c)
                    new_c["count"] -= 1
                    new_deck.append(new_c)
                removed = True
            else:
                new_deck.append(c)

        if removed and in_card:
            added = False
            for c in new_deck:
                if c["name"] == in_card["name"]:
                    new_c = dict(c)
                    new_c["count"] += 1
                    new_deck = [
                        new_c if x["name"] == in_card["name"] else x for x in new_deck
                    ]
                    added = True
                    break
            if not added:
                in_c = dict(in_card)
                in_c["count"] = 1
                new_deck.append(in_c)

            sb_removed = False
            final_sb = []
            for c in new_sb:
                if not sb_removed and c["name"] == in_card["name"]:
                    if c.get("count", 1) > 1:
                        new_c = dict(c)
                        new_c["count"] -= 1
                        final_sb.append(new_c)
                    sb_removed = True
                else:
                    final_sb.append(c)
            new_sb = final_sb

            sb_added = False
            for c in new_sb:
                if c["name"] == out_card["name"]:
                    new_c = dict(c)
                    new_c["count"] += 1
                    new_sb = [
                        new_c if x["name"] == out_card["name"] else x for x in new_sb
                    ]
                    sb_added = True
                    break
            if not sb_added:
                out_c = dict(out_card)
                out_c["count"] = 1
                new_sb.append(out_c)

        return new_deck, new_sb

    if (
        highest_cmc_spell
        and best_cheap_sb
        and highest_cmc_spell["name"] != best_cheap_sb["name"]
    ):
        d, s = swap_cards(base_deck, base_sb, highest_cmc_spell, best_cheap_sb)
        permutations.append(
            (
                f"Curve Lower (-{highest_cmc_spell['name']}, +{best_cheap_sb['name']})",
                d,
                s,
            )
        )

    if worst_spell and best_sb_spell and worst_spell["name"] != best_sb_spell["name"]:
        d, s = swap_cards(base_deck, base_sb, worst_spell, best_sb_spell)
        permutations.append(
            (f"Power Up (-{worst_spell['name']}, +{best_sb_spell['name']})", d, s)
        )

    if worst_spell and cuttable_land:
        d, s = swap_cards(base_deck, base_sb, worst_spell, cuttable_land)
        permutations.append((f"Play 18 Lands (-{worst_spell['name']})", d, s))

    if cuttable_land and best_sb_spell:
        d, s = swap_cards(base_deck, base_sb, cuttable_land, best_sb_spell)
        permutations.append((f"Play 16 Lands (+{best_sb_spell['name']})", d, s))

    if worst_colorless_land:
        pip_counts = {c: 0 for c in constants.CARD_COLORS}
        for c in spells:
            cost = c.get("mana_cost", "")
            for pip in re.findall(r"\{(.*?)\}", cost):
                for opt in pip.split("/"):
                    if opt in pip_counts:
                        pip_counts[opt] += c.get("count", 1)

        best_basic_color = (
            max(pip_counts, key=pip_counts.get)
            if any(pip_counts.values())
            else (
                archetype_key[0]
                if archetype_key and archetype_key != "All Decks"
                else "W"
            )
        )
        synth_basic = create_basic_lands(best_basic_color, 1)[0]
        d, s = swap_cards(base_deck, base_sb, worst_colorless_land, synth_basic)
        permutations.append(
            (f"Fix Mana Base (-{worst_colorless_land['name']}, +Basic Land)", d, s)
        )

    basic_types = list(set(c["name"] for c in basic_lands))
    if len(basic_types) >= 2:
        for type_add in basic_types:
            for type_sub in basic_types:
                if type_add == type_sub:
                    continue
                card_sub = next((c for c in basic_lands if c["name"] == type_sub), None)
                card_add = next((c for c in basic_lands if c["name"] == type_add), None)
                if not card_add:
                    color_map_inv = {
                        "Plains": "W",
                        "Island": "U",
                        "Swamp": "B",
                        "Mountain": "R",
                        "Forest": "G",
                        "Wastes": "C",
                    }
                    synth_color = color_map_inv.get(type_add, "W")
                    card_add = create_basic_lands(synth_color, 1)[0]

                if card_sub:
                    d, s = swap_cards(base_deck, base_sb, card_sub, card_add)
                    permutations.append(
                        (f"Optimize Mana (+{type_add}, -{type_sub})", d, s)
                    )

    best_score = -9999
    best_perm = permutations[0]

    for desc, p_deck, p_sb in permutations:
        stats = simulate_deck(p_deck, iterations=500)
        if not stats:
            continue
        score = (
            stats["cast_t2"]
            + stats["cast_t3"]
            + stats["cast_t4"]
            + (stats["curve_out"] * 2)
            - stats["mulligans"]
            - (stats["screw_t3"] * 1.5)
            - (stats["color_screw_t3"] * 2.0)
            - (stats["flood_t5"] * 1.5)
        )
        if score > best_score:
            best_score = score
            best_perm = (desc, p_deck, p_sb)

    final_deck, final_sb = best_perm[1], best_perm[2]
    final_stats = simulate_deck(final_deck, iterations=10000)
    return final_deck, final_sb, final_stats, f"Optimized: {best_perm[0]}"


def suggest_deck(
    taken_cards,
    metrics,
    configuration,
    event_type="PremierDraft",
    progress_callback=None,
    dataset_name=None,
):
    sorted_decks = {}
    pool_size = len(taken_cards)
    is_bo3 = "Trad" in event_type

    playable_spells = [c for c in taken_cards if "Land" not in c.get("types", [])]
    if not playable_spells or len(playable_spells) < 15:
        return sorted_decks

    try:
        pool_sig = tuple(
            sorted([f"{c.get('name', '')}:{c.get('count', 1)}" for c in taken_cards])
        )
        cache_key = (event_type, dataset_name, len(taken_cards), pool_sig)

        if cache_key in GLOBAL_DECK_CACHE:
            if progress_callback:
                progress_callback({"status": "Loaded optimized decks from cache."})
            return GLOBAL_DECK_CACHE[cache_key]

        color_options = identify_top_pairs(taken_cards, metrics)
        all_variants, incomplete_variants = [], []
        seen_signatures = set()
        simulated_cache = {}  # Cache to prevent random variance on identical decks

        def process_variant(variant_name, deck, sb, colors, arch_key):
            if not deck:
                return
            spells = [c for c in deck if "Land" not in c.get("types", [])]
            spell_count = sum(c.get("count", 1) for c in spells)
            if spell_count < 15:
                return

            pips = {c: 0 for c in constants.CARD_COLORS}
            for card in spells:
                cost = card.get("mana_cost", "")
                if not cost:
                    for c in card.get("colors", []):
                        if c in pips:
                            pips[c] += card.get("count", 1)
                    continue
                for pip in re.findall(r"\{(.*?)\}", cost):
                    for opt in [
                        c for c in pip.split("/") if c in constants.CARD_COLORS
                    ]:
                        pips[opt] += card.get("count", 1)

            active_colors = sorted(
                [c for c, count in pips.items() if count > 0],
                key=lambda x: pips[x],
                reverse=True,
            )

            if not active_colors:
                true_arch_key, true_variant_name = arch_key, variant_name
            else:
                if len(active_colors) == 1:
                    true_arch_key, true_variant_name = active_colors[0], "Consistent"
                elif len(active_colors) == 2:
                    if pips[active_colors[1]] <= 3:
                        true_arch_key, true_variant_name = (
                            active_colors[0],
                            f"Splash {active_colors[1]}",
                        )
                    else:
                        true_arch_key = "".join(
                            sorted(
                                active_colors[:2],
                                key=lambda x: constants.CARD_COLORS.index(x),
                            )
                        )
                        true_variant_name = (
                            "Tempo" if "Tempo" in variant_name else "Consistent"
                        )
                else:
                    true_arch_key = "".join(
                        sorted(
                            active_colors[:2],
                            key=lambda x: constants.CARD_COLORS.index(x),
                        )
                    )
                    true_variant_name = (
                        "Good Stuff (Soup)"
                        if "Soup" in variant_name
                        else f"Splash {''.join(active_colors[2:])}"
                    )

            opt_deck, opt_sb, opt_note = deck, sb, ""

            # Generate a strict string signature of the 40-card deck
            deck_sig = "|".join(
                sorted([f"{c['name']}:{c.get('count', 1)}" for c in opt_deck])
            )

            if deck_sig in simulated_cache:
                opt_stats, score, breakdown = simulated_cache[deck_sig]
            else:
                opt_stats = simulate_deck(opt_deck, iterations=10000)
                score, breakdown = calculate_holistic_score(
                    opt_deck, active_colors, pool_size, metrics
                )

                if opt_stats:
                    mc_penalties = []
                    if opt_stats["color_screw_t3"] > 10.0:
                        pen = (opt_stats["color_screw_t3"] - 10.0) * 2.5
                        score -= pen
                        mc_penalties.append(f"Color Screw (-{pen:.1f})")
                    if opt_stats["screw_t3"] > 22.0:
                        pen = (opt_stats["screw_t3"] - 22.0) * 1.5
                        score -= pen
                        mc_penalties.append(f"Mana Screw (-{pen:.1f})")
                    if opt_stats["flood_t5"] > 27.0:
                        pen = (opt_stats["flood_t5"] - 27.0) * 1.5
                        score -= pen
                        mc_penalties.append(f"Flood Risk (-{pen:.1f})")

                    score = max(0.0, score)
                    if mc_penalties:
                        breakdown = (
                            f"{breakdown} | {', '.join(mc_penalties)}"
                            if breakdown
                            else ", ".join(mc_penalties)
                        )
                simulated_cache[deck_sig] = (opt_stats, score, breakdown)

            sig = tuple(
                sorted([f"{c.get('name')}:{c.get('count', 1)}" for c in opt_deck])
            )
            if sig in seen_signatures:
                return
            seen_signatures.add(sig)

            variant_data = {
                "label_prefix": true_variant_name,
                "type": "Deck",
                "rating": score,
                "record": estimate_record(score, is_bo3),
                "deck_cards": opt_deck,
                "sideboard_cards": opt_sb,
                "colors": active_colors,
                "breakdown": breakdown,
                "stats": opt_stats,
                "optimization_note": opt_note,
            }

            full_label = f"{true_arch_key} {true_variant_name} [Est: {variant_data['record']}] (Power: {score:.0f})"
            if "Incomplete Deck" not in breakdown:
                all_variants.append((full_label, variant_data))
            else:
                incomplete_variants.append((full_label, variant_data))
            if progress_callback:
                progress_callback(
                    {"variant_label": full_label, "variant_data": variant_data}
                )

        for main_colors in color_options:
            arch_key = "".join(sorted(main_colors))
            if progress_callback:
                progress_callback({"status": f"Analyzing {arch_key} Archetypes..."})

            con_deck = build_variant_consistency(taken_cards, main_colors, metrics)
            process_variant(
                "Consistent",
                con_deck,
                get_sideboard(taken_cards, con_deck),
                main_colors,
                arch_key,
            )

            greedy_deck, splash_color = build_variant_greedy(
                taken_cards, main_colors, metrics
            )
            if greedy_deck:
                process_variant(
                    f"Splash {splash_color}",
                    greedy_deck,
                    get_sideboard(taken_cards, greedy_deck),
                    main_colors + [splash_color],
                    arch_key,
                )

            tempo_deck = build_variant_curve(taken_cards, main_colors, metrics)
            process_variant(
                "Tempo",
                tempo_deck,
                get_sideboard(taken_cards, tempo_deck),
                main_colors,
                arch_key,
            )

        if progress_callback:
            progress_callback({"status": "Analyzing Domain / Soup..."})
        soup_deck, soup_colors = build_variant_soup(taken_cards, metrics)
        if soup_deck:
            soup_arch_key = (
                "".join(sorted(soup_colors[:3])) if soup_colors else "All Decks"
            )
            process_variant(
                "Good Stuff (Soup)",
                soup_deck,
                get_sideboard(taken_cards, soup_deck),
                soup_colors[:3] if soup_colors else ["All Decks"],
                soup_arch_key,
            )

        final_list = all_variants + incomplete_variants
        if not final_list:
            return {}

        final_list.sort(key=lambda x: x[1]["rating"], reverse=True)
        best_score = final_list[0][1]["rating"]

        safe_decks = [v for v in final_list if len(v[1]["colors"]) <= 2]
        best_safe = safe_decks[0] if safe_decks else None

        filtered_list, accepted_signatures = [], []

        for label, data in final_list:
            score, is_top_deck, is_best_safe = (
                data["rating"],
                (len(filtered_list) == 0),
                (best_safe is not None and label == best_safe[0]),
            )
            sig = {}
            for c in data["deck_cards"]:
                sig[c["name"]] = sig.get(c["name"], 0) + c.get("count", 1)

            max_overlap = 0
            for acc_sig in accepted_signatures:
                overlap = sum(
                    min(count, acc_sig.get(name, 0)) for name, count in sig.items()
                )
                if overlap > max_overlap:
                    max_overlap = overlap

            cards_diff = 40 - max_overlap
            keep = True if (is_top_deck or is_best_safe) else False

            if not keep:
                if cards_diff < 3:
                    keep = False
                elif cards_diff >= 10:
                    keep = True if score >= best_score - 25.0 else False
                else:
                    keep = True if score >= best_score - 50.0 else False

            if keep:
                filtered_list.append((label, data))
                accepted_signatures.append(sig)
                if len(filtered_list) >= 10:
                    break

        final_list = filtered_list
        safe_decks_filtered = [v for v in final_list if len(v[1]["colors"]) <= 2]

        if safe_decks_filtered:
            actual_best_safe = safe_decks_filtered[0]
            best_safe_idx = final_list.index(actual_best_safe)

            old_label = actual_best_safe[0]
            new_label = old_label.replace("Consistent", "🛡️ Safe Core").replace(
                "Tempo", "🛡️ Safe Tempo"
            )
            if "🛡️" not in new_label:
                parts = new_label.split(" ", 1)
                new_label = (
                    f"{parts[0]} 🛡️ Safe Core {parts[1]}"
                    if len(parts) > 1
                    else f"🛡️ Safe Core {new_label}"
                )

            actual_best_safe[1]["label_prefix"] = (
                actual_best_safe[1]["label_prefix"]
                .replace("Consistent", "Safe Core")
                .replace("Tempo", "Safe Tempo")
            )
            updated_safe = (new_label, actual_best_safe[1])
            final_list[best_safe_idx] = updated_safe

            if best_safe_idx > 0:
                top_deck = final_list[0]
                if (top_deck[1]["rating"] - updated_safe[1]["rating"]) <= 6.0:
                    final_list.insert(0, final_list.pop(best_safe_idx))
                elif best_safe_idx > 1:
                    final_list.insert(1, final_list.pop(best_safe_idx))

        for label, data in final_list:
            sorted_decks[label] = data

        GLOBAL_DECK_CACHE[cache_key] = sorted_decks

    except Exception as e:
        logger.error(f"Deck builder failure: {e}", exc_info=True)
        return {}

    return sorted_decks


def build_variant_consistency(pool, colors, metrics, tier_data=None):
    candidates = [
        c
        for c in pool
        if is_castable(c, colors, strict=True) and "Land" not in c.get("types", [])
    ]
    candidates.sort(key=lambda x: get_card_rating(x, colors, metrics), reverse=True)
    spells, non_basic_lands = (
        candidates[:23],
        select_useful_lands(pool, colors, metrics),
    )

    total_lands_needed = 40 - len(spells)
    if len(non_basic_lands) > total_lands_needed:
        non_basic_lands.sort(
            key=lambda x: float(
                x.get("deck_colors", {}).get("All Decks", {}).get("gihwr", 0.0)
            ),
            reverse=True,
        )
        non_basic_lands = non_basic_lands[:total_lands_needed]

    needed_basics = max(0, total_lands_needed - len(non_basic_lands))
    basics = calculate_dynamic_mana_base(
        spells, non_basic_lands, colors, forced_count=needed_basics
    )
    return stack_cards(spells + non_basic_lands + basics)


def build_variant_greedy(pool, colors, metrics, tier_data=None):
    global_mean, global_std = metrics.get_metrics("All Decks", "gihwr")
    if global_mean == 0.0:
        global_mean = 54.0
    if global_std == 0.0:
        global_std = 4.0

    fixing_sources = count_fixing(pool)
    splash_candidates, best_rating = [], global_mean - (global_std * 0.5)

    for card in pool:
        card_colors, mana_cost = card.get("colors", []), card.get("mana_cost", "")
        if (
            is_castable(card, colors, strict=True)
            or not card_colors
            or len(card_colors) > 1
        ):
            continue

        splash_col, off_color_pips = card_colors[0], 0
        for pip in re.findall(r"\{(.*?)\}", mana_cost):
            options = [c for c in pip.split("/") if c in constants.CARD_COLORS]
            if options and not any(opt in colors for opt in options):
                off_color_pips += 1

        if off_color_pips > 1:
            total_fixing = fixing_sources.get(splash_col, 0) + count_fixing(pool).get(
                splash_col, 0
            )
            if not (
                off_color_pips == 2
                and get_functional_cmc(card) >= 5
                and total_fixing >= 3
            ):
                continue

        rating = get_card_rating(card, ["All Decks"], metrics)
        if rating > best_rating and fixing_sources.get(splash_col, 0) >= 1:
            splash_candidates.append((card, splash_col, rating))

    if not splash_candidates:
        return None, ""

    splash_candidates.sort(key=lambda x: x[2], reverse=True)
    best_splash_col = splash_candidates[0][1]
    valid_splashes = [c[0] for c in splash_candidates if c[1] == best_splash_col]

    main_spells = [
        c
        for c in pool
        if is_castable(c, colors, strict=True) and "Land" not in c.get("types", [])
    ]
    main_spells.sort(key=lambda x: get_card_rating(x, colors, metrics), reverse=True)

    deck_spells = main_spells[:23]
    needed = 23 - len(deck_spells)
    if needed > 0:
        deck_spells.extend(valid_splashes[:needed])
    elif valid_splashes:
        deck_spells = main_spells[:22] + [valid_splashes[0]]

    target_colors = colors + [best_splash_col]
    non_basic_lands = select_useful_lands(pool, target_colors, metrics)

    total_lands_needed = 40 - len(deck_spells)
    if len(non_basic_lands) > total_lands_needed:
        non_basic_lands.sort(
            key=lambda x: float(
                x.get("deck_colors", {}).get("All Decks", {}).get("gihwr", 0.0)
            ),
            reverse=True,
        )
        non_basic_lands = non_basic_lands[:total_lands_needed]

    needed_basics = max(0, total_lands_needed - len(non_basic_lands))
    basics = calculate_dynamic_mana_base(
        deck_spells, non_basic_lands, target_colors, forced_count=needed_basics
    )
    return stack_cards(deck_spells + non_basic_lands + basics), best_splash_col


def build_variant_curve(pool, colors, metrics, tier_data=None):
    candidates = [
        c
        for c in pool
        if is_castable(c, colors, strict=True) and "Land" not in c.get("types", [])
    ]

    def tempo_rating(card):
        base, cmc = get_card_rating(card, colors, metrics), get_functional_cmc(card)
        if cmc <= 2:
            return base + 4.0
        if cmc >= 5:
            return base - 8.0
        return base

    candidates.sort(key=tempo_rating, reverse=True)
    spells, non_basic_lands = (
        candidates[:24],
        select_useful_lands(pool, colors, metrics),
    )

    total_lands_needed = 40 - len(spells)
    if len(non_basic_lands) > total_lands_needed:
        non_basic_lands.sort(
            key=lambda x: float(
                x.get("deck_colors", {}).get("All Decks", {}).get("gihwr", 0.0)
            ),
            reverse=True,
        )
        non_basic_lands = non_basic_lands[:total_lands_needed]

    needed_basics = max(0, total_lands_needed - len(non_basic_lands))
    basics = calculate_dynamic_mana_base(
        spells, non_basic_lands, colors, forced_count=needed_basics
    )
    return stack_cards(spells + non_basic_lands + basics)


def build_variant_soup(pool, metrics, tier_data=None):
    candidates = [c for c in pool if "Land" not in c.get("types", [])]

    def soup_rating(card):
        base, tags = (
            get_card_rating(card, ["All Decks"], metrics, tier_data),
            card.get("tags", []),
        )
        text, name = (
            str(card.get("oracle_text", card.get("text", ""))).lower(),
            str(card.get("name", "")).lower(),
        )

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
        return base + 5.0 if is_fixer else base

    candidates.sort(key=soup_rating, reverse=True)
    spells = candidates[:23]
    if not spells:
        return None, []

    soup_colors = get_strict_colors(spells)
    if not soup_colors:
        soup_colors = ["W", "U", "B", "R", "G"]
    non_basic_lands = select_useful_lands(pool, soup_colors, metrics)

    total_lands_needed = 40 - len(spells)
    if len(non_basic_lands) > total_lands_needed:
        non_basic_lands.sort(
            key=lambda x: float(
                x.get("deck_colors", {}).get("All Decks", {}).get("gihwr", 0.0)
            ),
            reverse=True,
        )
        non_basic_lands = non_basic_lands[:total_lands_needed]

    needed_basics = max(0, total_lands_needed - len(non_basic_lands))
    basics = calculate_dynamic_mana_base(
        spells, non_basic_lands, soup_colors, forced_count=needed_basics
    )
    return stack_cards(spells + non_basic_lands + basics), soup_colors

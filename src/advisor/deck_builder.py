"""
src/advisor/deck_builder.py
AI Deck Suggester and Auto-Optimizer. Generates distinct archetype variants.
"""

import copy
import logging
import re
import itertools
from src import constants
from src.card_utils import get_functional_cmc, stack_cards
from src.utils import normalize_color_string
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

# The safe deck is promoted to the top only when it's competitive; otherwise it
# is still shown (the user always wants a non-soupy option) but left in place so
# it doesn't masquerade as the best deck.
SAFE_DECK_PROMOTE_TO_TOP_GAP = 6.0
SAFE_DECK_PROMOTE_TO_SECOND_GAP = 20.0


def deck_identity_colors(data):
    """A deck's mana identity, ignoring incidental single-pip splashes."""
    ident = data.get("identity_colors")
    return ident if ident is not None else data.get("colors", [])


def select_safe_deck_index(final_list):
    """Index of the <=2-color deck to feature as the 'safe' (non-soupy) option.

    The user always wants at least one single- or dual-color deck, even with
    poor mana, so this returns -1 only when the pool genuinely can't form one.
    Among the <=2-color decks it prefers complete decks over incomplete ones,
    then higher power."""
    candidates = [
        i
        for i, (_, data) in enumerate(final_list)
        if len(deck_identity_colors(data)) <= 2
    ]
    if not candidates:
        return -1

    def rank(i):
        data = final_list[i][1]
        complete = "Incomplete Deck" not in (data.get("breakdown") or "")
        # Among near-equal decks (rating rounded), prefer the one with the
        # fewest actual colors so the "safe" pick has the tightest mana rather
        # than the most incidental splashes.
        return (
            complete,
            round(data.get("rating", 0.0)),
            -len(data.get("colors", [])),
        )

    return max(candidates, key=rank)
    return -1


def clear_deck_cache():
    GLOBAL_DECK_CACHE.clear()
    _MC_CACHE.clear()
    from src.advisor.engine import _LOOKAHEAD_CACHE

    _LOOKAHEAD_CACHE.clear()


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
        # The 18th land's COLOR follows the deck's needs (recomputed split),
        # not whichever basic happens to appear first in deck order.
        d_cut, s_cut = swap_cards(base_deck, base_sb, worst_spell, None)
        spells_after = [c for c in d_cut if "Land" not in c.get("types", [])]
        lands_after = [c for c in d_cut if "Land" in c.get("types", [])]
        nonbasics_after = [
            c
            for c in lands_after
            if c.get("name") not in constants.BASIC_LANDS
            and "Basic" not in c.get("types", [])
        ]

        def _basic_counts(deck_cards):
            counts = {}
            for c in deck_cards:
                if c.get("name") in constants.BASIC_LANDS or "Basic" in c.get(
                    "types", []
                ):
                    counts[c["name"]] = counts.get(c["name"], 0) + c.get("count", 1)
            return counts

        existing_basics = _basic_counts(d_cut)
        needed_basics = max(0, 18 - len(nonbasics_after))
        with_extra = calculate_dynamic_mana_base(
            spells_after, nonbasics_after, colors, forced_count=needed_basics
        )
        grown = _basic_counts(spells_after + nonbasics_after + with_extra)
        extra_color = "W"
        best_gain = -1
        color_map_inv = {
            "Plains": "W", "Island": "U", "Swamp": "B",
            "Mountain": "R", "Forest": "G", "Wastes": "C",
        }
        for name, count in grown.items():
            gain = count - existing_basics.get(name, 0)
            if gain > best_gain:
                best_gain = gain
                extra_color = color_map_inv.get(name, "W")
        # Merge the extra basic into an existing row: appending a separate
        # count-1 row for a basic already in the deck meant repeated
        # Auto-Optimize calls grew the deck (40 -> 42 -> rejected).
        d = [dict(c) for c in d_cut]
        basic_name = {"W": "Plains", "U": "Island", "B": "Swamp",
                      "R": "Mountain", "G": "Forest", "C": "Wastes"}[extra_color]
        for c in d:
            if c.get("name") == basic_name:
                c["count"] = c.get("count", 1) + 1
                break
        else:
            d.append(create_basic_lands(extra_color, 1)[0])
        cut_to_sb = dict(worst_spell)
        cut_to_sb["count"] = 1
        s = list(s_cut) + [cut_to_sb]
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

    # One MC objective with common random numbers: every permutation is
    # scored under the SAME seed (shared trials within the round) using the
    # shared _mana_fitness, and the winner gets one common fresh 10k
    # evaluation. Auto-Optimize is deterministic run to run.
    base_sig = "|".join(
        sorted(f"{c['name']}:{c.get('count', 1)}" for c in base_deck)
    )
    round_seed = _deck_seed(base_sig)
    best_score = -9999
    best_perm = permutations[0]

    for desc, p_deck, p_sb in permutations:
        stats = _mc_simulation(p_deck, 500, round_seed)
        if not stats:
            continue
        score = _mana_fitness(stats)
        if score > best_score:
            best_score = score
            best_perm = (desc, p_deck, p_sb)

    final_deck, final_sb = best_perm[1], best_perm[2]
    final_stats = _mc_simulation(final_deck, 10000, round_seed + 999)
    return final_deck, final_sb, final_stats, f"Optimized: {best_perm[0]}"


def _diversity_filter(final_list, best_safe=None):
    """Drops near-duplicate variants. Signatures cover the SPELLS only, so two
    decks with the same 23 spells and any basic split are one deck; a single
    spell swap is a genuinely different configuration and survives the -50
    score band."""
    from src.advisor.deck_scorer import TARGET_SPELL_COUNT

    best_score = final_list[0][1]["rating"] if final_list else 0.0
    filtered_list, accepted_signatures = [], []

    for label, data in final_list:
        score, is_top_deck, is_best_safe = (
            data["rating"],
            (len(filtered_list) == 0),
            (best_safe is not None and label == best_safe[0]),
        )
        sig = {}
        for c in data["deck_cards"]:
            if "Land" not in c.get("types", []):
                sig[c["name"]] = sig.get(c["name"], 0) + c.get("count", 1)

        max_overlap = 0
        for acc_sig in accepted_signatures:
            overlap = sum(
                min(count, acc_sig.get(name, 0)) for name, count in sig.items()
            )
            if overlap > max_overlap:
                max_overlap = overlap

        spells_diff = TARGET_SPELL_COUNT - max_overlap
        keep = True if (is_top_deck or is_best_safe) else False

        if not keep:
            if spells_diff == 0:
                # Identical spells: only the basic split differs — one deck.
                keep = False
            elif spells_diff >= 10:
                keep = True if score >= best_score - 25.0 else False
            else:
                keep = True if score >= best_score - 50.0 else False

        if keep:
            filtered_list.append((label, data))
            accepted_signatures.append(sig)
            if len(filtered_list) >= 10:
                break

    return filtered_list


MC_FITNESS_WEIGHT = 0.15
MC_ITERATIONS = 10000  # trials per candidate simulation (part of cache identity)
# Rescaled so the mana term cannot outweigh a >=1-sigma difference in average
# card quality (~12 holistic points): the realistic fitness spread between a
# deck's mana configurations is ~40 points -> <= 6 score points. Anchored by
# test_mc_anchor_card_quality_dominates.


def _mana_fitness(stats):
    """One MC objective (adopted from the manual optimizer's cast/curve
    fitness, mana_base.brute_force_mana_base's scoring): early exact-drop
    castability and curve, penalized by mulligans, screw and color screw."""
    return (
        stats["cast_t2"]
        + stats["cast_t3"]
        + stats["cast_t4"]
        + stats["curve_out"] * 2.0
        - stats["mulligans"] * 1.5
        - stats["screw_t3"] * 1.5
        - stats["color_screw_t3"] * 3.0
    )


def _finalist_mana_base(deck_cards, pool, identity_colors, metrics):
    """Exact-40-gated finalist wiring around mana_base.brute_force_mana_base.

    Validates the candidate before handing it to the live optimizer (which
    Custom-Deck Auto-Lands also uses, unchanged): exactly 40 cards, no more
    copies of any spell or nonbasic than the pool owns (basics are exempt —
    they have no pool entry). Raises ValueError on violation instead of
    letting brute_force_mana_base silently return its first permutation for
    an invalid input. forced_count is a BASIC-land count: the optimizer
    appends basics to spells + nonbasics.
    """
    from src.advisor import mana_base as mb

    spells = [c for c in deck_cards if "Land" not in c.get("types", [])]
    lands = [c for c in deck_cards if "Land" in c.get("types", [])]
    nonbasics = [
        c
        for c in lands
        if c.get("name") not in constants.BASIC_LANDS
        and "Basic" not in c.get("types", [])
    ]
    total = sum(c.get("count", 1) for c in deck_cards)
    if total != 40:
        raise ValueError(f"finalist mana base needs exactly 40 cards, got {total}")

    owned = {}
    for c in pool:
        owned[c.get("name", "")] = owned.get(c.get("name", ""), 0) + c.get("count", 1)
    for c in spells + nonbasics:
        if c.get("count", 1) > owned.get(c.get("name", ""), 0):
            raise ValueError(
                f"candidate uses more copies of {c.get('name', '')} than the pool owns"
            )

    forced = max(0, 40 - sum(c.get("count", 1) for c in spells + nonbasics))
    # The optimization colors are every color the deck's SPELL COSTS require,
    # not just the archetype identity: identity deliberately ignores
    # incidental single pips, which used to strip the only source for a
    # retained splash card (a red bomb kept with zero red sources).
    cast_colors = sorted({
        col
        for c in spells
        for col in (c.get("colors") or [])
    } | set(identity_colors))
    basics = mb.brute_force_mana_base(spells, nonbasics, cast_colors, forced_count=forced)
    if not basics:
        return deck_cards
    return spells + nonbasics + basics


# Monte-Carlo results keyed by the kernel's own per-card mana profiles (the
# exact arrays _parse_deck_to_arrays produces) plus trial identity: two decks
# whose lands, costs, pips, ramp/removal flags and produced-mana masks match
# produce identical simulations, so spell swaps that preserve the mana profile
# reuse the simulation instead of paying for it. Cleared with the deck caches.
_MC_CACHE = {}


def _mana_profiles(arrays):
    """Per-copy mana profile tuples, aligned with the expanded card copies."""
    return [
        (
            bool(arrays.is_land[i]),
            bool(arrays.is_ramp[i]),
            bool(arrays.is_removal[i]),
            int(arrays.costs[i]),
            int(arrays.mana_produced[i]),
            tuple(int(v) for v in arrays.pips[i]),
            int(arrays.pip_count[i]),
            int(arrays.generic[i]),
        )
        for i in range(len(arrays.costs))
    ]


def _canonical_sim_deck(deck_cards, per_card=None):
    """The deck as count-1 copies in canonical (profile-sorted) order —
    what the simulator should be fed so profile-identical decks behave
    identically and rows never multiply."""
    from src.advisor.simulator import _parse_deck_to_arrays

    if per_card is None:
        arrays = _parse_deck_to_arrays(deck_cards)
        if arrays is None:
            return list(deck_cards)
        per_card = _mana_profiles(arrays)
    copies = []
    for c in deck_cards:
        copies.extend([dict(c, count=1)] * int(c.get("count", 1)))
    order = sorted(range(len(per_card)), key=lambda i: per_card[i])
    return [copies[i] for i in order]


def _mc_simulation(deck_cards, iterations, seed=None):
    """CRN simulation keyed by the mana-profile multiset ALONE. Decks the
    simulator cannot distinguish (identical parsed profiles) get IDENTICAL
    stats: common random numbers across candidates, independent of card
    names (name-derived seeds used to reward pure simulation noise) and of
    array order (cache history used to change candidate scores). The
    effective seed derives from the profile key, so even cache-cold results
    are independent of evaluation order across processes."""
    import zlib

    from src.advisor.simulator import _parse_deck_to_arrays, simulate_deck

    arrays = _parse_deck_to_arrays(deck_cards)
    if arrays is None:
        return simulate_deck(deck_cards, iterations=iterations, seed=seed)
    per_card = _mana_profiles(arrays)
    key = (tuple(sorted(per_card)), iterations)
    if key in _MC_CACHE:
        return _MC_CACHE[key]
    canonical = _canonical_sim_deck(deck_cards, per_card)
    profile_seed = zlib.crc32(str(key[0]).encode("utf-8")) % (2 ** 31)
    stats = simulate_deck(canonical, iterations=iterations, seed=profile_seed)
    if len(_MC_CACHE) < 4096:
        _MC_CACHE[key] = stats
    return stats


def _deck_seed(deck_sig):
    """Stable per-deck seed (CRC32 of the signature): suggest_deck's MC term
    is reproducible run to run, a precondition for the CRN objective."""
    import zlib

    return zlib.crc32(deck_sig.encode("utf-8")) % (2 ** 31)



# --- Cycle 3: bounded search over the spells (3.1-3.3) ---

SEARCH_CLASS_SPELLS = (22, 23, 24)


def _has_unpayable_colorless(card):
    """True when the card has mandatory {C} pips but the pool has no
    colorless sources (deck builder guard: never recommend an unpayable
    spell — the picker already penalizes it, the builder must exclude it)."""
    import re as _re

    cost = str(card.get("mana_cost", ""))
    required_c = cost.count("{C}")
    if required_c == 0:
        return False
    return True  # the builder has no colorless-source context; the picker
    # already applied the Colorless Requirement penalty — the builder
    # simply excludes {C} cards from candidates until colorless source
    # tracking reaches the builder layer (follow-up issue)


def _owned_counts(cards):
    owned = {}
    for c in cards:
        owned[c.get("name", "")] = owned.get(c.get("name", ""), 0) + c.get("count", 1)
    return owned


def _is_basic_land(card):
    return "Land" in card.get("types", []) and (
        card.get("name") in constants.BASIC_LANDS
        or "Basic" in card.get("types", [])
    )


def candidate_is_legal(deck_cards, pool):
    """3.1 legality: exactly 40 cards, 22-24 spells, and no spell or drafted
    nonbasic beyond the copies the pool owns. Basic lands are exempt — they
    have no pool entry."""
    total = sum(c.get("count", 1) for c in deck_cards)
    if total != 40:
        return False
    spell_count = sum(
        c.get("count", 1) for c in deck_cards if "Land" not in c.get("types", [])
    )
    if spell_count not in SEARCH_CLASS_SPELLS:
        return False
    owned = _owned_counts(pool)
    present = _owned_counts(deck_cards)
    for name, count in present.items():
        card = next(c for c in deck_cards if c.get("name", "") == name)
        if _is_basic_land(card):
            continue
        if count > owned.get(name, 0):
            return False
    return True


def _with_land_split(spells, nonbasics, identity_colors, forced_count):
    """3.2: the candidate's lands follow its spell configuration (heuristic
    split; brute force stays finalist-only)."""
    basics = calculate_dynamic_mana_base(
        spells, nonbasics, identity_colors, forced_count=max(0, forced_count)
    )
    return spells + nonbasics + basics


def search_neighbors(deck_cards, pool, identity_colors):
    """3.2: coupled, count-aware moves. Every spell replacement is generated
    together with its re-derived land split; spell-count moves (one more spell
    with one fewer land, and the reverse) are paired with the land change —
    never a land-only change that leaves 39 or 41 cards."""
    spells = [c for c in deck_cards if "Land" not in c.get("types", [])]
    nonbasics = [
        c for c in deck_cards if "Land" in c.get("types", []) and not _is_basic_land(c)
    ]
    n_spells = sum(c.get("count", 1) for c in spells)
    n_nonbasics = sum(c.get("count", 1) for c in nonbasics)
    lands_total = 40 - n_spells - n_nonbasics

    owned = _owned_counts(pool)
    in_deck = _owned_counts(deck_cards)
    sideboard = [
        c
        for c in pool
        if "Land" not in c.get("types", [])
        and is_castable(c, identity_colors, strict=True)
        and in_deck.get(c.get("name", ""), 0) < owned.get(c.get("name", ""), 0)
    ]

    def _swap_spell(out_card, in_card):
        new_spells = []
        removed = False
        for c in spells:
            if not removed and c.get("name") == out_card.get("name"):
                if c.get("count", 1) > 1:
                    nc = dict(c)
                    nc["count"] -= 1
                    new_spells.append(nc)
                removed = True
            else:
                new_spells.append(c)
        if not removed:
            return None
        added = False
        for c in new_spells:
            if c.get("name") == in_card.get("name"):
                nc = dict(c)
                nc["count"] += 1
                new_spells = [
                    nc if x.get("name") == c.get("name") else x for x in new_spells
                ]
                added = True
                break
        if not added:
            ic = dict(in_card)
            ic["count"] = 1
            new_spells.append(ic)
        return new_spells

    for in_card in sideboard:
        for s in spells:
            new_spells = _swap_spell(s, in_card)
            if new_spells:
                yield _with_land_split(
                    new_spells, nonbasics, identity_colors, lands_total
                )
        if n_spells < 24:
            # merge into an existing row instead of appending a duplicate:
            # duplicate rows broke the aggregate ownership math (A3)
            merged = [dict(c) for c in spells]
            for c in merged:
                if c.get("name") == in_card.get("name"):
                    c["count"] = c.get("count", 1) + 1
                    break
            else:
                ic = dict(in_card)
                ic["count"] = 1
                merged.append(ic)
            yield _with_land_split(
                merged, nonbasics, identity_colors, lands_total - 1
            )
    if n_spells > 22:
        for s in spells:
            new_spells = _swap_spell(s, None) if False else None
            # drop one copy of s (count-aware), add one land
            dropped = []
            removed = False
            for c in spells:
                if not removed and c.get("name") == s.get("name"):
                    if c.get("count", 1) > 1:
                        nc = dict(c)
                        nc["count"] -= 1
                        dropped.append(nc)
                    removed = True
                else:
                    dropped.append(c)
            if removed:
                yield _with_land_split(
                    dropped, nonbasics, identity_colors, lands_total + 1
                )


def _class_probe(seed_deck, pool, identity_colors, target_spells):
    """One legal spell-count configuration (22 or 24 spells) derived from the
    seed: drop the pool-cheapest spell (or add the best castable sideboard
    card) with the land split re-derived. Purely exploratory — honest score."""
    spells = [c for c in seed_deck if "Land" not in c.get("types", [])]
    nonbasics = [
        c for c in seed_deck
        if "Land" in c.get("types", []) and not _is_basic_land(c)
    ]
    n_spells = sum(c.get("count", 1) for c in spells)
    n_nonbasics = sum(c.get("count", 1) for c in nonbasics)
    lands = 40 - n_spells - n_nonbasics

    if target_spells == n_spells - 1 and spells:
        weakest = spells[0]
        for s in spells:
            if get_card_rating(s, identity_colors) < get_card_rating(
                weakest, identity_colors
            ):
                weakest = s
        dropped = []
        removed = False
        for c in spells:
            if not removed and c.get("name") == weakest.get("name"):
                if c.get("count", 1) > 1:
                    nc = dict(c)
                    nc["count"] -= 1
                    dropped.append(nc)
                removed = True
            else:
                dropped.append(c)
        if not removed:
            return None
        return _with_land_split(dropped, nonbasics, identity_colors, lands + 1)

    if target_spells == n_spells + 1:
        owned = _owned_counts(pool)
        in_deck = _owned_counts(seed_deck)
        candidates = [
            c
            for c in pool
            if "Land" not in c.get("types", [])
            and is_castable(c, identity_colors, strict=True)
            and in_deck.get(c.get("name", ""), 0) < owned.get(c.get("name", ""), 0)
            and not _has_unpayable_colorless(c)
        ]
        if not candidates:
            return None
        best_add = max(candidates, key=lambda c: get_card_rating(c, identity_colors))
        merged = [dict(c) for c in spells]
        for c in merged:
            if c.get("name") == best_add.get("name"):
                c["count"] = c.get("count", 1) + 1
                break
        else:
            added = dict(best_add)
            added["count"] = 1
            merged.append(added)
        return _with_land_split(
            merged, nonbasics, identity_colors, lands - 1
        )

    return None


def _deck_role_state(deck_cards, pool):
    """(creature_count, early_count, needs): what the deck fields versus a
    23-spell deck's targets, capped by what the pool can actually supply."""
    creature_target, early_target = 13, 8

    def counts(cards):
        creatures = early = 0
        for c in cards:
            if "Land" in c.get("types", []):
                continue
            n = c.get("count", 1)
            if "Creature" in c.get("types", []):
                creatures += n
            if get_functional_cmc(c) <= 2:
                early += n
        return creatures, early

    pool_c, pool_e = counts(pool)
    deck_c, deck_e = counts(deck_cards)
    needs = (
        max(0, min(creature_target, pool_c) - deck_c),
        max(0, min(early_target, pool_e) - deck_e),
    )
    return deck_c, deck_e, needs


def _deck_avg_wr(deck_cards, identity_colors, metrics):
    spells = [c for c in deck_cards if "Land" not in c.get("types", [])]
    n = sum(c.get("count", 1) for c in spells)
    if not n:
        return 0.0
    return sum(
        get_card_rating(c, identity_colors, metrics) * c.get("count", 1)
        for c in spells
    ) / n


def _search_score(deck_cards, pool_size, metrics):
    """The cycle-2 objective under the candidate's own deterministic seed:
    holistic(identity) + rescaled mana fitness."""
    identity = deck_color_identity(deck_cards)
    sig = "|".join(sorted(f"{c.get('name', '')}:{c.get('count', 1)}" for c in deck_cards))
    stats = _mc_simulation(deck_cards, 500, _deck_seed(sig))
    score, _ = calculate_holistic_score(deck_cards, identity, pool_size, metrics)
    if stats:
        score += MC_FITNESS_WEIGHT * _mana_fitness(stats)
    return score, stats, identity


def _paired_epsilon(incumbent, challenger, k=3, trials=300):
    """3.3 acceptance margin: the spread of the paired mana-fitness
    differences under k common seeds, in score points. When the estimate is
    zero, acceptance still requires a strict improvement."""
    import statistics

    from src.advisor.simulator import simulate_deck

    diffs = []
    for i in range(k):
        # Direct simulation with EXPLICIT common seeds: the profile-keyed
        # cache ignores passed seeds, which used to collapse every trial to
        # the same draw (epsilon identically zero). Paired trials must
        # actually resample.
        a = simulate_deck(_canonical_sim_deck(incumbent),
                          iterations=trials, seed=97000 + i)
        b = simulate_deck(_canonical_sim_deck(challenger),
                          iterations=trials, seed=97000 + i)
        if a and b:
            diffs.append(_mana_fitness(b) - _mana_fitness(a))
    if len(diffs) < 2:
        return 0.0
    return statistics.pstdev(diffs) * MC_FITNESS_WEIGHT * 0.5


def _canonical_key(deck_cards):
    return tuple(sorted((c.get("name", ""), c.get("count", 1)) for c in deck_cards))


def beam_search(
    seed_decks,
    pool,
    pool_size,
    metrics,
    width=8,
    max_evals=400,
    progress_callback=None,
):
    """Deterministic beam search over legal 40-card configurations.

    Seeded from the surviving variants; children come from the same coupled,
    count-aware move generator the hill-climb uses; every beam member must be
    legal, and a member is only kept over its seed when the acceptance guards
    (noise margin, quality-or-role-needs) pass. Deterministic by construction:
    fixed expansion order, canonical dedupe, ties broken by the canonical key.
    Returns one best deck per seed (never worse than the seed itself).
    """
    def guarded(incumbent, cand, cand_score, inc_score):
        if cand_score - inc_score <= max(_paired_epsilon(incumbent, cand), 1.5):
            return False
        cand_identity = deck_color_identity(cand)
        inc_identity = deck_color_identity(incumbent)
        if _deck_avg_wr(cand, cand_identity, metrics) >= _deck_avg_wr(
            incumbent, inc_identity, metrics
        ) - 1e-9:
            return True
        inc_c, inc_e, needs = _deck_role_state(incumbent, pool)
        cand_c, cand_e, _ = _deck_role_state(cand, pool)
        return (needs[0] > 0 and cand_c > inc_c) or (needs[1] > 0 and cand_e > inc_e)

    results = []
    evals = 0
    for seed_deck in seed_decks:
        seed_score, _, _ = _search_score(seed_deck, pool_size, metrics)
        evals += 1
        best_deck, best_score = seed_deck, seed_score
        # anchor the beam to the seed's identity (archetype-anchored search,
        # same rationale as the hill climb)
        beam_identity = deck_color_identity(seed_deck)

        beam = [(seed_score, _canonical_key(seed_deck), seed_deck)]
        seen = {_canonical_key(seed_deck)}
        # Frontier continuation is decoupled from incumbent acceptance: a
        # plateau layer (no guarded improvement) still holds viable states —
        # the synergy payoff can be two NEUTRAL swaps away. Budget and the
        # seen-set bound the expansion; guarded acceptance still protects
        # the incumbent.
        while evals < max_evals:
            improved = False
            candidates = []
            for score, _key, deck in beam:
                for cand in search_neighbors(deck, pool, beam_identity):
                    if evals >= max_evals:
                        break
                    ck = _canonical_key(cand)
                    if ck in seen or not candidate_is_legal(cand, pool):
                        continue
                    cand_score, _, _ = _search_score(cand, pool_size, metrics)
                    evals += 1
                    seen.add(ck)
                    candidates.append((cand_score, ck, cand, deck, score))
                if evals >= max_evals:
                    break
            if not candidates:
                break
            candidates.sort(key=lambda t: (-t[0], t[1]))
            new_beam = []
            for cand_score, ck, cand, parent, parent_score in candidates:
                if len(new_beam) >= width:
                    break
                new_beam.append((cand_score, ck, cand))
            beam = new_beam
            top_score, _top_key, top_deck = beam[0]
            if top_score > best_score and guarded(best_deck, top_deck, top_score, best_score):
                best_deck, best_score = top_deck, top_score
                improved = True
            if progress_callback and evals % 40 == 0:
                progress_callback({"status": f"Beam search... ({evals} candidates)"})
        results.append((best_deck, best_score))
    return results


def hill_climb_search(
    seed_decks,
    pool,
    pool_size,
    metrics,
    max_evals=150,
    deadline_s=2.5,
    progress_callback=None,
):
    """3.3: hill-climb seeded from each surviving variant. Round-robin under
    one shared evaluation budget, CRN seeds per candidate, acceptance
    requires clearing the paired-noise margin, and every seed always stays
    a candidate: the search can only add, never replace with something
    worse. Returns one best deck per seed. The stop is budget-only: any
    wall-clock dependence would make the selected deck vary with machine
    speed."""
    budgets = max_evals
    evals = 0
    best_per_seed = []
    for seed_idx, seed_deck in enumerate(seed_decks):
        incumbent = seed_deck
        # The climb is anchored to the SEED's color identity: recomputing it
        # from the incumbent let the search drift archetype step by step
        # (a UB control variant ending as a WUBR soup) once cards were priced
        # under their own best pair. Each variant explores within itself.
        seed_identity = deck_color_identity(seed_deck)
        inc_score, _, inc_identity = _search_score(incumbent, pool_size, metrics)
        evals += 1
        exhausted = False
        while not exhausted:
            neighbors = list(search_neighbors(incumbent, pool, seed_identity))
            accepted = False
            for cand in neighbors:
                if evals >= budgets:
                    # budget-only stop: a wall-clock deadline here made the
                    # SELECTED DECK depend on machine speed (adversarial
                    # round: identical inputs, different results)
                    exhausted = True
                    break
                cand_score, _, cand_identity = _search_score(cand, pool_size, metrics)
                evals += 1
                if cand_score > inc_score:
                    eps = _paired_epsilon(incumbent, cand)
                    # A minimum margin beyond the noise estimate: lateral
                    # one-card swaps that clear the noise but carry no real
                    # objective gain churn the deck without improving it.
                    if cand_score - inc_score <= max(eps, 1.5):
                        continue
                    # Independent-counts guard: a swap that lowers the deck's
                    # average card quality may only be accepted when it fills
                    # a role the pool is short on (creatures, early plays) —
                    # mana farming on an already-sound deck is not an
                    # improvement, whatever the composite says.
                    quality_ok = _deck_avg_wr(cand, cand_identity, metrics) >= (
                        _deck_avg_wr(incumbent, inc_identity, metrics) - 1e-9
                    )
                    if not quality_ok:
                        inc_c, inc_e, needs = _deck_role_state(incumbent, pool)
                        cand_c, cand_e, _ = _deck_role_state(cand, pool)
                        fills_need = (needs[0] > 0 and cand_c > inc_c) or (
                            needs[1] > 0 and cand_e > inc_e
                        )
                        if not fills_need:
                            continue
                    incumbent = cand
                    inc_score = cand_score
                    inc_identity = cand_identity
                    accepted = True
                    break
            if not accepted:
                exhausted = True  # neighborhood exhausted (idempotence)
            if progress_callback and evals % 20 == 0:
                progress_callback({"status": f"Searching decks... ({evals} candidates)"})
        best_per_seed.append((incumbent, inc_score))
    return best_per_seed

def suggest_deck(
    taken_cards,
    metrics,
    configuration,
    event_type="PremierDraft",
    progress_callback=None,
    dataset_name=None,
    tier_data=None,
):
    sorted_decks = {}
    pool_size = len(taken_cards)
    is_bo3 = "Trad" in event_type

    # Canonical processing order (name, count): builder selection breaks
    # rating ties by list position, which made the EMITTED deck depend on
    # the pool's arrival order even though the cache identity is
    # order-insensitive (fresh adversarial round F2).
    taken_cards = sorted(
        taken_cards,
        key=lambda c: (c.get("name", ""), c.get("count", 1)),
    )

    playable_spells = [c for c in taken_cards if "Land" not in c.get("types", [])]
    if not playable_spells or len(playable_spells) < 15:
        return sorted_decks

    try:
        pool_sig = tuple(
            sorted([f"{c.get('name', '')}:{c.get('count', 1)}" for c in taken_cards])
        )
        def _stats_sig(cards):
            # EVERY stat slice that feeds the scorers (all pairs, not just
            # All Decks): a pair-only WR change must invalidate the cache
            parts = []
            for c in cards:
                dc = c.get("deck_colors", {})
                for pair, st in sorted(dc.items()):
                    parts.append(
                        "{}|{}:{}/{}".format(
                            c.get("name", ""),
                            pair,
                            st.get("gihwr", 0),
                            st.get("samples", 0),
                        )
                    )
            import zlib as _zlib

            return _zlib.crc32(";".join(sorted(parts)).encode("utf-8"))

        def _cost_sig(cards):
            parts = []
            for c in cards:
                parts.append(
                    "{}:{}:{}".format(
                        c.get("name", ""),
                        c.get("mana_cost", ""),
                        c.get("cmc", 0),
                    )
                )
            import zlib as _zlib

            return _zlib.crc32(";".join(sorted(parts)).encode("utf-8"))

        metrics_sig = None
        try:
            metrics_sig = metrics.get_metrics("All Decks", "gihwr") if metrics else None
        except Exception:
            metrics_sig = None
        def _tier_sig(tier_data):
            """Tier content changes must invalidate the suggestion cache:
            importing a new tier list while keeping the same pool used to
            return stale suggestions computed with the old tiers."""
            if not tier_data:
                return None
            import hashlib as _hashlib

            parts = []
            for name, obj in sorted(tier_data.items()):
                ratings = getattr(obj, "ratings", {})
                for card_name, r in sorted(ratings.items()):
                    parts.append(f"{card_name}:{getattr(r, 'rating', '')}")
            return _hashlib.md5(";".join(parts).encode("utf-8")).hexdigest()

        cache_key = (
            event_type,
            dataset_name,
            len(taken_cards),
            pool_sig,
            _stats_sig(taken_cards),
            _cost_sig(taken_cards),
            tuple(metrics_sig) if metrics_sig else None,
            _tier_sig(tier_data),
        )

        if cache_key in GLOBAL_DECK_CACHE:
            if progress_callback:
                progress_callback({"status": "Loaded optimized decks from cache."})
            return GLOBAL_DECK_CACHE[cache_key]

        color_options = identify_top_pairs(taken_cards, metrics, tier_data)
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

            pips, active_colors = deck_pips_and_colors(deck)
            identity_colors = deck_color_identity(deck)

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

            # Simulation cache: keyed by the full trial identity (deck
            # signature, seed, iteration count) and stores ONLY the simulated
            # stats — the contextual holistic score is recomputed per variant
            # because it depends on the valuation context.
            sim_seed = _deck_seed(deck_sig)
            sim_key = (deck_sig, sim_seed, MC_ITERATIONS)
            if sim_key in simulated_cache:
                opt_stats = simulated_cache[sim_key]
            else:
                opt_stats = simulate_deck(
                    opt_deck, iterations=MC_ITERATIONS, seed=sim_seed
                )
                simulated_cache[sim_key] = opt_stats

            score, breakdown = calculate_holistic_score(
                opt_deck, identity_colors, pool_size, metrics, tier_data
            )
            if opt_stats:
                # One MC objective, rescaled (see MC_FITNESS_WEIGHT): the
                # three hinge penalties are gone; the mana term rewards
                # castable curves and punishes screw continuously instead
                # of at three cliff thresholds.
                mc = MC_FITNESS_WEIGHT * _mana_fitness(opt_stats)
                score += mc
                score = max(0.0, score)
                breakdown = (
                    f"{breakdown} | Mana (+{mc:.1f})" if breakdown else f"Mana (+{mc:.1f})"
                )

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
                "identity_colors": identity_colors,
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
            arch_key = normalize_color_string("".join(main_colors))
            if progress_callback:
                progress_callback({"status": f"Analyzing {arch_key} Archetypes..."})

            con_deck = build_variant_consistency(taken_cards, main_colors, metrics, tier_data)
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

            tempo_deck = build_variant_curve(taken_cards, main_colors, metrics, tier_data)
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
                normalize_color_string("".join(soup_colors[:3]))
                if soup_colors
                else "All Decks"
            )
            process_variant(
                "Good Stuff (Soup)",
                soup_deck,
                get_sideboard(taken_cards, soup_deck),
                soup_colors[:3] if soup_colors else ["All Decks"],
                soup_arch_key,
            )

        # Incomplete (land-padded) variants are only worth showing when there
        # is almost nothing else to offer.
        if len(all_variants) >= 3:
            final_list = list(all_variants)
            # Always keep at least one non-soupy option: if none of the complete
            # decks is <=2 colors, retain the best <=2-color incomplete deck so
            # the user always has a single/dual-color suggestion (poor mana OK).
            if not any(len(deck_identity_colors(v[1])) <= 2 for v in final_list):
                two_color_incomplete = [
                    v
                    for v in incomplete_variants
                    if len(deck_identity_colors(v[1])) <= 2
                ]
                if two_color_incomplete:
                    final_list.append(
                        max(two_color_incomplete, key=lambda v: v[1]["rating"])
                    )
        else:
            final_list = all_variants + incomplete_variants
        if not final_list:
            return {}

        final_list.sort(key=lambda x: x[1]["rating"], reverse=True)
        best_score = final_list[0][1]["rating"]

        safe_idx = select_safe_deck_index(final_list)
        best_safe = final_list[safe_idx] if safe_idx >= 0 else None

        final_list = _diversity_filter(final_list, best_safe)
        best_safe_idx = select_safe_deck_index(final_list)

        if best_safe_idx >= 0:
            actual_best_safe = final_list[best_safe_idx]

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
                gap = final_list[0][1]["rating"] - updated_safe[1]["rating"]
                if gap <= SAFE_DECK_PROMOTE_TO_TOP_GAP:
                    final_list.insert(0, final_list.pop(best_safe_idx))
                elif gap <= SAFE_DECK_PROMOTE_TO_SECOND_GAP and best_safe_idx > 1:
                    final_list.insert(1, final_list.pop(best_safe_idx))
                # Otherwise leave it in its natural position: still shown and
                # labeled, but not masquerading as a top pick.

        # Finalist mana optimization: the top-3 variants are re-based with
        # brute_force_mana_base (exact-40-gated wrapper; Auto-Lands' own path
        # is untouched, and there is deliberately NO two-color short-circuit
        # here — exact-pip castability still improves for 2-color decks).
        # The finalist brute-force score is the one reported: these decks are
        # re-scored, and the holistic + rescaled-mana formula is recomputed
        # on the new configuration.
        for idx in range(min(3, len(final_list))):
            label, data = final_list[idx]
            try:
                redeck = _finalist_mana_base(
                    data["deck_cards"], taken_cards, data.get("identity_colors") or data.get("colors"), metrics
                )
            except ValueError:
                continue
            if redeck is data["deck_cards"]:
                continue
            pips_d, active_d = deck_pips_and_colors(redeck)
            identity_d = deck_color_identity(redeck)
            deck_sig_d = "|".join(
                sorted(f"{c['name']}:{c.get('count', 1)}" for c in redeck)
            )
            stats_d = simulate_deck(
                redeck, iterations=MC_ITERATIONS, seed=_deck_seed(deck_sig_d)
            )
            score_d, breakdown_d = calculate_holistic_score(
                redeck, identity_d, pool_size, metrics, tier_data
            )
            if stats_d:
                score_d += MC_FITNESS_WEIGHT * _mana_fitness(stats_d)
                score_d = max(0.0, score_d)
            data = dict(data)
            data["deck_cards"] = redeck
            data["colors"] = active_d or data.get("colors")
            data["identity_colors"] = identity_d
            data["rating"] = score_d
            data["breakdown"] = breakdown_d
            data["stats"] = stats_d or data.get("stats")
            final_list[idx] = (label, data)

        # Cycle 3: bounded search seeded from the surviving variants. The
        # search can only ADD a strictly better configuration — every seed
        # stays a candidate — and every emitted candidate is legality-checked
        # (exact-40, 22-24 spells, pool multiplicity).
        try:
            if progress_callback:
                progress_callback({"status": "Searching for better decks..."})
            search_seeds = [data["deck_cards"] for _, data in final_list[:3]]
            results = hill_climb_search(
                search_seeds,
                taken_cards,
                pool_size,
                metrics,
                progress_callback=progress_callback,
            )
            # Beam search over the same seeds with the same guards; a seed's
            # result is whichever of hill-climb/beam found the better
            # configuration (each is never worse than the seed on its own).
            beam_results = beam_search(
                search_seeds,
                taken_cards,
                pool_size,
                metrics,
                progress_callback=progress_callback,
            )
            results = [
                (beam_best, beam_score) if beam_score > climb_score
                else (climb_best, climb_score)
                for (climb_best, climb_score), (beam_best, beam_score) in zip(
                    results, beam_results
                )
            ]
            for (label, data), (best, best_score) in zip(final_list[:3], results):
                if best is data["deck_cards"]:
                    continue
                if best_score <= data["rating"]:
                    continue
                if not candidate_is_legal(best, taken_cards):
                    continue
                _, stats_s, identity_s = _search_score(best, pool_size, metrics)
                searched = dict(data)
                searched.update(
                    deck_cards=stack_cards(best),
                    rating=best_score,
                    stats=stats_s or data.get("stats"),
                    identity_colors=identity_s,
                    # the sideboard follows the FINAL deck: pool minus deck,
                    # never the seed's stale remainder
                    sideboard_cards=get_sideboard(taken_cards, best),
                    label_prefix=f"Searched {data.get('label_prefix', '')}",
                )
                final_list.insert(0, (f"🔎 {label}", searched))

            # Class probes: a spell-count configuration the builders no longer
            # emit is still a legal option worth showing — honest rating, the
            # seed stays the anchor. Built from the top seed only.
            present_classes = {
                sum(
                    c.get("count", 1)
                    for c in data["deck_cards"]
                    if "Land" not in c.get("types", [])
                )
                for _, data in final_list
            }
            # Probe seed: the top variant, but when a coherent (<=3 color)
            # build is within noise of the top, prefer it — a spell-count
            # probe anchored to a 5-color soup drifts the suggestion away
            # from the archetype the user is looking at.
            top_seed = final_list[0][1]["deck_cards"] if final_list else None
            if top_seed is not None:
                if len(deck_color_identity(top_seed)) > 3:
                    top_rating = final_list[0][1].get("rating", 0.0)
                    for _, cand_data in final_list[1:]:
                        if len(cand_data.get("identity_colors", [])) <= 3 and \
                                top_rating - cand_data.get("rating", 0.0) <= 1.5:
                            top_seed = cand_data["deck_cards"]
                            break
                top_identity = deck_color_identity(top_seed)
                for target in (22, 24):
                    if target in present_classes:
                        continue
                    probe = _class_probe(top_seed, taken_cards, top_identity, target)
                    if probe is None or not candidate_is_legal(probe, taken_cards):
                        continue
                    p_score, p_stats, p_identity = _search_score(
                        probe, pool_size, metrics
                    )
                    probed = dict(final_list[0][1])
                    probed.update(
                        deck_cards=stack_cards(probe),
                        rating=p_score,
                        stats=p_stats,
                        identity_colors=p_identity,
                        sideboard_cards=get_sideboard(taken_cards, probe),
                        label_prefix=f"{target}-Spell Probe",
                    )
                    final_list.append((f"⚖ {target} Spells", probed))
        except Exception as e:
            logger.warning(f"Deck search error: {e}")

        # Publication: re-rank the completed list by FINAL rating and rebuild
        # the derived display fields (record, Power label). Search results and
        # probes used to be spliced in iteration order with their seed's
        # stale label — the panel picks the first row, which was not always
        # the best final deck (fresh adversarial round R3-2).
        final_list.sort(key=lambda kv: -kv[1].get("rating", 0.0))
        for label, data in final_list:
            # sort the deck for display: spells by CMC, then lands
            deck_cards = data.get("deck_cards", [])
            spells = sorted(
                [c for c in deck_cards if "Land" not in c.get("types", [])],
                key=lambda c: (c.get("cmc", 0), c.get("name", "")),
            )
            lands = [c for c in deck_cards if "Land" in c.get("types", [])]
            data["deck_cards"] = spells + lands
            rating = data.get("rating", 0.0)
            record = estimate_record(rating, is_bo3)
            data["record"] = record
            if "(Power:" in label:
                head = label.split("(Power:")[0].rstrip()
                label = f"{head}(Power: {rating:.0f})"
            sorted_decks[label] = data

        GLOBAL_DECK_CACHE[cache_key] = sorted_decks

    except Exception as e:
        # Internal failures must surface as builder errors, not as the
        # friendly "not enough playables" empty result: the UI worker's error
        # branch (and its users) deserve to see the real cause.
        logger.error(f"Deck builder failure: {e}", exc_info=True)
        raise

    return sorted_decks


def build_variant_consistency(pool, colors, metrics, tier_data=None):
    _tier = tier_data  # forwarded to every rating below (RP1)
    candidates = [
        c
        for c in pool
        if is_castable(c, colors, strict=True) and "Land" not in c.get("types", [])
        and not _has_unpayable_colorless(c)
    ]
    candidates.sort(
        key=lambda x: get_card_rating(x, colors, metrics, tier_data=tier_data),
        reverse=True,
    )
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


def deck_pips_and_colors(deck):
    """Pip histogram and pip-descending color list over a deck's spells."""
    spells = [c for c in deck if "Land" not in c.get("types", [])]
    pips = {c: 0 for c in constants.CARD_COLORS}
    for card in spells:
        cost = card.get("mana_cost", "")
        if not cost:
            for c in card.get("colors", []):
                if c in pips:
                    pips[c] += card.get("count", 1)
            continue
        for pip in re.findall(r"\{(.*?)\}", cost):
            for opt in [c for c in pip.split("/") if c in constants.CARD_COLORS]:
                pips[opt] += card.get("count", 1)
    active_colors = sorted(
        [c for c, count in pips.items() if count > 0],
        key=lambda x: pips[x],
        reverse=True,
    )
    return pips, active_colors


def deck_color_identity(deck_cards):
    """A deck's true color identity ignores incidental single pips from a lone
    gold/hybrid card (e.g. one 5-color card adding a stray white pip to a
    Golgari deck). Such a deck is still mechanically 2-color. Shared by the
    suggester's holistic scoring and the engine's lookahead so both score the
    same deck under the same color regime."""
    pips, active_colors = deck_pips_and_colors(deck_cards)
    identity = [c for c in active_colors if pips.get(c, 0) >= 2]
    if not identity:
        identity = active_colors[:2] if active_colors else []
    return identity


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
            # Count fixing once: fixing_sources is the hoisted per-color count;
            # recomputing and adding it here doubled every source (2 sources
            # passed a >= 3 gate).
            total_fixing = fixing_sources.get(splash_col, 0)
            if not (
                off_color_pips == 2
                and get_functional_cmc(card) >= 5
                and total_fixing >= 3
            ):
                continue

        rating = get_card_rating(card, ["All Decks"], metrics, tier_data=tier_data)
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
    main_spells.sort(
        key=lambda x: get_card_rating(x, colors, metrics, tier_data=tier_data),
        reverse=True,
    )

    # A splash is 2-3 cards depending on fixing, not a third color pillar.
    # Filling thin main colors with unlimited splash cards produced "splash"
    # decks with 6 off-color spells on 2 sources.
    splash_cap = 3 if fixing_sources.get(best_splash_col, 0) >= 3 else 2

    deck_spells = main_spells[:23]
    splash_in_deck = False
    needed = 23 - len(deck_spells)
    if needed > 0:
        deck_spells.extend(valid_splashes[: min(needed, splash_cap)])
        if valid_splashes:
            splash_in_deck = True
        if sum(c.get("count", 1) for c in deck_spells) < 20:
            # Even a capped splash can't make this pair a real deck.
            return None, ""
    elif valid_splashes:
        # The splash must beat the 23rd spell it would cut on ONE shared scale:
        # rate both with the deck's own colors. The old code swapped
        # unconditionally, cutting a pair-proven on-color spell for a splash
        # that had only cleared an absolute floor.
        best_splash = valid_splashes[0]
        if get_card_rating(
            best_splash, colors, metrics, tier_data=tier_data
        ) > get_card_rating(
            main_spells[22], colors, metrics, tier_data=tier_data
        ):
            deck_spells = main_spells[:22] + [best_splash]
            splash_in_deck = True

    target_colors = colors + [best_splash_col] if splash_in_deck else list(colors)
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
    return (
        stack_cards(deck_spells + non_basic_lands + basics),
        best_splash_col if splash_in_deck else "",
    )


def build_variant_curve(pool, colors, metrics, tier_data=None):
    _tier = tier_data  # forwarded to every rating below (RP1)
    candidates = [
        c
        for c in pool
        if is_castable(c, colors, strict=True) and "Land" not in c.get("types", [])
        and not _has_unpayable_colorless(c)
    ]

    def tempo_rating(card):
        base, cmc = get_card_rating(card, colors, metrics, tier_data=tier_data), get_functional_cmc(card)
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

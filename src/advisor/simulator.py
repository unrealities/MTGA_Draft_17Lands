"""Approximate early-turn deck castability with lands and non-land mana sources.

Known limitation: mana available only via a separately cast prepared spell,
such as Konstrari Improviser's ability, is not modeled.
"""

import re
from typing import NamedTuple

import numpy as np
from numba import njit

# Mana Bitmask Mapping
COLOR_BITS = {"W": 1, "U": 2, "B": 4, "R": 8, "G": 16}
ANY_COLOR = 31  # W|U|B|R|G

# Fixed widths so the arrays can be consumed by the numba kernel.
DECK_SIZE = 40
MAX_PIPS = 8  # colored pips tracked per card (more only occurs on 8+ drops)
MAX_SOURCES = 16  # lands + ramp seen by turn 4 is at most 7 + 3 = 10

PIP_PATTERN = re.compile(r"\{(.*?)\}")


class DeckArrays(NamedTuple):
    is_land: np.ndarray  # bool[40]
    is_ramp: np.ndarray  # bool[40] non-land mana sources (rocks, dorks, treasure)
    is_removal: np.ndarray  # bool[40]
    costs: np.ndarray  # int8[40] printed mana value used for castability
    mana_produced: np.ndarray  # int32[40] color mask produced by lands/ramp
    pips: np.ndarray  # int32[40, MAX_PIPS] colored pips, each a mask of options
    pip_count: np.ndarray  # int8[40] number of colored pips used in `pips`
    generic: np.ndarray  # int8[40] generic portion of the cost


def parse_mana_cost(mana_cost, fallback_cmc=0):
    """
    Splits a printed mana cost into (colored_pips, generic).

    colored_pips is a list of bitmasks; each pip may be paid by any color in
    its mask ({G/U} -> G|U, {G/P} -> G). Numbers add to generic, {2/W}
    counts as 2 generic, {C} and {S} count as generic and {X} counts as 0, so
    the total always matches the printed mana value. Only the front face of
    split / modal costs is used. A card without a mana_cost string falls back
    to `fallback_cmc` generic mana.
    """
    cost = str(mana_cost or "").split("//")[0]
    symbols = PIP_PATTERN.findall(cost)
    if not symbols:
        try:
            return [], max(0, int(fallback_cmc or 0))
        except (TypeError, ValueError):
            return [], 0

    colored, generic = [], 0
    for sym in symbols:
        sym = sym.upper()
        if sym.isdigit():
            generic += int(sym)
            continue
        # Monocolored hybrid {2/W}: count it at its mana value (2 generic)
        digits = [opt for opt in sym.split("/") if opt.isdigit()]
        if digits:
            generic += int(digits[0])
            continue
        mask = 0
        for opt in sym.split("/"):
            mask |= COLOR_BITS.get(opt, 0)
        if mask:
            colored.append(mask)
        elif sym in ("C", "S"):
            generic += 1
        # X, Y, Z and unknown symbols contribute nothing to the mana value
    return colored, generic


def _parse_deck_to_arrays(deck_list):
    """Converts the deck from slow Python dicts to fast NumPy arrays."""
    flat_deck = []
    for c in deck_list:
        flat_deck.extend([c] * int(c.get("count", 1)))

    if len(flat_deck) < DECK_SIZE:
        return None

    is_land = np.zeros(DECK_SIZE, dtype=np.bool_)
    is_ramp = np.zeros(DECK_SIZE, dtype=np.bool_)
    is_removal = np.zeros(DECK_SIZE, dtype=np.bool_)
    costs = np.zeros(DECK_SIZE, dtype=np.int8)
    mana_produced = np.zeros(DECK_SIZE, dtype=np.int32)
    pips = np.zeros((DECK_SIZE, MAX_PIPS), dtype=np.int32)
    pip_count = np.zeros(DECK_SIZE, dtype=np.int8)
    generic = np.zeros(DECK_SIZE, dtype=np.int8)

    for i, c in enumerate(flat_deck[:DECK_SIZE]):
        types = c.get("types", [])
        tags = c.get("tags", [])
        text = str(c.get("oracle_text", c.get("text", ""))).lower()
        any_color = re.search(r"\bany (?:one |combination of )?colors?\b", text) is not None

        is_land[i] = "Land" in types
        is_ramp[i] = (
            "fixing_ramp" in tags or any_color or "treasure" in text
        ) and not is_land[i]
        is_removal[i] = "removal" in tags

        # Calculate produced mana bitmask
        if is_land[i] or is_ramp[i]:
            if any_color or "treasure" in text:
                mana_produced[i] = ANY_COLOR
            else:
                # Read production clauses, excluding symbols in activation costs.
                symbols = []
                for clause in re.findall(r"\badd\b([^.;\n]*)", text):
                    symbols.extend(PIP_PATTERN.findall(clause))
                mask = 0
                if symbols:
                    for symbol in symbols:
                        for color in symbol.upper().split("/"):
                            mask |= COLOR_BITS.get(color, 0)
                else:
                    for color in c.get("colors", []):
                        mask |= COLOR_BITS.get(color, 0)
                mana_produced[i] = mask

        # Printed cost (castability deliberately ignores cycling / alt costs)
        if not is_land[i]:
            colored, gen = parse_mana_cost(c.get("mana_cost", ""), c.get("cmc", 0))
            total = len(colored) + gen
            # Pips beyond MAX_PIPS (8+ colored pips) are treated as generic
            colored = colored[:MAX_PIPS]
            for p, mask in enumerate(colored):
                pips[i, p] = mask
            pip_count[i] = len(colored)
            generic[i] = min(total - len(colored), 100)
            costs[i] = min(total, 100)

    return DeckArrays(
        is_land, is_ramp, is_removal, costs, mana_produced, pips, pip_count, generic
    )


@njit(cache=True)
def _fill_cover(src_masks, n_src, cover):
    """cover[u] = number of sources able to produce at least one color in u."""
    for u in range(32):
        cover[u] = 0
    for i in range(n_src):
        m = src_masks[i]
        for u in range(1, 32):
            if m & u:
                cover[u] += 1


@njit(cache=True)
def _can_pay(card, pips, pip_count, generic, n_src, cover):
    """
    True if the card's cost can be paid by n_src distinct mana sources.

    Every pip needs its own source. The colored pips must be matched to
    distinct sources that can make one of their colors; by Hall's theorem that
    is possible iff every subset S of pips is covered by at least |S| sources
    that produce a color in the union of S's masks. Generic pips then take any
    of the remaining sources.
    """
    k = pip_count[card]
    if k + generic[card] > n_src:
        return False
    for subset in range(1, 1 << k):
        union = 0
        size = 0
        for p in range(k):
            if subset & (1 << p):
                union |= pips[card, p]
                size += 1
        if cover[union] < size:
            return False
    return True


@njit(cache=True)
def _collect_sources(
    deck_indices,
    start,
    seen,
    turn,
    is_land,
    is_ramp,
    costs,
    mana_produced,
    pips,
    pip_count,
    generic,
    src_masks,
    land_masks,
    cover,
):
    """
    Fills src_masks with the mana sources available on `turn`, where `seen`
    cards (from deck_indices[start]) have been drawn. Returns the count.

    Sources are every land drawn so far plus each ramp card that was already
    in hand on the previous turn and castable then from the lands drawn by
    that turn (ramp cost < turn). Casting the ramp is not charged against this
    turn's mana; it was paid for on an earlier turn.
    """
    n = 0
    for j in range(start, start + seen):
        idx = deck_indices[j]
        if is_land[idx] and n < MAX_SOURCES:
            src_masks[n] = mana_produced[idx]
            n += 1

    if turn < 2:
        return n

    prev_seen = seen - 1
    n_prev = 0
    for j in range(start, start + prev_seen):
        idx = deck_indices[j]
        if is_land[idx] and n_prev < MAX_SOURCES:
            land_masks[n_prev] = mana_produced[idx]
            n_prev += 1

    has_cover = False
    for j in range(start, start + prev_seen):
        idx = deck_indices[j]
        if is_ramp[idx] and costs[idx] < turn and n < MAX_SOURCES:
            if not has_cover:
                _fill_cover(land_masks, n_prev, cover)
                has_cover = True
            if _can_pay(idx, pips, pip_count, generic, n_prev, cover):
                src_masks[n] = mana_produced[idx]
                n += 1
    return n


@njit(cache=True)
def _castable_on_turn(
    deck_indices,
    start,
    seen,
    turn,
    is_land,
    is_ramp,
    costs,
    mana_produced,
    pips,
    pip_count,
    generic,
    src_masks,
    land_masks,
    cover,
):
    """
    Returns (has_drop, castable): whether a non-land card with mana value
    `turn` is in hand, and whether at least one such card can be cast on
    `turn` from the mana sources available then.
    """
    has_drop = False
    for j in range(start, start + seen):
        idx = deck_indices[j]
        if not is_land[idx] and costs[idx] == turn:
            has_drop = True
            break
    if not has_drop:
        return False, False

    n_src = _collect_sources(
        deck_indices,
        start,
        seen,
        turn,
        is_land,
        is_ramp,
        costs,
        mana_produced,
        pips,
        pip_count,
        generic,
        src_masks,
        land_masks,
        cover,
    )
    if n_src < turn:
        return True, False

    _fill_cover(src_masks, n_src, cover)
    for j in range(start, start + seen):
        idx = deck_indices[j]
        if not is_land[idx] and costs[idx] == turn:
            if _can_pay(idx, pips, pip_count, generic, n_src, cover):
                return True, True
    return True, False


@njit(cache=True)
def _run_fast_monte_carlo(
    is_land,
    is_ramp,
    is_removal,
    costs,
    mana_produced,
    pips,
    pip_count,
    generic,
    iterations,
):
    mulligans = 0
    screw_t3 = 0
    screw_t4 = 0
    flood_t5 = 0
    cast_t2 = 0
    cast_t3 = 0
    cast_t4 = 0
    curve_out = 0
    removal_t4 = 0
    color_screw_t3 = 0
    total_kept_cards = 0

    deck_indices = np.arange(DECK_SIZE)
    src_masks = np.zeros(MAX_SOURCES, dtype=np.int32)
    land_masks = np.zeros(MAX_SOURCES, dtype=np.int32)
    cover = np.zeros(32, dtype=np.int32)

    for _ in range(iterations):
        np.random.shuffle(deck_indices)

        mull_count = 0
        hand_idx = deck_indices[0:7]
        lands_in_hand = np.sum(is_land[hand_idx])

        if lands_in_hand < 2 or lands_in_hand > 5:
            mull_count = 1
            hand_idx = deck_indices[7:14]
            lands_in_hand = np.sum(is_land[hand_idx])
            if lands_in_hand < 2 or lands_in_hand > 4:
                mull_count = 2

        kept_size = 7 - mull_count
        total_kept_cards += kept_size
        if mull_count > 0:
            mulligans += 1

        start_ptr = mull_count * 7

        # Turn 3 & 4 & 5 States (on the play: one draw per turn from turn 2)
        t3_idx = deck_indices[start_ptr : start_ptr + kept_size + 2]
        t3_lands = np.sum(is_land[t3_idx])
        if t3_lands < 3:
            screw_t3 += 1

        t4_idx = deck_indices[start_ptr : start_ptr + kept_size + 3]
        if np.sum(is_land[t4_idx]) < 4:
            screw_t4 += 1
        if np.any(is_removal[t4_idx]):
            removal_t4 += 1

        t5_idx = deck_indices[start_ptr : start_ptr + kept_size + 4]
        if np.sum(is_land[t5_idx]) >= 6:
            flood_t5 += 1

        # Castability: each pip needs its own source of a matching color
        _, c2 = _castable_on_turn(
            deck_indices,
            start_ptr,
            kept_size + 1,
            2,
            is_land,
            is_ramp,
            costs,
            mana_produced,
            pips,
            pip_count,
            generic,
            src_masks,
            land_masks,
            cover,
        )
        has_3_drop, c3 = _castable_on_turn(
            deck_indices,
            start_ptr,
            kept_size + 2,
            3,
            is_land,
            is_ramp,
            costs,
            mana_produced,
            pips,
            pip_count,
            generic,
            src_masks,
            land_masks,
            cover,
        )
        _, c4 = _castable_on_turn(
            deck_indices,
            start_ptr,
            kept_size + 3,
            4,
            is_land,
            is_ramp,
            costs,
            mana_produced,
            pips,
            pip_count,
            generic,
            src_masks,
            land_masks,
            cover,
        )

        # Color screw: enough lands and a 3-drop in hand, but none castable
        if t3_lands >= 3 and has_3_drop and not c3:
            color_screw_t3 += 1

        if c2:
            cast_t2 += 1
        if c3:
            cast_t3 += 1
        if c4:
            cast_t4 += 1
        if c2 and c3 and c4:
            curve_out += 1

    return (
        mulligans,
        screw_t3,
        screw_t4,
        flood_t5,
        cast_t2,
        cast_t3,
        cast_t4,
        curve_out,
        removal_t4,
        color_screw_t3,
        total_kept_cards,
    )


def simulate_deck(deck_list, iterations=10000):
    arrays = _parse_deck_to_arrays(deck_list)
    if not arrays:
        return None

    results = _run_fast_monte_carlo(*arrays, iterations)

    return {
        "mulligans": (results[0] / iterations) * 100.0,
        "screw_t3": (results[1] / iterations) * 100.0,
        "screw_t4": (results[2] / iterations) * 100.0,
        "flood_t5": (results[3] / iterations) * 100.0,
        "cast_t2": (results[4] / iterations) * 100.0,
        "cast_t3": (results[5] / iterations) * 100.0,
        "cast_t4": (results[6] / iterations) * 100.0,
        "curve_out": (results[7] / iterations) * 100.0,
        "removal_t4": (results[8] / iterations) * 100.0,
        "color_screw_t3": (results[9] / iterations) * 100.0,
        "avg_hand_size": results[10] / iterations,
    }

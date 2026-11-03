"""Shared color-payment constraints, separate from a card's rules colors.

Each mandatory symbol is a set of alternatives: {G/U} is one requirement,
{G}{U} is two. Generic/Phyrexian alternatives do not force a deck color.
These are color feasibility/demand helpers, not a finite-source castability
test; the simulator matches individual pips to distinct mana sources.
"""

from functools import lru_cache
from itertools import combinations
import re

COLORS = "WUBRG"


@lru_cache(maxsize=4096)
def mana_symbols(cost):
    """Front-face symbols, with order-independent alternatives per symbol."""
    return tuple(frozenset(s.upper().split("/"))
                 for s in re.findall(r"\{(.*?)\}", str(cost or "").split("//")[0]))


def color_requirements(card):
    cost = card.get("mana_cost", "")
    if not cost:
        return tuple(frozenset([c]) for c in card.get("colors", []) if c in COLORS)
    return tuple(
        symbol.intersection(COLORS) for symbol in mana_symbols(cost)
        if symbol.intersection(COLORS)
        and not any(option.isdigit() or option == "P" for option in symbol)
    )


def off_color_requirements(card, colors):
    colors = set(colors)
    return tuple(options for options in color_requirements(card) if not options & colors)


def assign_mana_colors(cards, preferred_colors=()):
    """Choose one color per required pip without inventing hybrid splashes.

    Hard pips anchor the deck. Of only 32 possible color subsets, choose a
    cover of every hybrid symbol that adds the fewest unpreferred colors,
    then the fewest colors overall. Fixed WUBRG tie-breaking makes the result
    independent of spell order or whether a symbol is written G/U or U/G.
    This chooses a deck color plan, not the optimal land allocation.
    """
    requirements = [color_requirements(card) for card in cards]
    hard = {c for reqs in requirements for options in reqs
            if len(options) == 1 for c in options}
    preferred = set(preferred_colors).intersection(COLORS)
    flexible = [opts for reqs in requirements for opts in reqs if len(opts) > 1]
    covers = (
        set(subset) for n in range(6) for subset in combinations(COLORS, n)
        if hard <= set(subset) and all(set(subset) & opts for opts in flexible)
    )
    chosen = min(covers, key=lambda colors: (
        len(colors - hard - preferred), len(colors),
        tuple(COLORS.index(c) for c in COLORS if c in colors),
    ))
    demand = dict.fromkeys(COLORS, 0)
    for card, reqs in zip(cards, requirements):
        for options in reqs:
            if len(options) == 1:
                demand[next(iter(options))] += card.get("count", 1)
    assigned = []
    for reqs in requirements:
        assigned.append(tuple(max(
            (c for c in COLORS if c in options & chosen),
            key=lambda c: (demand[c], c in preferred, -COLORS.index(c)),
        ) for options in reqs))
    return assigned


def mana_color_demand(cards, preferred_colors=()):
    pips = dict.fromkeys(COLORS, 0)
    for card, assigned in zip(cards, assign_mana_colors(cards, preferred_colors)):
        for color in assigned:
            pips[color] += card.get("count", 1)
    return pips

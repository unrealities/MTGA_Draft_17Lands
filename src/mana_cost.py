"""Which colors a mana cost asks for, separate from a card's rules colors.

Each symbol is a set of payment options: {G/U} is one symbol that G or U can
pay, while {G}{U} is two. A symbol that generic mana ({2/U}) or life ({U/P})
can also pay is optional. It never makes a deck need its color, but in a deck
that already plays that color it still asks for sources of it.

These helpers decide color feasibility and land demand. They do not check
that a deck has enough sources to cast a card on a given turn.
"""

from functools import lru_cache
from itertools import combinations
import re

COLORS = "WUBRG"


@lru_cache(maxsize=4096)
def mana_symbols(cost):
    """Front-face symbols, each an order-independent set of options."""
    return tuple(frozenset(s.upper().split("/"))
                 for s in re.findall(r"\{(.*?)\}", str(cost or "").split("//")[0]))


def _colored_symbols(card):
    """(color options, optional) for each symbol that a color can pay."""
    cost = card.get("mana_cost", "")
    if not cost:
        # No printed cost: assume one solid pip of each listed color.
        return tuple((frozenset(c), False) for c in card.get("colors", []) if c in COLORS)
    return tuple(
        (symbol.intersection(COLORS), any(o.isdigit() or o == "P" for o in symbol))
        for symbol in mana_symbols(cost) if symbol.intersection(COLORS)
    )


def color_requirements(card):
    """Symbols that some color must pay: AND across symbols, OR within one."""
    return tuple(options for options, optional in _colored_symbols(card) if not optional)


def off_color_requirements(card, colors):
    colors = set(colors)
    return tuple(options for options in color_requirements(card) if not options & colors)


def assign_mana_colors(cards, preferred_colors=()):
    """The color that pays each colored symbol, per card, in one deck plan.

    Solid pips fix their colors. Hybrid symbols that those don't cover get
    the fewest colors outside the preferred ones, then the fewest colors; all
    32 subsets of WUBRG are checked so the result does not depend on card
    order. Each symbol is paid with a preferred color when it can be, then
    with the color that has the most solid pips. Optional symbols count only
    when the plan already has one of their colors.
    """
    symbols = [_colored_symbols(card) for card in cards]
    required = [options for syms in symbols for options, optional in syms if not optional]
    preferred = set(preferred_colors).intersection(COLORS)
    solid = {c for options in required if len(options) == 1 for c in options}
    # combinations() yields WUBRG order, so min() breaks ties consistently.
    covers = (
        set(subset) for n in range(len(COLORS) + 1) for subset in combinations(COLORS, n)
        if solid <= set(subset) and all(options & set(subset) for options in required)
    )
    plan = min(covers, key=lambda s: (len(s - preferred), len(s))) | preferred

    solid_pips = dict.fromkeys(COLORS, 0)
    for card, syms in zip(cards, symbols):
        for options, optional in syms:
            if len(options) == 1 and not optional:
                solid_pips[next(iter(options))] += card.get("count", 1)

    def pay(options):
        return max(options & plan,
                   key=lambda c: (c in preferred, solid_pips[c], -COLORS.index(c)))

    return [tuple(pay(options) for options, optional in syms
                  if not optional or options & plan)
            for syms in symbols]


def mana_color_demand(cards, preferred_colors=()):
    """Colored pips per color, counting copies, under assign_mana_colors."""
    pips = dict.fromkeys(COLORS, 0)
    for card, assigned in zip(cards, assign_mana_colors(cards, preferred_colors)):
        for color in assigned:
            pips[color] += card.get("count", 1)
    return pips

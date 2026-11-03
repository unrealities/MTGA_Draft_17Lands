# Hybrid mana: payment choices and color demand

A card's rules colors are not a list of required mana sources. Do not change
`card["colors"]` to repair payment logic. A `{G/U}` card remains green and blue
even in a deck that casts it using only Forests.

## Shared contract

`src/mana_cost.py` parses front-face symbols and exposes mandatory colored
requirements. Requirements combine with AND; options within a symbol combine
with OR. Thus `{G/U}` needs one of those colors, while `{G}{U}` needs both.
`{2/U}` has a generic route and does not force blue sources. A missing printed
cost retains the existing conservative fallback to the card's listed colors.

- **Color feasibility and lane bonuses:** every mandatory symbol must have
  an option in the lane. A playable hybrid receives the same on-color treatment
  as an equivalent spell with a solid pip.
- **Splash feasibility:** every remaining symbol must have an option supported
  by the fixing map. `{U/R}` can use red fixing; `{G/U}{B}` in green still needs
  black fixing. Neither the presence of a slash nor unrelated fixing is enough.
  The existing splash multipliers remain heuristics, not cast probabilities.
- **Mana allocation and deck labels:** use hard pips as anchors and choose a
  cover of hybrid requirements among the 32 possible color subsets. Prefer
  existing/declared colors before introducing new ones, then minimize the
  number of colors. WUBRG breaks ties consistently. Count each symbol once,
  including stacked copies. This is a color-plan heuristic; it does not claim
  to find the probability-optimal mana base.
- **Simulation:** preserve all colored alternatives in each pip's mask and
  match pips to distinct sources. For `{2/U}`, enumerate one-blue vs two-generic
  payments and reserve those sources before considering the rest of the cost.
  Keep printed mana value for ordinary curve slots; two-brid spells can also
  occupy their cheaper payment slots. Ramp deployment charges the selected
  payment's mana, rather than always charging printed mana value.

The simulator still approximates dedicated colorless/snow payments as generic
and does not model paying life for Phyrexian symbols. The shared color helpers
are color-feasibility helpers, not a complete Magic cost/payment engine. Color
affinity used to discover draft lanes remains a separate statistical heuristic.

## Earlier implementations

- [PR #146](https://github.com/unrealities/MTGA_Draft_17Lands/pull/146), merged:
  introduced resolving hybrids toward core colors and `get_strict_colors()`.
  The latter was a good direction, but its greedy choice depended on spell
  order; `{W/U}` followed by `{U/B}` could select two colors when blue alone
  suffices.
- [PR #171](https://github.com/unrealities/MTGA_Draft_17Lands/pull/171), merged:
  retained several independent parsers. Its mana allocator skips a symbol only
  when all alternatives are numeric/X/C, so `{2/U}` still forced blue sources.
- [PR #204](https://github.com/unrealities/MTGA_Draft_17Lands/pull/204), merged:
  the best existing foundation for actual payment. It retained both hybrid
  options and used Hall's matching condition so a dual land cannot pay two
  symbols. This change keeps that approach and adds two-generic alternatives.
- [PR #223](https://github.com/unrealities/MTGA_Draft_17Lands/pull/223), closed,
  unmerged: recognized generic/life alternatives in advisor castability and
  extracted shared deck-label helpers. But its label helper still counted
  both hybrid halves. Its `_has_hybrid_route()` splash exception checked for
  one off-color hybrid symbol without checking for a fixing source, so it is
  not a safe implementation to copy wholesale.

Regression coverage is in `tests/test_hybrid_mana.py`: lane parity, supported
and unsupported splashes, real gold costs, two-brid allocation/payment, deck
labels and score features, copy/order invariance, and 1,008 comparisons of the
simulator's payment matcher with independent exhaustive source assignment.

Rules basis: [Comprehensive Rules, 107.4e and 202.2](https://media.wizards.com/2025/downloads/MagicCompRules%2020251114.pdf).

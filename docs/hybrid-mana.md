# Hybrid mana: payment choices and color demand

A card's rules colors are not a list of required mana sources. Do not change
`card["colors"]` to repair payment logic. A `{G/U}` card remains green and blue
even in a deck that casts it using only Forests.

## Shared contract

`src/mana_cost.py` reads the front face of a printed cost. Symbols combine
with AND; options within a symbol combine with OR. Thus `{G/U}` needs one of
those colors, while `{G}{U}` needs both. A card with no printed cost falls back
to one solid pip of each listed color.

A symbol that generic mana (`{2/U}`) or life (`{U/P}`) can also pay is
*optional*:

- **Castability, lanes and splashes** ignore it. `{2/U}` is castable in a
  mono-red deck.
- **Land demand** counts it when the deck already plays that color, so a
  W/U deck full of `{U/P}` still gets Islands, and a mono-green deck with
  `{2/U}` does not.

Uses:

- **Color feasibility and lane bonuses:** every required symbol must have an
  option in the lane. A playable hybrid gets the same on-color treatment as an
  equivalent spell with a solid pip.
- **Splash feasibility:** every off-color symbol must have an option the
  fixing supports. `{U/R}` can use red fixing; `{G/U}{B}` in green still
  needs black fixing. The greedy builder's double-pip splash requires mana
  value 5 or greater and at least two fixing sources for that color. Previously
  it counted the same sources twice against a threshold of three; the new
  check counts them once and retains the two-source minimum.
- **Mana allocation and deck labels:** solid pips fix their colors. Hybrid
  symbols they don't cover get the fewest colors outside the declared deck
  colors, then the fewest colors; all 32 subsets of WUBRG are checked, so card
  order and `G/U` vs `U/G` don't matter. Each symbol is then paid with a
  declared color when it can be, then the color with the most solid pips.
  This picks a color plan, not the probability-optimal mana base.

## Not covered

The Monte Carlo simulator is unchanged: it keeps both hybrid options per pip
and matches pips to distinct sources (PR #204), but counts `{2/U}` as two
generic mana, never as one blue. It treats `{C}` and snow as generic and does
not model paying life. Color affinity used to discover draft lanes is a
separate statistical heuristic.

## Earlier implementations

- [PR #146](https://github.com/unrealities/MTGA_Draft_17Lands/pull/146), merged:
  introduced resolving hybrids toward core colors and `get_strict_colors()`.
  Its greedy choice depended on spell order; `{W/U}` followed by `{U/B}`
  could select two colors when blue alone suffices.
- [PR #171](https://github.com/unrealities/MTGA_Draft_17Lands/pull/171), merged:
  kept several independent parsers. Its mana allocator skipped a symbol only
  when all options were numeric/X/C, so `{2/U}` still forced blue sources.
- [PR #204](https://github.com/unrealities/MTGA_Draft_17Lands/pull/204), merged:
  the simulator's distinct-source payment matching described above.
- [PR #223](https://github.com/unrealities/MTGA_Draft_17Lands/pull/223), closed:
  recognized generic/life options in castability, but its label helper still
  counted both hybrid halves, and its splash exception accepted an off-color
  hybrid without checking for a fixing source.

Regression coverage is in `tests/test_hybrid_mana.py`.

Rules basis: [Comprehensive Rules, 107.4e and 202.2](https://media.wizards.com/2025/downloads/MagicCompRules%2020251114.pdf).

# Pair parts at `6e48023`

716435 decks and 3293757 games from 20 sets; 167 color-pair-by-set terms.

## Weights

A part's slope over the overall rating's. The engine assumes 0.95; 0 is no blend. Set-clustered 95% intervals.

| part | model | weight |
|---|---|---|
| fit (primary) | with pair terms | +1.29 [+1.20, +1.39] |
| fit | no pair terms | +1.49 [+1.31, +1.66] |
| level | no pair terms | -0.23 [-0.38, -0.08] |

## Held-out log loss

Gain over the overall rating with the same terms, in millinats a game, with 1.96 per-draft SEs. Positive: predicts better than no blend.

| rating | no pair terms | with pair terms |
|---|---|---|
| the engine's rating | -0.448 [-0.477, -0.419] | +0.456 [+0.433, +0.479] |
| fit only (0.95 x fit) | +0.346 [+0.328, +0.363] | +0.464 [+0.440, +0.487] |
| level only (0.95 x level) | -0.661 [-0.688, -0.633] | – |
| free slopes | +0.486 [+0.456, +0.516] | +0.492 [+0.462, +0.522] |

**By the protocol's rule: the level explains it.**

## Not deciding

Fit's weight with pair terms:

| decks or cards | weight |
|---|---|
| cards under 3,000 games in the pair | +0.95 [+0.84, +1.06] |
| cards from 3,000 games in the pair | +1.49 [+1.34, +1.63] |
| strong drafters | +1.26 [+1.14, +1.38] |
| the rest | +1.31 [+1.22, +1.41] |

## By set

Model SEs. Level is fit with no pair terms; fit, with them.

| set | decks | fit (± SE) | level (± SE) |
|---|---|---|---|
| BLB | 46397 | +1.10 ± 0.06 | -0.54 ± 0.04 |
| Cube_-_Powered | 131 | – | – |
| DFT | 42455 | +1.18 ± 0.08 | -0.59 ± 0.05 |
| DMU | 26632 | +1.14 ± 0.11 | +0.33 ± 0.05 |
| DSK | 43290 | +1.32 ± 0.08 | -0.03 ± 0.03 |
| EOE | 45090 | +1.11 ± 0.13 | -0.03 ± 0.04 |
| FDN | 45531 | +1.18 ± 0.11 | -0.27 ± 0.04 |
| FIN | 41438 | +1.33 ± 0.11 | -0.36 ± 0.04 |
| FRA | 38768 | +1.21 ± 0.10 | -0.38 ± 0.05 |
| HOB | 46588 | +1.42 ± 0.12 | -0.00 ± 0.04 |
| LTR | 43828 | +1.57 ± 0.08 | -0.76 ± 0.04 |
| MH3 | 25897 | +1.46 ± 0.11 | -0.09 ± 0.04 |
| MSH | 42086 | +1.16 ± 0.11 | -0.63 ± 0.04 |
| NEO | 43772 | +1.08 ± 0.09 | -0.33 ± 0.04 |
| OTJ | 37947 | +1.25 ± 0.10 | -0.44 ± 0.05 |
| PIO | 32891 | +1.45 ± 0.13 | -0.27 ± 0.08 |
| SOS | 38669 | +1.81 ± 0.13 | -0.33 ± 0.07 |
| TDM | 10479 | +1.11 ± 0.19 | +0.76 ± 0.12 |
| TLA | 37906 | +1.27 ± 0.11 | -0.34 ± 0.05 |
| TMT | 26640 | +1.33 ± 0.14 | +0.06 ± 0.05 |

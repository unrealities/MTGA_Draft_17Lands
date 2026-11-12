# Card ratings at `39a1a78`

716435 decks and 3293757 games from 20 sets; held-out log loss per game, 5 folds. Intervals are 98.33%.

Card quality is worth 1.63 [1.56, 1.70] millinats a game: the engine's version against no card quality at all.

## Primary results

Gain: how much better the engine's version predicts than the ablation, in millinats a game (positive: the engine's is better) and as a share of what card quality is worth.

| what the engine does | ablation | gain (millinats a game) | share of card quality's worth | verdict |
|---|---|---|---|---|
| Archetype weighting | `no-archetype` | -0.439 [-0.473, -0.404] | -26.9% [-29.1%, -24.8%] | ablation predicts better |
| Shrinkage | `no-shrinkage` | +0.017 [+0.008, +0.025] | +1.0% [+0.5%, +1.6%] | engine's predicts better |
| IWD premium | `no-iwd` | +0.033 [+0.031, +0.034] | +2.0% [+1.9%, +2.1%] | engine's predicts better |

## Other versions

Not used for a verdict. Gain of the engine's version over each.

| version | gain (millinats a game) | share of card quality's worth |
|---|---|---|
| blend weight 0.65 (engine's at pick 1) | -0.173 [-0.182, -0.165] | -10.6% |
| blend weight 1.3 (engine's from pick 15) | +0.185 [+0.176, +0.193] | +11.3% |
| no power bonus | +0.294 [+0.282, +0.307] | +18.1% |
| overall GIH WR alone | -0.257 [-0.291, -0.223] | -15.8% |
| the deck score's blend (0.7 pair, 0.3 overall) | +0.149 [+0.136, +0.162] | +9.1% |

## By set

Gain of the engine's version over each ablation, in millinats a game (± SE).

| set | decks | card quality's worth | `no-archetype` | `no-shrinkage` | `no-iwd` |
|---|---|---|---|---|---|
| BLB | 46397 | 1.51 | -0.562 ± 0.056 | -0.026 ± 0.008 | +0.025 ± 0.002 |
| Cube_-_Powered | 131 | -0.66 | +2.756 ± 1.150 | -0.590 ± 0.408 | +0.033 ± 0.042 |
| DFT | 42455 | 1.26 | -0.344 ± 0.057 | -0.014 ± 0.009 | +0.030 ± 0.002 |
| DMU | 26632 | 1.93 | +0.009 ± 0.096 | +0.030 ± 0.015 | +0.025 ± 0.003 |
| DSK | 43290 | 2.22 | -0.562 ± 0.061 | +0.023 ± 0.009 | +0.047 ± 0.003 |
| EOE | 45090 | 1.47 | -0.521 ± 0.061 | +0.024 ± 0.009 | +0.030 ± 0.002 |
| FDN | 45531 | 1.65 | -0.731 ± 0.052 | +0.026 ± 0.008 | +0.031 ± 0.002 |
| FIN | 41438 | 1.47 | -0.658 ± 0.058 | +0.010 ± 0.010 | +0.035 ± 0.002 |
| FRA | 38768 | 1.17 | -0.417 ± 0.059 | +0.031 ± 0.014 | +0.034 ± 0.003 |
| HOB | 46588 | 1.55 | -0.395 ± 0.054 | +0.040 ± 0.017 | +0.038 ± 0.002 |
| LTR | 43828 | 1.37 | -0.504 ± 0.054 | -0.004 ± 0.008 | +0.032 ± 0.003 |
| MH3 | 25897 | 2.51 | -0.556 ± 0.083 | -0.029 ± 0.015 | +0.049 ± 0.004 |
| MSH | 42086 | 1.50 | -0.600 ± 0.055 | +0.015 ± 0.012 | +0.036 ± 0.002 |
| NEO | 43772 | 1.90 | -0.751 ± 0.065 | +0.011 ± 0.010 | +0.045 ± 0.003 |
| OTJ | 37947 | 1.92 | -0.431 ± 0.055 | +0.032 ± 0.010 | +0.032 ± 0.003 |
| PIO | 32891 | 1.12 | +0.358 ± 0.075 | +0.026 ± 0.020 | -0.006 ± 0.003 |
| SOS | 38669 | 1.89 | -0.083 ± 0.057 | -0.005 ± 0.018 | +0.036 ± 0.002 |
| TDM | 10479 | 1.75 | +0.880 ± 0.178 | +0.052 ± 0.066 | +0.018 ± 0.005 |
| TLA | 37906 | 1.51 | -0.568 ± 0.056 | +0.014 ± 0.011 | +0.038 ± 0.002 |
| TMT | 26640 | 1.67 | -0.555 ± 0.088 | +0.121 ± 0.061 | +0.035 ± 0.003 |

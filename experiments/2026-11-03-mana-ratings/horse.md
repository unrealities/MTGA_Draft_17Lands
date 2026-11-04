# Ratings at `067c22f`

914784 decks and 4138617 games from 20 sets; held-out log loss per game, 5 folds. Intervals are 98.33%.

Card quality is worth 1.63 [1.57, 1.69] millinats a game: the engine's version against no card quality at all.

## Primary results

Gain: how much better the engine's version predicts than the ablation, in millinats a game (positive: the engine's is better) and as a share of what card quality is worth.

| what the engine does | ablation | gain (millinats a game) | share of card quality's worth | verdict |
|---|---|---|---|---|
| Archetype weighting | `no-archetype` | -0.434 [-0.472, -0.397] | -26.7% [-29.0%, -24.4%] | drop |
| Shrinkage | `no-shrinkage` | +0.140 [+0.122, +0.158] | +8.6% [+7.5%, +9.7%] | keep |
| IWD premium | `no-iwd` | +0.034 [+0.033, +0.036] | +2.1% [+2.0%, +2.2%] | keep |

## Other versions

Not used for a verdict. Gain of the engine's version over each.

| version | gain (millinats a game) | share of card quality's worth |
|---|---|---|
| blend weight 0.65 (engine's at pick 1) | -0.203 [-0.213, -0.194] | -12.5% |
| blend weight 1.3 (engine's from pick 15) | +0.214 [+0.206, +0.223] | +13.2% |
| no power bonus | +0.321 [+0.309, +0.333] | +19.7% |
| overall GIH WR alone | -0.257 [-0.294, -0.220] | -15.8% |
| the deck score's blend (0.7 pair, 0.3 overall) | +0.264 [+0.244, +0.284] | +16.2% |

## By set

Gain of the engine's version over each ablation, in millinats a game (± SE).

| set | decks | card quality's worth | `no-archetype` | `no-shrinkage` | `no-iwd` |
|---|---|---|---|---|---|
| BLB | 49985 | 1.55 | -0.467 ± 0.064 | +0.094 ± 0.031 | +0.025 ± 0.002 |
| Cube_-_Powered | 240 | 2.36 | +1.609 ± 1.263 | -0.204 ± 0.511 | +0.026 ± 0.031 |
| DFT | 49987 | 1.25 | -0.452 ± 0.069 | +0.077 ± 0.024 | +0.032 ± 0.002 |
| DMU | 49971 | 1.71 | -0.365 ± 0.081 | +0.087 ± 0.023 | +0.029 ± 0.002 |
| DSK | 49994 | 2.14 | -0.678 ± 0.071 | +0.199 ± 0.027 | +0.051 ± 0.003 |
| EOE | 49975 | 1.50 | -0.512 ± 0.061 | +0.160 ± 0.031 | +0.031 ± 0.002 |
| FDN | 49984 | 1.67 | -0.573 ± 0.062 | +0.216 ± 0.031 | +0.030 ± 0.002 |
| FIN | 49955 | 1.56 | -0.622 ± 0.067 | +0.189 ± 0.029 | +0.036 ± 0.002 |
| FRA | 49990 | 1.33 | -0.481 ± 0.055 | +0.132 ± 0.031 | +0.035 ± 0.002 |
| HOB | 49994 | 1.58 | -0.319 ± 0.057 | +0.167 ± 0.034 | +0.037 ± 0.002 |
| LTR | 49995 | 1.35 | -0.439 ± 0.065 | -0.014 ± 0.025 | +0.031 ± 0.003 |
| MH3 | 34923 | 2.43 | -0.523 ± 0.097 | -0.014 ± 0.034 | +0.047 ± 0.004 |
| MSH | 49990 | 1.51 | -0.487 ± 0.062 | +0.074 ± 0.029 | +0.035 ± 0.002 |
| NEO | 49977 | 1.91 | -0.620 ± 0.072 | +0.251 ± 0.037 | +0.046 ± 0.003 |
| OTJ | 49982 | 1.90 | -0.437 ± 0.068 | +0.081 ± 0.024 | +0.034 ± 0.002 |
| PIO | 45410 | 1.28 | +0.183 ± 0.070 | +0.162 ± 0.047 | +0.001 ± 0.003 |
| SOS | 49945 | 1.89 | -0.137 ± 0.068 | +0.209 ± 0.031 | +0.039 ± 0.002 |
| TDM | 49976 | 1.38 | -0.184 ± 0.066 | -0.013 ± 0.029 | +0.036 ± 0.003 |
| TLA | 49986 | 1.53 | -0.533 ± 0.073 | +0.192 ± 0.032 | +0.040 ± 0.002 |
| TMT | 34525 | 1.66 | -0.637 ± 0.082 | +0.479 ± 0.070 | +0.037 ± 0.003 |

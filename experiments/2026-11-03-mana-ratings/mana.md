# Mana luck at `067c22f`

798355 decks and 3657022 games from 19 sets; 3243502 games (88.7%) are 7-card keeps with the hand in the deck. Intervals are 98.75%.

Left out: DMU, whose dump records mulligans in 0.14% of games (under 2%), so its mulligans pass as 7-card keeps.

## Primary results

Value: what a point of `simulate_deck()`'s rate costs, in deck score points, from the event's cost within decks and how far the rate moves the real chance in kept hands. The penalty: its points per point of rate past its threshold.

| penalty | ablation | cost of the event (win rate points) | real chance per simulated point | value (score points per point) | penalty | decks past it | keep or drop |
|---|---|---|---|---|---|---|---|
| Color Screw | `no-mc-color` | -14.1 [-16.3, -11.9] | +1.00 [+0.98, +1.03] | -0.17 [-0.20, -0.14] | -2.5 past 10% | 47816 | drop |
| Mana Screw | `no-mc-screw` | -19.2 [-22.0, -16.3] | +1.62 [+1.52, +1.72] | -0.37 [-0.45, -0.30] | -1.5 past 22% | 531 | drop |
| Flood Risk | `no-mc-flood` | -13.2 [-14.5, -11.9] | +1.18 [+1.14, +1.23] | -0.19 [-0.22, -0.16] | -1.5 past 27% | 609650 | drop |
| All three | `no-mc-all` | | | -0.38 [-0.44, -0.33] | -3.37 on average | 617424 | drop |

Card quality: 0.358 log-odds per unit (12 score points).

## Calibration

Lands in a 7-card keep: share of keeps, against random 7s from the same decks and random 7s the simulator would keep (2 to 5 lands).

| lands | kept | random | simulator's keeps |
|---|---|---|---|
| 0 | 0.0% | 1.4% | 0.0% |
| 1 | 0.1% | 9.7% | 0.0% |
| 2 | 23.4% | 25.1% | 28.8% |
| 3 | 57.5% | 32.2% | 36.9% |
| 4 | 18.7% | 22.0% | 25.2% |
| 5 | 0.3% | 8.0% | 9.2% |
| 6 | 0.0% | 1.4% | 0.0% |
| 7 | 0.0% | 0.1% | 0.0% |

Rates in percent: real (mulligans in games; events as the mean chance in kept hands), the simulator's in its own 7-card keeps, and `simulate_deck()`'s, which the penalties read.

| sets | mulligans: real / sim | screw: real / sim keeps / sim | flood: real / sim keeps / sim | color screw: real / sim keeps / sim |
|---|---|---|---|---|
| all sets | 11.3 / 12.8 | 7.1 / 8.6 / 10.0 | 21.3 / 28.3 / 27.2 | 3.6 / 4.1 / 4.2 |
| BLB | 12.9 / 12.9 | 7.2 / 8.7 / 10.1 | 20.9 / 28.1 / 27.0 | 2.7 / 3.2 / 3.3 |
| Cube_-_Powered | 10.2 / 14.8 | 9.0 / 10.2 / 11.7 | 16.0 / 24.5 / 23.3 | 5.0 / 6.0 / 6.2 |
| DFT | 10.9 / 12.7 | 6.9 / 8.5 / 9.9 | 21.4 / 28.5 / 27.4 | 3.4 / 4.0 / 4.1 |
| DSK | 11.3 / 13.0 | 7.5 / 8.8 / 10.2 | 20.4 / 27.7 / 26.6 | 3.9 / 4.5 / 4.5 |
| EOE | 11.9 / 12.5 | 6.7 / 8.4 / 9.8 | 21.8 / 28.8 / 27.6 | 2.5 / 3.2 / 3.3 |
| FDN | 11.8 / 12.8 | 7.0 / 8.6 / 10.0 | 21.2 / 28.3 / 27.1 | 3.9 / 4.5 / 4.5 |
| FIN | 11.1 / 12.7 | 7.0 / 8.6 / 9.9 | 21.4 / 28.4 / 27.3 | 3.2 / 3.7 / 3.8 |
| FRA | 9.2 / 12.8 | 7.2 / 8.6 / 10.0 | 21.0 / 28.2 / 27.1 | 4.1 / 4.4 / 4.5 |
| HOB | 9.8 / 12.7 | 7.1 / 8.6 / 9.9 | 21.2 / 28.4 / 27.3 | 2.7 / 3.1 / 3.2 |
| LTR | 12.0 / 14.5 | 9.9 / 10.1 / 11.5 | 17.2 / 24.8 / 23.7 | 3.4 / 4.1 / 4.2 |
| MH3 | 12.2 / 11.5 | 5.4 / 7.4 / 8.7 | 26.6 / 32.2 / 31.0 | 7.6 / 7.9 / 8.0 |
| MSH | 9.6 / 12.9 | 7.3 / 8.7 / 10.1 | 20.8 / 28.1 / 27.0 | 2.4 / 2.9 / 2.9 |
| NEO | 10.2 / 13.2 | 7.7 / 8.9 / 10.3 | 20.1 / 27.4 / 26.3 | 2.9 / 3.3 / 3.3 |
| OTJ | 11.4 / 12.4 | 6.4 / 8.3 / 9.7 | 22.2 / 29.0 / 27.9 | 3.7 / 4.4 / 4.5 |
| PIO | 11.7 / 12.1 | 6.2 / 7.9 / 9.3 | 24.5 / 30.5 / 29.3 | 4.0 / 4.8 / 4.9 |
| SOS | 13.0 / 12.6 | 6.6 / 8.4 / 9.8 | 21.9 / 28.7 / 27.6 | 3.9 / 4.9 / 4.9 |
| TDM | 12.6 / 12.8 | 7.0 / 8.6 / 10.0 | 21.3 / 28.2 / 27.0 | 5.4 / 6.1 / 6.1 |
| TLA | 10.8 / 12.8 | 7.1 / 8.6 / 10.0 | 21.0 / 28.3 / 27.1 | 2.7 / 3.2 / 3.2 |
| TMT | 10.8 / 12.8 | 7.2 / 8.6 / 10.0 | 21.0 / 28.2 / 27.1 | 2.8 / 3.3 / 3.3 |

## Win rate by lands in hand

Within decks, against keeps with 3 lands, in win rate points.

| lands in a 7-card keep | keeps | win rate against 3 |
|---|---|---|
| 0-1 | 3012 | -10.2 [-16.7, -3.6] |
| 2 | 758797 | -3.8 [-4.4, -3.2] |
| 3 | 1863739 | (reference) |
| 4 | 607421 | -4.0 [-4.4, -3.6] |
| 5 | 10507 | -12.1 [-14.3, -10.0] |
| 6-7 | 26 | -7.4 [-40.5, +25.7] |

## By set

Cost of each event within decks, in win rate points.

| set | keeps | screw | flood | color screw |
|---|---|---|---|---|
| BLB | 195708 | -18.1 ± 1.2 | -14.0 ± 1.0 | -15.2 ± 1.4 |
| Cube_-_Powered | 1040 | -22.9 ± 14.0 | +8.8 ± 17.2 | +6.0 ± 14.3 |
| DFT | 190135 | -27.1 ± 1.3 | -16.3 ± 1.0 | -18.2 ± 1.2 |
| DSK | 190402 | -20.5 ± 1.2 | -16.6 ± 1.1 | -13.9 ± 1.2 |
| EOE | 177400 | -19.7 ± 1.4 | -14.4 ± 1.1 | -19.1 ± 1.5 |
| FDN | 194452 | -18.3 ± 1.3 | -15.0 ± 1.0 | -13.0 ± 1.1 |
| FIN | 184505 | -19.2 ± 1.3 | -12.7 ± 1.0 | -14.2 ± 1.3 |
| FRA | 179683 | -17.7 ± 1.3 | -9.4 ± 1.1 | -11.6 ± 1.2 |
| HOB | 194101 | -24.3 ± 1.3 | -16.1 ± 1.0 | -15.9 ± 1.4 |
| LTR | 193554 | -10.9 ± 1.1 | -12.7 ± 1.2 | -15.4 ± 1.2 |
| MH3 | 133799 | -20.4 ± 1.7 | -12.3 ± 1.0 | -6.9 ± 0.9 |
| MSH | 190342 | -20.3 ± 1.3 | -14.0 ± 1.0 | -17.4 ± 1.5 |
| NEO | 192114 | -13.2 ± 1.2 | -15.3 ± 1.1 | -13.8 ± 1.3 |
| OTJ | 193853 | -22.4 ± 1.3 | -13.7 ± 1.0 | -17.0 ± 1.2 |
| PIO | 167696 | -19.4 ± 1.4 | -10.3 ± 1.0 | -16.3 ± 1.2 |
| SOS | 175243 | -21.0 ± 1.4 | -11.5 ± 1.1 | -14.3 ± 1.2 |
| TDM | 174310 | -18.5 ± 1.3 | -12.7 ± 1.1 | -11.4 ± 1.0 |
| TLA | 184649 | -24.0 ± 1.3 | -13.0 ± 1.1 | -15.5 ± 1.4 |
| TMT | 130516 | -18.9 ± 1.5 | -10.0 ± 1.2 | -15.3 ± 1.6 |

## Deck-level fit

Not used for the verdict. Games won on each rate past its threshold, with fit.py's controls, in score points per point of rate.

| penalty | value | penalty | keep or drop |
|---|---|---|---|
| Color Screw | -0.32 [-0.52, -0.13] | -2.5 | drop |
| Mana Screw | +0.22 [-0.85, +1.29] | -1.5 | can't tell |
| Flood Risk | -0.34 [-0.61, -0.07] | -1.5 | drop |

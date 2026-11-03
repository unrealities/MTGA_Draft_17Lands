# Rule targets at `3d945ee`

## Data

914784 decks and 4138617 games from 20 sets (BLB, Cube_-_Powered, DFT, DMU, DSK, EOE, FDN, FIN, FRA, HOB, LTR, MH3, MSH, NEO, OTJ, PIO, SOS, TDM, TLA, TMT); game win rate 55.4%. 16828 unfinished decks were left out.

Cards tagged by the app, per set (the rules see only tagged cards):

| set | removal | fixing_ramp |
|---|---|---|
| BLB | 59 | 21 |
| Cube_-_Powered | 0 | 0 |
| DFT | 52 | 19 |
| DMU | 58 | 17 |
| DSK | 64 | 16 |
| EOE | 63 | 29 |
| FDN | 51 | 18 |
| FIN | 54 | 33 |
| FRA | 73 | 21 |
| HOB | 32 | 21 |
| LTR | 61 | 27 |
| MH3 | 69 | 50 |
| MSH | 54 | 13 |
| NEO | 75 | 18 |
| OTJ | 60 | 30 |
| PIO | 100 | 22 |
| SOS | 54 | 21 |
| TDM | 55 | 15 |
| TLA | 53 | 41 |
| TMT | 42 | 10 |

## Primary results

Per card, in game win rate points (at the overall win rate), with 98.33% intervals: 95% familywise across the three rules. Each SE is the larger of the model's (widened for overdispersion) and the set-clustered one. *Rating SDs*: the same effect as a change in that card's rating, in the format's SDs of GIH WR. *The rule's size*: what the rule's multiplier does to a card's score, in the same units.

| rule | tested claim | sets | decks in region | per card (points) | interval | rating SDs | the rule's size | verdict |
|---|---|---|---|---|---|---|---|---|
| Removal Saturated (0.8x past 6) | a removal spell past the sixth is worth less than a spell of the same rating | 19 | 402956 (44.1%) | +0.09 | [-0.04, +0.23] | +0.24 ± 0.15 | -0.87 | not established |
| Curve Too Heavy (0.7x past 4) | a 5+ mana spell past the fourth is worth less than a spell of the same rating | 20 | 209837 (22.9%) | -0.09 | [-0.26, +0.08] | -0.24 ± 0.18 | -1.30 | not established |
| Critical: Needs Fixing (1.4x) | in decks with off-color spells, a fixing card is worth more while fixing is no more than the off-color spells | 20 | 177579 (19.4%) | -0.04 | [-0.31, +0.22] | -0.11 ± 0.28 | +1.33 | not established |

*Supported*: the interval excludes zero in the rule's direction. *Contradicted*: it excludes zero the other way. *Not established*: it includes zero.

## Uncertainty and sensitivity

Per card, in game win rate points (SE). *Model* and *set-clustered* SEs of the primary fit; *with counts*: lands, creatures and colors added as controls; *strong drafters*: skill bucket 58% or more.

| rule | primary | model SE | set-clustered SE | with counts | strong drafters |
|---|---|---|---|---|---|
| Removal Saturated (0.8x past 6) | +0.09 | 0.02 | 0.06 | +0.20 (0.05) | +0.11 (0.06) |
| Curve Too Heavy (0.7x past 4) | -0.09 | 0.03 | 0.07 | -0.04 (0.06) | -0.03 (0.08) |
| Critical: Needs Fixing (1.4x) | -0.04 | 0.04 | 0.11 | +0.05 (0.09) | -0.08 (0.12) |

## Other contrasts

Per card, in game win rate points (SE), from the primary fit.

| rule | contrast | per card |
|---|---|---|
| Removal Saturated (0.8x past 6) | removal up to the sixth | +0.23 (0.05) |
| Removal Saturated (0.8x past 6) | change in slope past the sixth | -0.14 (0.06) |
| Curve Too Heavy (0.7x past 4) | 5+ drops up to the fourth | +0.01 (0.06) |
| Curve Too Heavy (0.7x past 4) | change in slope past the fourth | -0.11 (0.11) |
| Critical: Needs Fixing (1.4x) | fixing card while short | +0.13 (0.10) |
| Critical: Needs Fixing (1.4x) | fixing card once not short | +0.17 (0.05) |
| Critical: Needs Fixing (1.4x) | fixing card in a deck with no off-color spells | +0.18 (0.05) |

## By set

The primary estimate fit on each set alone, per card in game win rate points. Sets with fewer than 100 decks in the rule's region are marked –.

| set | Removal Saturated (0.8x past 6) | Curve Too Heavy (0.7x past 4) | Critical: Needs Fixing (1.4x) |
|---|---|---|---|
| BLB | +0.27 (0.07) | -0.56 (0.24) | +0.68 (0.34) |
| Cube_-_Powered | – | – | +2.30 (2.33) |
| DFT | +0.10 (0.08) | +0.28 (0.11) | +0.01 (0.22) |
| DMU | +0.36 (0.08) | -0.02 (0.17) | +0.27 (0.15) |
| DSK | +0.09 (0.07) | -0.11 (0.07) | -0.01 (0.22) |
| EOE | -0.05 (0.08) | -0.41 (0.11) | -0.20 (0.24) |
| FDN | +0.17 (0.08) | -0.30 (0.17) | -0.35 (0.29) |
| FIN | -0.03 (0.07) | +0.44 (0.12) | -0.05 (0.19) |
| FRA | +0.36 (0.06) | +0.37 (0.25) | -0.20 (0.20) |
| HOB | +0.33 (0.11) | -0.00 (0.24) | -0.48 (0.29) |
| LTR | -0.09 (0.06) | +0.35 (0.17) | +0.33 (0.27) |
| MH3 | -0.14 (0.08) | +0.41 (0.13) | -0.18 (0.21) |
| MSH | +0.47 (0.08) | -0.19 (0.70) | +0.34 (0.21) |
| NEO | +0.16 (0.10) | -0.14 (0.35) | +0.39 (0.24) |
| OTJ | +0.24 (0.12) | +0.37 (0.16) | +0.29 (0.15) |
| PIO | -0.02 (0.07) | -0.35 (0.11) | -0.28 (0.17) |
| SOS | -0.09 (0.08) | -0.07 (0.11) | +0.52 (0.18) |
| TDM | -0.08 (0.08) | -0.27 (0.07) | +0.18 (0.14) |
| TLA | +0.01 (0.08) | +0.09 (0.19) | -0.52 (0.18) |
| TMT | -0.11 (0.08) | +0.29 (0.18) | +0.53 (0.25) |
| sets in the rule's direction | 8/19 | 11/19 | 11/20 |

## By count

Game win rate points of decks at each count against decks at the rule's threshold, at the same card quality (SE).

**Removal Saturated (0.8x past 6)**, removal spells in the deck:

| count | decks | points |
|---|---|---|
| 2 or fewer | 38874 | -1.09 (0.21) |
| 3 | 64143 | -0.71 (0.15) |
| 4 | 108473 | -0.33 (0.12) |
| 5 | 143981 | -0.23 (0.09) |
| 6 (reference) | 156117 | 0 |
| 7 | 137912 | +0.17 (0.10) |
| 8 | 105867 | +0.13 (0.12) |
| 9 | 71376 | +0.25 (0.21) |
| 10 or more | 87801 | +0.46 (0.27) |

**Curve Too Heavy (0.7x past 4)**, heavy spells in the deck:

| count | decks | points |
|---|---|---|
| 0 or fewer | 65875 | +0.15 (0.32) |
| 1 | 134339 | -0.09 (0.16) |
| 2 | 181797 | -0.06 (0.12) |
| 3 | 179802 | -0.04 (0.09) |
| 4 (reference) | 143134 | 0 |
| 5 | 96353 | +0.05 (0.10) |
| 6 | 56786 | -0.07 (0.20) |
| 7 or more | 56698 | -0.31 (0.24) |


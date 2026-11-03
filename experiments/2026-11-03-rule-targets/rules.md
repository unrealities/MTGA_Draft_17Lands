# Rule targets at `5d06abf`

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

Per card, in game win rate points (at the overall win rate), with 99.17% intervals: 95% familywise across the 6 rules. Each SE is the larger of the model's (widened for overdispersion) and the set-clustered one. *Rating SDs*: the same effect as a change in that card's rating, in the format's SDs of GIH WR, with its interval. *The rule's size*: what the rule's multiplier does to a card's score, in the same units.

| rule | tested claim | sets | decks in region | per card (points) | interval | rating SDs | the rule's size | verdict | keep or drop |
|---|---|---|---|---|---|---|---|---|---|
| Removal Saturated (0.8x past 6) | a removal spell past the sixth is worth less than a spell of the same rating | 19 | 402956 (44.1%) | +0.09 | [-0.06, +0.24] | +0.24 [-0.15, +0.63] | -0.87 | not established | drop |
| Curve Too Heavy (0.7x past 4) | a 5+ mana spell past the fourth is worth less than a spell of the same rating | 20 | 209837 (22.9%) | -0.09 | [-0.28, +0.10] | -0.24 [-0.72, +0.25] | -1.30 | not established | can't tell |
| Critical: Needs Fixing (1.4x) | in decks with off-color spells, a fixing card is worth more while fixing is no more than the off-color spells | 20 | 177579 (19.4%) | -0.04 | [-0.34, +0.25] | -0.11 [-0.85, +0.63] | +1.33 | not established | drop |
| Critical: Needs Creatures (1.25x under 13) | a creature is worth more than a spell of the same rating while the deck has fewer than 13 | 20 | 251588 (27.5%) | +0.17 | [+0.02, +0.32] | +0.43 [+0.04, +0.81] | +0.83 | supported | can't tell |
| Critical: Needs Removal (1.3x under 3) | a removal spell is worth more than a spell of the same rating while the deck has fewer than 3 | 19 | 38874 (4.3%) | +0.29 | [+0.01, +0.58] | +0.76 [-0.01, +1.53] | +1.00 | supported | can't tell |
| Critical: Needs 2-Drops (up to 1.5x under 7) | a creature or removal spell of mana value 2 or less is worth more than a spell of the same rating while the deck has fewer than 7 | 20 | 176783 (19.3%) | +0.35 | [+0.15, +0.55] | +0.91 [+0.38, +1.45] | +0.85 | supported | can't tell |

*Supported*: the interval excludes zero in the rule's direction. *Contradicted*: it excludes zero the other way. *Not established*: it includes zero. *Drop*: the whole interval in rating SDs is closer to zero than to the rule's size, so the card is valued better without the rule; *keep*: closer to the rule's size; otherwise *can't tell*.

## Deck score terms

The deck score's other terms in the same fit, in score points (SE), beside the app's weight. *Keep or drop* as above: whether the term's value is closer to zero or to the app's weight. `missing_fixing` is set from drafters' builds, not game results, since few registered decks are short of fixing.

| term | decks with it | from games | interval | app's weight | keep or drop |
|---|---|---|---|---|---|
| two_colors | 458943 | +3.67 (0.30) | [+2.87, +4.47] | +3.50 | keep |
| domain_supported | 17561 | +0.18 (0.31) | [-0.62, +0.99] | +3.20 | drop |
| missing_fixing | 23988 | -0.43 (0.34) | [-1.32, +0.47] | -2.50 | can't tell |

## Uncertainty and sensitivity

Per card, in game win rate points (SE). *Model* and *set-clustered* SEs of the primary fit; *with counts*: lands, creatures and colors added as controls; *strong drafters*: skill bucket 58% or more.

| rule | primary | model SE | set-clustered SE | with counts | strong drafters |
|---|---|---|---|---|---|
| Removal Saturated (0.8x past 6) | +0.09 | 0.02 | 0.06 | +0.20 (0.05) | +0.11 (0.06) |
| Curve Too Heavy (0.7x past 4) | -0.09 | 0.03 | 0.07 | -0.04 (0.06) | -0.03 (0.08) |
| Critical: Needs Fixing (1.4x) | -0.04 | 0.04 | 0.11 | +0.05 (0.09) | -0.08 (0.12) |
| Critical: Needs Creatures (1.25x under 13) | +0.17 | 0.02 | 0.06 | +0.15 (0.06) | +0.08 (0.06) |
| Critical: Needs Removal (1.3x under 3) | +0.29 | 0.10 | 0.11 | +0.39 (0.11) | +0.38 (0.21) |
| Critical: Needs 2-Drops (up to 1.5x under 7) | +0.35 | 0.03 | 0.08 | +0.30 (0.08) | +0.30 (0.08) |

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
| Critical: Needs Creatures (1.25x under 13) | creature from the 13th | +0.19 (0.04) |
| Critical: Needs Removal (1.3x under 3) | removal from the third to the sixth | +0.22 (0.06) |
| Critical: Needs 2-Drops (up to 1.5x under 7) | early play from the 7th | +0.16 (0.06) |

## By set

The primary estimate fit on each set alone, per card in game win rate points. Sets with fewer than 100 decks in the rule's region are marked –.

| set | Removal Saturated (0.8x past 6) | Curve Too Heavy (0.7x past 4) | Critical: Needs Fixing (1.4x) | Critical: Needs Creatures (1.25x under 13) | Critical: Needs Removal (1.3x under 3) | Critical: Needs 2-Drops (up to 1.5x under 7) |
|---|---|---|---|---|---|---|
| BLB | +0.27 (0.07) | -0.56 (0.24) | +0.68 (0.34) | -0.28 (0.15) | -0.34 (0.36) | +0.78 (0.15) |
| Cube_-_Powered | – | – | +2.30 (2.33) | +0.36 (0.50) | – | +0.86 (0.83) |
| DFT | +0.10 (0.08) | +0.28 (0.11) | +0.01 (0.22) | +0.10 (0.09) | +0.81 (0.42) | +0.30 (0.17) |
| DMU | +0.36 (0.08) | -0.02 (0.17) | +0.27 (0.15) | +0.11 (0.12) | -0.20 (0.40) | +0.61 (0.17) |
| DSK | +0.09 (0.07) | -0.11 (0.07) | -0.01 (0.22) | +0.31 (0.08) | +0.00 (0.49) | +0.59 (0.17) |
| EOE | -0.05 (0.08) | -0.41 (0.11) | -0.20 (0.24) | +0.49 (0.12) | +0.20 (0.56) | +0.49 (0.14) |
| FDN | +0.17 (0.08) | -0.30 (0.17) | -0.35 (0.29) | -0.13 (0.16) | +0.55 (0.43) | +0.62 (0.16) |
| FIN | -0.03 (0.07) | +0.44 (0.12) | -0.05 (0.19) | +0.10 (0.06) | +0.65 (0.38) | -0.00 (0.11) |
| FRA | +0.36 (0.06) | +0.37 (0.25) | -0.20 (0.20) | -0.21 (0.10) | +0.19 (0.75) | +0.32 (0.29) |
| HOB | +0.33 (0.11) | -0.00 (0.24) | -0.48 (0.29) | +0.26 (0.14) | -0.59 (0.39) | +0.71 (0.15) |
| LTR | -0.09 (0.06) | +0.35 (0.17) | +0.33 (0.27) | +0.26 (0.05) | +0.35 (0.45) | +0.30 (0.10) |
| MH3 | -0.14 (0.08) | +0.41 (0.13) | -0.18 (0.21) | +0.46 (0.14) | +0.52 (0.60) | -0.32 (0.18) |
| MSH | +0.47 (0.08) | -0.19 (0.70) | +0.34 (0.21) | +0.21 (0.20) | +1.60 (0.51) | +0.65 (0.17) |
| NEO | +0.16 (0.10) | -0.14 (0.35) | +0.39 (0.24) | +0.41 (0.23) | +0.56 (0.33) | -0.25 (0.39) |
| OTJ | +0.24 (0.12) | +0.37 (0.16) | +0.29 (0.15) | +0.09 (0.11) | +0.14 (0.25) | +0.30 (0.12) |
| PIO | -0.02 (0.07) | -0.35 (0.11) | -0.28 (0.17) | +0.01 (0.12) | +0.70 (0.48) | -0.00 (0.17) |
| SOS | -0.09 (0.08) | -0.07 (0.11) | +0.52 (0.18) | +0.03 (0.05) | +0.61 (0.36) | +0.16 (0.12) |
| TDM | -0.08 (0.08) | -0.27 (0.07) | +0.18 (0.14) | +0.22 (0.11) | +0.38 (0.59) | +0.37 (0.12) |
| TLA | +0.01 (0.08) | +0.09 (0.19) | -0.52 (0.18) | +0.33 (0.11) | +0.49 (0.57) | +0.43 (0.21) |
| TMT | -0.11 (0.08) | +0.29 (0.18) | +0.53 (0.25) | +0.13 (0.17) | +0.92 (0.79) | +0.65 (0.22) |
| sets in the rule's direction | 8/19 | 11/19 | 11/20 | 17/20 | 16/19 | 16/20 |

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

**Curve Too Heavy (0.7x past 4)**, spells of mana value 5 or more in the deck:

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

**Critical: Needs Creatures (1.25x under 13)**, creatures in the deck:

| count | decks | points |
|---|---|---|
| 10 or fewer | 95780 | -0.82 (0.29) |
| 11 | 62779 | -0.43 (0.15) |
| 12 | 93029 | -0.23 (0.10) |
| 13 (reference) | 123865 | 0 |
| 14 | 147496 | +0.19 (0.12) |
| 15 | 144800 | +0.37 (0.13) |
| 16 | 113662 | +0.76 (0.13) |
| 17 or more | 133373 | +0.83 (0.21) |

**Critical: Needs 2-Drops (up to 1.5x under 7)**, creatures and removal spells of mana value 2 or less in the deck:

| count | decks | points |
|---|---|---|
| 3 or fewer | 11244 | -1.71 (0.29) |
| 4 | 23412 | -0.97 (0.24) |
| 5 | 51557 | -0.37 (0.16) |
| 6 | 90570 | -0.01 (0.13) |
| 7 (reference) | 127283 | 0 |
| 8 | 148227 | +0.42 (0.13) |
| 9 | 143679 | +0.59 (0.13) |
| 10 or more | 318812 | +0.84 (0.20) |


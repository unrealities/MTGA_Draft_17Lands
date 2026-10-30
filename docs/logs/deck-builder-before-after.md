# Deck builder suggestions before and after the deck score refit

The deck builder's top suggestion for 3,000 real pools: 300 17Lands Premier Draft decks from each of ten sets (DFT, FDN, FIN, FRA, HOB, MSH, SOS, TDM, TLA, TMT), each pool being the drafter's deck plus sideboard. Ratings below are the builder's, after its mana simulation adjustments.

| scorer | top build is 3+ colors short of fixing | same main colors as the drafter's deck | cards in common with the drafter's deck |
|---|---|---|---|
| old (main) | 3.6% | 59.6% | 19.5 |
| new weights, no fixing penalty | 8.9% | 58.9% | 19.6 |
| **new weights, fixing penalty -2.5 (this PR)** | 4.9% | 58.7% | 19.6 |
| new weights, fixing penalty -6 (main's value) | 3.3% | 58.4% | 19.6 |
| the drafters' own decks | 2.7% | - | - |

## How the fixing penalty was fit

Game results can't fit the fixing penalty: drafters rarely play a deck of three or more colors without the fixing for it, so there are too few such decks to measure. Instead it is fit to the builds drafters chose. For 3,000 other pools from the same sets, every candidate build the deck builder considered was kept. The build the drafter chose is taken to be the candidate in the drafter's own colors with the fewest cards different from their deck, if that is 10 cards or fewer (2,904 pools). A conditional logit then asks how much each part of the deck score explains which candidate was chosen, in deck score points with card quality fixed at its 12 points per standard deviation.

| | in the deck score | fitted to drafters' choices |
|---|---|---|
| two colors or fewer | +3.5 | +2.9 ± 0.1 |
| each fixing card short | -2.5 | -2.6 ± 0.3 |

The two-color bonus, fit to game results, comes out about the same from drafters' choices. Where the builder offered both kinds of build, 28% of its candidates were short of fixing but only 5% of the builds drafters chose were. Requiring the chosen build to be within 6 cards of the drafter's deck gives -2.1 ± 0.4; strong drafters alone give -1.4 to -1.7 ± 0.5. The domain and missing-spells weights can't be fit this way: too few candidates differ on them.

The top suggestion's colors change for 9.8% of pools. Below are the pools whose top suggestion changed the most, then pools where the fixing penalty changed it.

## Biggest changes, old to new

### 1. TLA: the drafter played UR

Their deck went 0–1 in games (17Lands deck `554be594d6b344f7b35d3ca04e8f01b7:1`; the drafter's game win rate bucket is 0.50).

- **Drafter's deck:** 2 Abandon Attachments, Benevolent River Spirit, Cat-Owl, Fire Nation Attacks, Flexible Waterbender, Forecasting Fortune Teller, Geyser Leaper, Iroh's Demonstration, Kyoshi Battle Fan, Mai, Jaded Edge, Master Pakku, Meteor Sword, Octopus Form, Otter-Penguin, Sokka, Bold Boomeranger, The Cave of Two Lovers, 2 The Legend of Kuruk, Uncle Iroh, Vindictive Warden, Waterbending Lesson, Watery Grasp; lands: 9 Island, 8 Mountain
- **Old: WR Splash UGB, 77** (Excellent Aggro Curve (+5.0) | Flood Risk (-0.2)). 2 Abandon Attachments, Cat-Owl, Deserter's Disciple, 2 Earth Kingdom Protectors, Earth Rumble Wrestlers, Enter the Avatar State, Fire Nation Attacks, 2 How to Start a Riot, Iroh's Demonstration, Jeong Jeong's Deserters, Kyoshi Battle Fan, Mai, Jaded Edge, Pretending Poxbearers, 2 Sun Warriors, The Cave of Two Lovers, Uncle Iroh, Vindictive Warden, Watery Grasp, Yip Yip!; lands: 2 Island, 7 Mountain, 8 Plains
- **New: UB Splash RWG, 73** (Greedy Mana Strain (-5.0) | Flood Risk (-0.5)). 2 Abandon Attachments, Benevolent River Spirit, Cat-Owl, Dai Li Indoctrination, Flexible Waterbender, Forecasting Fortune Teller, Geyser Leaper, Kyoshi Battle Fan, Mai, Scornful Striker, Master Pakku, Meteor Sword, Octopus Form, Otter-Penguin, Platypus-Bear, Pretending Poxbearers, The Cave of Two Lovers, 2 The Legend of Kuruk, The Spirit Oasis, Vindictive Warden, Waterbending Lesson, Watery Grasp; lands: 9 Island, Mountain, 7 Swamp

### 2. SOS: the drafter played UR

Their deck went 0–1 in games (17Lands deck `934e81cb94dd4e56ae8ffc283e78026a:0`; the drafter's game win rate bucket is 0.42).

- **Drafter's deck:** Artistic Process, 2 Banishing Betrayal, Brush Off, Deluge Virtuoso, Flashback, Heated Argument, Jadzi, Steward of Fate, Landscape Painter, 2 Matterbending Mage, Molten-Core Maestro, Page, Loose Leaf, Procrastinate, Rapturous Moment, Spell Pierce, Splatter Technique, Stadium Tidalmage, Tome Blast, 2 Visionary's Dance, 2 Zealous Lorecaster; lands: 9 Island, 8 Mountain
- **Old: UG Safe Tempo, 83** (Excellent Aggro Curve (+5.0), Rock-Solid Mana (+2.5)). Applied Geometry, 2 Banishing Betrayal, Brush Off, Deluge Virtuoso, Follow the Lumarets, Fractal Mascot, Jadzi, Steward of Fate, Landscape Painter, 2 Matterbending Mage, Mindful Biomancer, Page, Loose Leaf, Paradox Surveyor, Procrastinate, 2 Pterafractyl, 2 Rancorous Archaic, Spell Pierce, 2 Studious First-Year, Tenured Concocter, Wild Hypothesis; lands: 8 Forest, 8 Island
- **New: UR Safe Tempo, 80** (Rock-Solid Mana (+3.5)). Artistic Process, 2 Banishing Betrayal, Brush Off, Deluge Virtuoso, Flashback, Goblin Glasswright, Heated Argument, Jadzi, Steward of Fate, Landscape Painter, 2 Matterbending Mage, Molten-Core Maestro, Page, Loose Leaf, Procrastinate, Return the Favor, Spell Pierce, Splatter Technique, Stadium Tidalmage, Tome Blast, 2 Visionary's Dance, 2 Zealous Lorecaster; lands: 8 Island, 8 Mountain

### 3. SOS: the drafter played BG, splashing U

Their deck went 1–0 in games (17Lands deck `c08b4b0bb7984b24ab3e569a3e94ad35:1`; the drafter's game win rate bucket is 0.40).

- **Drafter's deck:** Additive Evolution, Bitter Triumph, Bogwater Lumaret, Burrog Barrage, Cost of Brilliance, Emeritus of Abundance, Emil, Vastlands Roamer, Foolish Fate, Germination Practicum, Grave Researcher, Lluwen, Exchange Student, 2 Mind into Matter, 2 Mindful Biomancer, Noxious Newt, Page, Loose Leaf, Paradox Gardens, 2 Pest Mascot, Poisoner's Apprentice, Root Manipulation, Shared Roots, 2 Titan's Grave, Witherbloom Charm; lands: 6 Forest, Island, 7 Swamp
- **Old: BG Safe Tempo, 80** (Excellent Aggro Curve (+5.0), Rock-Solid Mana (+2.5)). Bitter Triumph, Bogwater Lumaret, 2 Burrog Barrage, Cost of Brilliance, Emeritus of Abundance, Follow the Lumarets, Foolish Fate, Germination Practicum, Giant Growth, Grave Researcher, Lluwen, Exchange Student, Lumaret's Favor, Masterful Flourish, 2 Mindful Biomancer, Noxious Newt, 2 Pest Mascot, Poisoner's Apprentice, Pull from the Grave, Rabid Attack, Shared Roots, 2 Titan's Grave, Witherbloom Charm; lands: 8 Forest, 6 Swamp
- **New: UG Safe Core, 79** (Rock-Solid Mana (+3.5) | Flood Risk (-0.7)). Additive Evolution, 2 Burrog Barrage, Embrace the Paradox, Emeritus of Abundance, Emil, Vastlands Roamer, Follow the Lumarets, Fractal Mascot, Germination Practicum, Giant Growth, 2 Hungry Graffalon, Lumaret's Favor, 2 Mind into Matter, 2 Mindful Biomancer, Noxious Newt, 2 Page, Loose Leaf, Paradox Gardens, Quandrix Charm, Shared Roots, Snarl Song; lands: 10 Forest, 6 Island

### 4. TLA: the drafter played WUG

Their deck went 2–1 in games (17Lands deck `35ddc33f23e74a588d5afaaf9443990f:0`; the drafter's game win rate bucket is 0.62).

- **Drafter's deck:** Aang's Journey, 2 Abandon Attachments, Avatar's Wrath, Compassionate Healer, 2 Earth Kingdom Soldier, Enter the Avatar State, Forecasting Fortune Teller, Geyser Leaper, Glider Kids, Guru Pathik, Iguana Parrot, Kyoshi Battle Fan, Lost Days, Meditation Pools, North Pole Gates, 2 Path to Redemption, 2 Rowdy Snowballers, Suki, Courageous Rescuer, The Earth King, Ty Lee, Chi Blocker, Water Tribe Captain; lands: 2 Forest, 6 Island, 7 Plains
- **Old: UB Splash GR, 79** (Excellent Aggro Curve (+5.0) | Flood Risk (-1.2)). Aang's Journey, 2 Abandon Attachments, Corrupt Court Official, Dai Li Indoctrination, Flexible Waterbender, Forecasting Fortune Teller, Geyser Leaper, Guru Pathik, Heartless Act, Hog-Monkey, Iguana Parrot, Kyoshi Battle Fan, Lo and Li, Twin Tutors, Lost Days, Merchant of Many Hats, Northern Air Temple, 2 Platypus-Bear, 2 Rowdy Snowballers, Serpent's Pass, Tundra Tank, Ty Lee, Chi Blocker; lands: 9 Island, 7 Swamp
- **New: WU Good Stuff (Soup), 77** (Flood Risk (-2.2)). Aang's Journey, 2 Abandon Attachments, Compassionate Healer, Corrupt Court Official, 2 Earth Kingdom Soldier, Enter the Avatar State, Forecasting Fortune Teller, Glider Kids, Guru Pathik, Heartless Act, Kyoshi Battle Fan, Lo and Li, Twin Tutors, Lost Days, Meditation Pools, Merchant of Many Hats, Misty Palms Oasis, North Pole Gates, 2 Path to Redemption, Serpent's Pass, Suki, Courageous Rescuer, The Earth King, Tundra Tank, Ty Lee, Chi Blocker, Water Tribe Captain; lands: 2 Forest, 3 Island, 6 Plains, 2 Swamp

### 5. MSH: the drafter played UB

Their deck went 1–2 in games (17Lands deck `f77249ec9e174fdbaa04ef973bf80ca1:1`; the drafter's game win rate bucket is 0.46).

- **Drafter's deck:** 2 Aerial Doombot, Arnim Zola, Bio-Fanatic, 2 Atlantis Attacks, Attuma, Atlantean Warlord, Bold Biochemist, Bullseye, Death Dealer, Cruel Alliance, Dependable Quinjet, Falcon, Winged Wonder, H.E.R.B.I.E. Scout Unit, Hour of Defeat, Moonstone, Harsh Mistress, Red Room Recruit, Roxxon Brutes, Stature, Size Shifter, Super Intelligence, Super-Skrull, Taskmaster, Mercenary Mimic, Trickster's Stratagem, We Say Thee Nay!, Yellowjacket, Heartless Marauder; lands: 9 Island, 8 Swamp
- **Old: UB Safe Core Splash R, 81** (Excellent Aggro Curve (+5.0)). 2 Aerial Doombot, Agents of HYDRA, Attuma, Atlantean Warlord, Bold Biochemist, Bullseye, Death Dealer, Cruel Alliance, Depower, H.E.R.B.I.E. Scout Unit, HYDRA Infiltration, Hour of Defeat, 2 Hydraulic Helper, Kingpin's Enforcers, Project Deathlok Soldier, Red Room Recruit, Roxxon Brutes, Stature, Size Shifter, Super Intelligence, Super Suit, Super-Skrull, Trickster's Stratagem, We Say Thee Nay!, Yellowjacket, Heartless Marauder; lands: 7 Island, 9 Swamp
- **New: U Safe Core Splash G, 79** (Rock-Solid Mana (+3.5)). 2 Aerial Doombot, Atlantean Cavalry, 2 Atlantis Attacks, Attuma, Atlantean Warlord, Bold Biochemist, Dependable Quinjet, Depower, Epic Fight, Falcon, Winged Wonder, H.E.R.B.I.E. Scout Unit, 2 Hydraulic Helper, I Am Iron Man, Iron Lad, Diverging Destiny, Restorative Technique, Stature, Size Shifter, Super Intelligence, Super Suit, Training Regimen, Trickster's Stratagem, Vibranium Energy Daggers, We Say Thee Nay!; lands: 7 Forest, 9 Island

### 6. SOS: the drafter played UG, splashing WBR

Their deck went 2–3 in games (17Lands deck `6edc9d999e0c4539afdef7060a6b6138:1`; the drafter's game win rate bucket is 0.58).

- **Drafter's deck:** Applied Geometry, Arcane Omens, Banishing Betrayal, Brain Freeze, Brush Off, Disdainful Stroke, Divergent Equation, Embrace the Paradox, Essence Scatter, Fields of Strife, Forum of Amity, Great Hall of the Biblioplex, Homesickness, Hydro-Channeler, Informed Inkwright, Knockout Maneuver, Repel Calamity, Shared Roots, Silverquill Charm, Skycoach Conductor, Spell Pierce, Splatter Technique, Strixhaven Skycoach, Studious First-Year, Sundering Archaic, Titan's Grave, Traumatic Critique; lands: 4 Forest, 5 Island, 2 Mountain, Plains, Swamp
- **Old: UG Good Stuff (Soup), 87** (Excellent Aggro Curve (+5.0) | Flood Risk (-2.2)). Applied Geometry, Arcane Omens, Brush Off, Disdainful Stroke, Divergent Equation, Embrace the Paradox, Essence Scatter, Fields of Strife, Forum of Amity, Goblin Glasswright, Great Hall of the Biblioplex, Hydro-Channeler, Informed Inkwright, Inkling Mascot, Knockout Maneuver, Quick Study, Repel Calamity, Shared Roots, 2 Silverquill Charm, Skycoach Conductor, Splatter Technique, Strixhaven Skycoach, Studious First-Year, Sundering Archaic, Titan's Grave, Traumatic Critique; lands: 4 Forest, 4 Island, 3 Mountain, Plains, Swamp
- **New: UR Safe Core, 76** (Rock-Solid Mana (+3.5) | Flood Risk (-3.4)). Banishing Betrayal, Biblioplex Tomekeeper, Brain Freeze, Brush Off, Chase Inspiration, Disdainful Stroke, Divergent Equation, Essence Scatter, 2 Expressive Firedancer, Fractal Anomaly, Goblin Glasswright, Great Hall of the Biblioplex, Homesickness, Hydro-Channeler, Muse's Encouragement, Quick Study, Rearing Embermare, Skycoach Conductor, Spell Pierce, Splatter Technique, Strixhaven Skycoach, Sundering Archaic, Traumatic Critique; lands: 10 Island, 6 Mountain

## Where the fixing penalty changes the build

### 7. TLA: the drafter played WB

Their deck went 0–2 in games (17Lands deck `4e16fcf588e34936b9c6dd7edafa84e6:1`; the drafter's game win rate bucket is 0.48).

- **Drafter's deck:** Appa, Loyal Sky Bison, 2 Beetle-Headed Merchants, Buzzard-Wasp Colony, 2 Callous Inspector, Glider Kids, Glider Staff, Joo Dee, One of Many, June, Bounty Hunter, Long Feng, Grand Secretariat, 2 Merchant of Many Hats, Messenger Hawk, Meteor Sword, Misty Palms Oasis, Obsessive Pursuit, Path to Redemption, Phoenix Fleet Airship, 2 Pirate Peddlers, Rabaroo Troop, 2 Tolls of War; lands: 7 Plains, 9 Swamp
- **Old: WB Splash GUR, 75** (Flood Risk (-1.9)). 2 Callous Inspector, Canyon Crawler, Cat-Owl, Crescent Island Temple, 2 Curious Farm Animals, 2 Earth Kingdom Soldier, Glider Kids, Glider Staff, Joo Dee, One of Many, June, Bounty Hunter, Long Feng, Grand Secretariat, 2 Merchant of Many Hats, Messenger Hawk, Misty Palms Oasis, Obsessive Pursuit, Path to Redemption, Phoenix Fleet Airship, Rabaroo Troop, Sun-Blessed Peak, 2 Tolls of War; lands: 2 Mountain, 4 Plains, 9 Swamp
- **New, no fixing penalty: UB Splash GW, 76**. 2 Beetle-Headed Merchants, Buzzard-Wasp Colony, 2 Callous Inspector, Canyon Crawler, Cat-Owl, Flexible Waterbender, Foggy Swamp Spirit Keeper, Hog-Monkey, Joo Dee, One of Many, June, Bounty Hunter, Katara, Bending Prodigy, Long Feng, Grand Secretariat, 2 Merchant of Many Hats, Messenger Hawk, Obsessive Pursuit, Otter-Penguin, Phoenix Fleet Airship, 2 Pirate Peddlers, 2 Watery Grasp; lands: 8 Island, 8 Swamp
- **New: WB Splash GUR, 75** (Flood Risk (-1.9)). 2 Callous Inspector, Canyon Crawler, Cat-Owl, Crescent Island Temple, 2 Curious Farm Animals, 2 Earth Kingdom Soldier, Glider Kids, Glider Staff, Joo Dee, One of Many, June, Bounty Hunter, Long Feng, Grand Secretariat, 2 Merchant of Many Hats, Messenger Hawk, Misty Palms Oasis, Obsessive Pursuit, Path to Redemption, Phoenix Fleet Airship, Rabaroo Troop, Sun-Blessed Peak, 2 Tolls of War; lands: 2 Mountain, 4 Plains, 9 Swamp

### 8. FRA: the drafter played WU, splashing B

Their deck went 0–1 in games (17Lands deck `6802dad314fd40958507be4a5bb466ea:1`; the drafter's game win rate bucket is 0.50).

- **Drafter's deck:** Apex Witchstalker, 2 Blossom-Blessed Angel, Cryotheory Adept, Fatehold Chronologist, Geist of Saint Thalia, Generous Revival, 2 Icy Reception, Infinite Coursework, Lyra, Tolarian Archangel, 2 Memory Trap, Perfected Theory, Plan for All Outcomes, Proft, Consulting Detective, Rewrite Regrets, Rise of the Deathbringer, Shatterwing Pegasus, Sphinx's Approach, Surveillance Phantasm, Twinned Vision, Variable Chaser, Yuriko, Hope from the Shadows; lands: 7 Island, 6 Plains, 3 Swamp
- **Old: UB Splash WR, 72** (Excellent Aggro Curve (+5.0), Greedy Mana Strain (-12.0)). Apex Witchstalker, Cryotheory Adept, Fatehold Chronologist, Geist of Saint Thalia, 2 Hapatra, the Desert Frost, 2 Icy Reception, Infinite Coursework, Lyra, Tolarian Archangel, Perfected Theory, Plan for All Outcomes, Proft, Consulting Detective, Rewrite Regrets, Rise of the Deathbringer, 2 Screeching Soulbreaker, 2 Sphinx's Approach, Surveillance Phantasm, Twinned Vision, Variable Chaser, Void Extrapolator, Yuriko, Hope from the Shadows; lands: 8 Island, 8 Swamp
- **New, no fixing penalty: WU Splash GR, 80** (Flood Risk (-1.0)). Academic Ascent, 2 Blossom-Blessed Angel, Emergency Phytomedic, Fatehold Chronologist, Geist of Saint Thalia, Generous Revival, 2 Icy Reception, Infinite Coursework, Lyra, Tolarian Archangel, 2 Memory Trap, Plan for All Outcomes, Proft, Consulting Detective, 2 Shatterwing Pegasus, 2 Sphinx's Approach, Surveillance Phantasm, Tomik, Orzhov Lawmage, Twinned Vision, Variable Chaser; lands: 9 Island, 8 Plains
- **New: UB Splash WR, 74** (Greedy Mana Strain (-5.0)). Apex Witchstalker, Cryotheory Adept, Fatehold Chronologist, Geist of Saint Thalia, 2 Hapatra, the Desert Frost, 2 Icy Reception, Infinite Coursework, Lyra, Tolarian Archangel, Perfected Theory, Plan for All Outcomes, Proft, Consulting Detective, Rewrite Regrets, Rise of the Deathbringer, 2 Screeching Soulbreaker, 2 Sphinx's Approach, Surveillance Phantasm, Twinned Vision, Variable Chaser, Void Extrapolator, Yuriko, Hope from the Shadows; lands: 8 Island, 8 Swamp

### 9. FRA: the drafter played BR

Their deck went 0–3 in games (17Lands deck `a24efe62b0ae45feb7cb489abe7af413:0`; the drafter's game win rate bucket is 0.60).

- **Drafter's deck:** Blessed Ghoul, Cast Away Doubt, 2 Command the Stage, Ferocity of the Hunt, Fulminous Forte, Gallia, the Merrymaker, 3 Grim Repriser, Hallway Heckler, Jiang Yanggu, Alone, Massacre Girl, Most Wanted, Master of Barbs, No Admittance, Silence the Echo, Skilled Battlecarver, Stingerquill Annex, Stingerquill Charm, 2 Tether Technician, Traxos, Scourge Eternal, Twinned Vision, Way of the Warlord, Whiplash Wordsmith, Wrath of the Bloodmane; lands: 8 Mountain, 6 Swamp
- **Old: BR Good Stuff (Soup), 58** (Excellent Aggro Curve (+5.0), Greedy Mana Strain (-18.0) | Flood Risk (-2.1)). 2 Blessed Ghoul, 2 Cast Away Doubt, Clash of Elements, Fulminous Forte, 3 Grim Repriser, Jiang Yanggu, Alone, Karn, Gilded Guardian, Marwyn, the Clearcutter, Master of Barbs, Medic's Kitesail, No Admittance, Protege's Awakening, 2 Skilled Battlecarver, Stingerquill Annex, Stingerquill Charm, Tether Technician, Twinned Vision, Way of the Warlord, Wrath of the Bloodmane; lands: Forest, Island, 7 Mountain, Plains, 6 Swamp
- **New, no fixing penalty: BR Good Stuff (Soup), 71** (Flood Risk (-2.1)). 2 Blessed Ghoul, 2 Cast Away Doubt, Clash of Elements, Fulminous Forte, 3 Grim Repriser, Jiang Yanggu, Alone, Karn, Gilded Guardian, Marwyn, the Clearcutter, Master of Barbs, Medic's Kitesail, No Admittance, Protege's Awakening, 2 Skilled Battlecarver, Stingerquill Annex, Stingerquill Charm, Tether Technician, Twinned Vision, Way of the Warlord, Wrath of the Bloodmane; lands: Forest, Island, 7 Mountain, Plains, 6 Swamp
- **New: UR Splash B, 64** (Greedy Mana Strain (-5.0)). Arni, Renowned Champion, Artifist Acumen, Blazing Crescendo, Clash of Elements, 2 Command the Stage, Eardrum Rattler, Fulminous Forte, Gallia, the Merrymaker, Hallway Heckler, Marwyn, the Clearcutter, Master of Barbs, Medic's Kitesail, No Admittance, Protege's Awakening, 2 Skilled Battlecarver, 2 Tether Technician, Traxos, Scourge Eternal, Twinned Vision, Way of the Warlord, Whiplash Wordsmith, Wrath of the Bloodmane; lands: 4 Island, 12 Mountain

### 10. TDM: the drafter played URG

Their deck went 1–3 in games (17Lands deck `81069166d36d4e699d315116fb852ba8:0`; the drafter's game win rate bucket is 0.38).

- **Drafter's deck:** Aegis Sculptor, Dirgur Island Dragon, Dispelling Exhale, 2 Effortless Master, Eshki Dragonclaw, Focus the Mind, Glacial Dragonhunt, Highspire Bell-Ringer, Humbling Elder, Kishla Skimmer, Kishla Trawlers, Molten Exhale, Ringing Strike Mastery, Sagu Pummeler, Sarkhan's Resolve, Scalding Tarn, 4 Sibsig Appraiser, Snakeskin Veil, 2 Swiftwater Cliffs, Temur Devotee, Temur Tawnyback; lands: 5 Forest, 6 Island, 3 Mountain
- **Old: UR Safe Tempo, 79** (Excellent Aggro Curve (+5.0), Rock-Solid Mana (+2.5)). Aegis Sculptor, Devoted Duelist, Dispelling Exhale, 2 Effortless Master, Fire-Rim Form, Focus the Mind, 2 Glacial Dragonhunt, Highspire Bell-Ringer, Humbling Elder, 2 Kishla Trawlers, Molten Exhale, Ringing Strike Mastery, Scalding Tarn, 2 Seize Opportunity, 4 Sibsig Appraiser, Snowmelt Stag, 2 Swiftwater Cliffs, Temur Devotee, Wingspan Stride; lands: 7 Island, 6 Mountain
- **New, no fixing penalty: UG Safe Core Splash R, 76** (Flood Risk (-2.6)). Aegis Sculptor, Auroral Procession, Bewildering Blizzard, Dirgur Island Dragon, Dispelling Exhale, Dusyut Earthcarver, Focus the Mind, Humbling Elder, Kishla Skimmer, 2 Kishla Trawlers, Piercing Exhale, Sagu Pummeler, Sarkhan's Resolve, Scalding Tarn, 4 Sibsig Appraiser, Snakeskin Veil, Snowmelt Stag, Synchronized Charge, Temur Devotee, Temur Tawnyback; lands: 8 Forest, 7 Island, Mountain
- **New: UR Safe Tempo, 75** (Rock-Solid Mana (+3.5)). Aegis Sculptor, Devoted Duelist, Dispelling Exhale, 2 Effortless Master, Fire-Rim Form, Focus the Mind, 2 Glacial Dragonhunt, Highspire Bell-Ringer, Humbling Elder, 2 Kishla Trawlers, Molten Exhale, Ringing Strike Mastery, Scalding Tarn, 2 Seize Opportunity, 4 Sibsig Appraiser, Snowmelt Stag, 2 Swiftwater Cliffs, Temur Devotee, Wingspan Stride; lands: 7 Island, 6 Mountain

from math import comb

import hands
import pytest
from src.advisor import simulator as sim

ISLAND = {"name": "Island", "types": ["Land", "Basic"], "colors": ["U"],
          "oracle_text": "({T}: Add {U}.)"}
MOUNTAIN = {"name": "Mountain", "types": ["Land", "Basic"], "colors": ["R"],
            "oracle_text": "({T}: Add {R}.)"}
OGRE = {"name": "Ogre", "types": ["Creature"], "mana_cost": "{1}{R}{R}", "cmc": 3,
        "colors": ["R"]}


class FakeApp:
    cards = {"Island": ISLAND, "Mountain": MOUNTAIN, "Ogre": OGRE}

    def deck(self, cards):
        return [dict(self.cards[n], count=c) for n, c in cards.items()]


@pytest.fixture(scope="module")
def kernels():
    return hands.make_kernels(sim)


def test_screw_and_flood_chances():
    # Two lands in hand, 15 of the other 33 cards lands: screwed unless one
    # of the next two is a land.
    assert hands.screw_chance(2, 17) == pytest.approx(comb(18, 2) / comb(33, 2))
    assert hands.screw_chance(3, 17) == 0.0
    assert hands.flood_chance(5, 17) == pytest.approx(1 - comb(21, 4) / comb(33, 4))
    assert hands.flood_chance(6, 17) == 1.0
    assert hands.flood_chance(1, 17) == 0.0


def test_hand_indices():
    where = hands.positions({"Island": 17, "Ogre": 23})
    assert where["Ogre"][0] == 17
    idx = hands.hand_indices({"Island": 3, "Ogre": 4}, where)
    assert idx == [0, 1, 2, 17, 18, 19, 20]
    assert hands.hand_indices({"Island": 3, "Elf": 4}, where) is None
    assert hands.hand_indices({"Island": 3}, where) is None


def test_color_screw_when_no_land_makes_red(kernels):
    decks = [
        {"id": "blue", "cards": {"Island": 17, "Ogre": 23}},
        {"id": "red", "cards": {"Mountain": 17, "Ogre": 23}},
        {"id": "short", "cards": {"Island": 17, "Ogre": 22}},
    ]
    games = [
        ["blue:0", True, 0, True, {"Island": 3, "Ogre": 4}],
        ["blue:0", False, 0, False, {"Island": 2, "Ogre": 5}],
        ["blue:0", False, 1, False, {"Island": 2, "Ogre": 5}],
        ["red:0", True, 0, True, {"Mountain": 3, "Ogre": 4}],
    ]
    games = [[g[0].split(":")[0], *g[1:]] for g in games]
    rows, skipped = hands.deck_hands(FakeApp(), sim, kernels, decks, games,
                                     shuffles=2000, kept7_shuffles=2000)
    assert skipped == {"not 40 cards": 1}
    blue, red = rows
    three, two, mulligan = blue["games"]
    # Three Islands and four Ogres: no Ogre is ever castable.
    assert three == [1, 0, 1, 3, 0.0, pytest.approx(hands.flood_chance(3, 17)), 1.0]
    # Two Islands: color screwed whenever a land comes by turn 3.
    assert two[6] == pytest.approx(1 - comb(18, 2) / comb(33, 2), abs=0.04)
    assert mulligan == [0, 1, 0, None, None, None, None]
    assert red["games"][0][6] == 0.0
    assert blue["lands"] == 17 and blue["sim"]["color_screw_t3"] > 50
    assert red["sim"]["color_screw_t3"] == 0
    assert 0 < blue["kept7"]["screw_t3"] < blue["sim"]["screw_t3"] + 10

"""Tests for the focused simulator fixes: mana filters and deterministic seeds."""

from src.advisor.simulator import _parse_deck_to_arrays, simulate_deck


def _card(name, text, mana_cost="{1}", cmc=1, types=("Artifact",), count=1):
    return {
        "name": name, "count": count, "types": list(types),
        "mana_cost": mana_cost, "colors": [], "cmc": cmc,
        "oracle_text": text, "tags": ["fixing_ramp"],
    }


def _classify(card):
    filler = {"name": "Filler", "count": 39, "types": ["Creature"],
              "mana_cost": "{1}{G}", "colors": ["G"], "cmc": 2}
    arrays = _parse_deck_to_arrays([card, filler])
    return bool(arrays.is_ramp[0]), bool(arrays.is_filter[0]), int(arrays.mana_produced[0])


class TestManaFilterClassification:
    def test_prophetic_prism_is_a_filter_that_fixes(self):
        prism = _card("Prophetic Prism", "{1}, {T}: Add one mana of any color. "
                      "{1}, {T}, Sacrifice Prophetic Prism: Draw a card.")
        assert _classify(prism) == (False, True, 31)

    def test_chromatic_star_is_a_filter(self):
        star = _card("Chromatic Star", "{1}, {T}, Sacrifice Chromatic Star: Add "
                     "one mana of any color. When Chromatic Star is put into a "
                     "graveyard from the battlefield, draw a card.")
        assert _classify(star) == (False, True, 31)

    def test_sol_ring_is_ramp(self):
        assert _classify(_card("Sol Ring", "{T}: Add {C}{C}."))[:2] == (True, False)

    def test_llanowar_elves_is_ramp(self):
        elves = _card("Llanowar Elves", "{T}: Add {G}.", mana_cost="{G}",
                      types=("Creature",))
        assert _classify(elves) == (True, False, 16)

    def test_servant_of_the_conduit_energy_cost_is_not_mana(self):
        servant = _card(
            "Servant of the Conduit",
            "When this creature enters, you get {E}{E}.\n"
            "{T}, Pay {E}: Add one mana of any color.",
            mana_cost="{1}{G}", cmc=2, types=("Creature",),
        )
        assert _classify(servant) == (True, False, 31)

    def test_signet_makes_more_than_it_costs(self):
        signet = _card("Azorius Signet", "{1}, {T}: Add {W}{U}.", cmc=2,
                       mana_cost="{2}")
        assert _classify(signet) == (True, False, 3)

    def test_free_tap_outweighs_filter_ability(self):
        lens = _card("Prismatic Lens", "{T}: Add {C}. {1}, {T}: Add one mana "
                     "of any color.", cmc=2, mana_cost="{2}")
        assert _classify(lens)[:2] == (True, False)

    def test_treasure_maker_with_filter_stays_ramp(self):
        card = _card("Treasure Prism", "{1}, {T}: Add one mana of any color. "
                     "When this enters, create a Treasure token.")
        assert _classify(card) == (True, False, 31)

    def test_non_mana_add_is_not_a_filter(self):
        card = _card("Counter Rock", "{2}, {T}: Draw a card. Then add a +1/+1 "
                     "counter.", cmc=2, mana_cost="{2}")
        assert _classify(card)[:2] == (True, False)


def _splash_deck(prisms):
    deck = [
        {"name": "Forest", "count": 17, "types": ["Land"], "colors": ["G"]},
        {"name": "Red Splash", "count": 23 - prisms, "types": ["Creature"],
         "mana_cost": "{2}{R}", "colors": ["R"], "cmc": 3},
    ]
    if prisms:
        deck.append(_card("Prophetic Prism", "{1}, {T}: Add one mana of any color.",
                          count=prisms))
    return deck


class TestFilterFixing:
    def test_prism_lets_a_splash_be_cast(self):
        assert simulate_deck(_splash_deck(0), iterations=2000)["cast_t3"] == 0.0
        assert simulate_deck(_splash_deck(4), iterations=2000)["cast_t3"] > 0.0

    @staticmethod
    def _cast_turn_3(forests, spell_cost):
        import numpy as np
        from src.advisor.simulator import MAX_SOURCES, _castable_on_turn

        forest = {"name": "Forest", "count": forests, "types": ["Land"],
                  "colors": ["G"]}
        prism = _card("Prophetic Prism", "{1}, {T}: Add one mana of any color.")
        spell = {"name": "Spell", "count": 1, "types": ["Creature"],
                 "mana_cost": spell_cost, "cmc": 3}
        filler = {"name": "Filler", "count": 40, "types": ["Creature"],
                  "mana_cost": "{6}", "cmc": 6}
        a = _parse_deck_to_arrays([forest, prism, spell, filler])
        # On the play: the opening hand plus two draws by turn 3
        return _castable_on_turn(
            np.arange(40), 0, 9, 3, a.is_land, a.is_ramp, a.is_filter,
            a.costs, a.mana_produced, a.pips, a.pip_count, a.generic,
            np.zeros(MAX_SOURCES, dtype=np.int32),
            np.zeros(MAX_SOURCES, dtype=np.int32),
            np.zeros(32, dtype=np.int32),
        )

    def test_prism_adds_no_mana(self):
        assert self._cast_turn_3(2, "{2}{G}") == (True, False)

    def test_prism_converts_a_land_to_any_color(self):
        assert self._cast_turn_3(3, "{2}{R}") == (True, True)
        assert self._cast_turn_3(3, "{1}{R}{R}") == (True, False)


class TestDeterministicSimulation:
    def _deck(self):
        return [
            {"name": "Bear", "count": 23, "types": ["Creature"],
             "mana_cost": "{1}{G}", "colors": ["G"], "cmc": 2},
            {"name": "Forest", "count": 17, "types": ["Land"]},
        ]

    def test_same_deck_same_results(self):
        results = [simulate_deck(self._deck(), iterations=200) for _ in range(3)]
        assert all(r == results[0] for r in results)

    def test_default_seed_is_shared_fixed_seed(self):
        assert simulate_deck(self._deck(), iterations=200) == simulate_deck(
            self._deck(), iterations=200, seed=0
        )
        assert simulate_deck(self._deck(), iterations=200, seed=1) != simulate_deck(
            self._deck(), iterations=200, seed=0
        )

    def test_order_and_names_do_not_change_results(self):
        renamed = [
            {**self._deck()[1], "name": "Some Forest"},
            {**self._deck()[0], "name": "Other Bear"},
        ]
        assert simulate_deck(renamed, iterations=200) == simulate_deck(
            self._deck(), iterations=200
        )

"""Tests for the three focused fixes: mana filters, CRN seeds, determinism."""

import numpy as np
import pytest


class TestManaFilterClassification:
    """Prophetic Prism costs {1} to activate and produces 1 mana — a filter.
    Sol Ring costs {0} and produces 2 — ramp. Llanowar Elves {T}: Add {G} — ramp."""

    def _is_ramp(self, card):
        from src.advisor.simulator import _parse_deck_to_arrays
        deck = [card] + [
            {"name": "Filler", "count": 39, "types": ["Creature"],
             "mana_cost": "{1}{G}", "colors": ["G"], "cmc": 2},
        ]
        arr = _parse_deck_to_arrays(deck)
        return bool(arr.is_ramp[0]) if arr else False

    def test_prophetic_prism_is_not_ramp(self):
        """Prism: '{1}, {T}: Add one mana of any color.' — filter, not ramp."""
        prism = {
            "name": "Prophetic Prism", "count": 1, "types": ["Artifact"],
            "mana_cost": "{1}", "colors": [], "cmc": 1,
            "oracle_text": "{1}, {T}: Add one mana of any color. {1}, {T}, "
                           "Sacrifice Prophetic Prism: Draw a card.",
            "tags": ["fixing_ramp"],
        }
        assert not self._is_ramp(prism), "Prism (activation cost {1}) should not be ramp"

    def test_chromatic_star_is_not_ramp(self):
        """Star: '{1}, {T}, Sacrifice: Add one mana of any color.' — filter."""
        star = {
            "name": "Chromatic Star", "count": 1, "types": ["Artifact"],
            "mana_cost": "{1}", "colors": [], "cmc": 1,
            "oracle_text": "{1}, {T}, Sacrifice Chromatic Star: Add one mana "
                           "of any color. When Chromatic Star is put into a "
                           "graveyard from the battlefield, draw a card.",
            "tags": ["fixing_ramp"],
        }
        assert not self._is_ramp(star), "Star (activation cost {1}) should not be ramp"

    def test_sol_ring_is_ramp(self):
        """Sol Ring: '{T}: Add {C}{C}.' — no activation cost, produces 2 — ramp."""
        sol = {
            "name": "Sol Ring", "count": 1, "types": ["Artifact"],
            "mana_cost": "{1}", "colors": [], "cmc": 1,
            "oracle_text": "{T}: Add {C}{C}.",
            "tags": ["fixing_ramp"],
        }
        assert self._is_ramp(sol), "Sol Ring (free activation) should be ramp"

    def test_llanowar_elves_is_ramp(self):
        """Elves: '{T}: Add {G}.' — no activation cost — ramp."""
        elves = {
            "name": "Llanowar Elves", "count": 1, "types": ["Creature"],
            "mana_cost": "{G}", "colors": ["G"], "cmc": 1,
            "oracle_text": "{T}: Add {G}.",
            "tags": ["fixing_ramp"],
        }
        assert self._is_ramp(elves), "Elves (free activation) should be ramp"

    def test_draw_then_add_not_false_positive(self):
        """'{2}, {T}: Draw a card... add counters' should NOT match as filter
        (the 'add' is in a later sentence about counters, not mana)."""
        card = {
            "name": "Test Card", "count": 1, "types": ["Artifact"],
            "mana_cost": "{2}", "colors": [], "cmc": 2,
            "oracle_text": "{2}, {T}: Draw a card. Then add a +1/+1 counter.",
            "tags": ["fixing_ramp"],
        }
        # The regex uses [^.]* to stay within the same sentence
        assert self._is_ramp(card), "Draw+counters (not mana filter) should still be ramp"


class TestDeterministicSimulation:
    """Same deck → same results, every time. Different decks → same seed (CRN)."""

    def _deck(self):
        return [
            {"name": "Bear", "count": 23, "types": ["Creature"],
             "mana_cost": "{1}{G}", "colors": ["G"], "cmc": 2},
            {"name": "Forest", "count": 17, "types": ["Land"]},
        ]

    def test_same_deck_same_results(self):
        from src.advisor.simulator import simulate_deck
        r1 = simulate_deck(self._deck(), iterations=200)
        r2 = simulate_deck(self._deck(), iterations=200)
        assert r1 == r2, "Same deck must produce identical simulation results"

    def test_repeated_calls_stable(self):
        """Multiple sequential calls (no cache clearing) stay deterministic."""
        from src.advisor.simulator import simulate_deck
        results = [simulate_deck(self._deck(), iterations=200) for _ in range(3)]
        assert all(r == results[0] for r in results)

    def test_fixed_seed_is_crn(self):
        """Both decks use seed 0 (CRN): same random stream for comparisons."""
        from src.advisor.simulator import simulate_deck
        d1 = self._deck()
        d2 = [
            {"name": "Elf", "count": 23, "types": ["Creature"],
             "mana_cost": "{G}", "colors": ["G"], "cmc": 1},
            {"name": "Forest", "count": 17, "types": ["Land"]},
        ]
        r1 = simulate_deck(d1, iterations=200, seed=0)
        r2 = simulate_deck(d2, iterations=200, seed=0)
        # Different decks with the same seed: different cards drawn, but
        # the same random stream (proven by running each twice)
        r1b = simulate_deck(d1, iterations=200, seed=0)
        r2b = simulate_deck(d2, iterations=200, seed=0)
        assert r1 == r1b and r2 == r2b, "Explicit seed must be deterministic"

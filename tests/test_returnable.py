"""
tests/test_returnable.py
Unit tests for the wheel/returnable indicator logic in retrieve_current_pack_cards.

In an 8-player draft:
  pack_index    = (current_pick - 1) % 8
  return_pick   = (slot_index + 1) + 8

A card in slot i is returnable only if:
  - return_pick > current_pick
  - the user did NOT already pick it from slot i
"""

import pytest
from src.log_scanner import ArenaScanner


@pytest.fixture
def scanner(tmp_path):
    """Fresh scanner with retrieve_unknown=True so any string ID is its own card name."""
    s = ArenaScanner(str(tmp_path / "Player.log"), [], retrieve_unknown=True)
    s.log_enable(False)
    return s


def _setup(scanner, *, current_pick, current_pack_cards, initial_pack=None, picked_cards=None):
    """
    Inject scanner state for returnable tests.

    current_pack_cards  - list of card IDs in the pack the user is currently seeing
    initial_pack        - dict of {slot_index: [card_ids]} for other slots
    picked_cards        - dict of {slot_index: [card_ids]} the user has already picked
    """
    scanner.current_pick = current_pick
    pack_index = (current_pick - 1) % 8

    scanner.pack_cards = [[] for _ in range(8)]
    scanner.pack_cards[pack_index] = list(current_pack_cards)

    scanner.initial_pack = [[] for _ in range(8)]
    for i, ids in (initial_pack or {}).items():
        scanner.initial_pack[i] = list(ids)

    scanner.picked_cards = [[] for _ in range(8)]
    for i, ids in (picked_cards or {}).items():
        scanner.picked_cards[i] = list(ids)

    scanner.taken_cards = [c for ids in (picked_cards or {}).values() for c in ids]


def _returnable(scanner):
    """Returns {card_name: returnable_at_list} for the current pack."""
    return {c["name"]: c.get("returnable_at", []) for c in scanner.retrieve_current_pack_cards()}


# ---------------------------------------------------------------------------
# Basic returnable behaviour
# ---------------------------------------------------------------------------

def test_no_other_slots_means_no_returnable(scanner):
    """Card in pack with no other initial_pack slots → not returnable."""
    _setup(scanner, current_pick=2, current_pack_cards=["card_a"])
    assert _returnable(scanner)["card_a"] == []


def test_card_in_future_slot_is_returnable(scanner):
    """Card appearing in a slot whose return_pick is still ahead → marked returnable."""
    # pick 2 → pack_index=1.  slot 0 returns at pick 9.
    _setup(
        scanner,
        current_pick=2,
        current_pack_cards=["card_a"],
        initial_pack={0: ["card_a", "card_b"]},
    )
    assert _returnable(scanner)["card_a"] == [9]


def test_card_not_in_other_slot_has_no_returnable(scanner):
    """Card in pack but absent from all other slots → not returnable."""
    _setup(
        scanner,
        current_pick=2,
        current_pack_cards=["card_a"],
        initial_pack={0: ["card_b", "card_c"]},
    )
    assert _returnable(scanner)["card_a"] == []


# ---------------------------------------------------------------------------
# User-picked card suppression
# ---------------------------------------------------------------------------

def test_picked_card_not_returnable(scanner):
    """
    Card A picked at pick 1 (slot 0). At pick 2, card A is in the pack.
    Slot 0 would return at pick 9 — but user already took it, so no ⟳.
    """
    _setup(
        scanner,
        current_pick=2,
        current_pack_cards=["card_a"],
        initial_pack={0: ["card_a", "card_b"]},
        picked_cards={0: ["card_a"]},
    )
    assert _returnable(scanner)["card_a"] == []


def test_different_card_picked_from_slot_does_not_suppress(scanner):
    """
    User picked card_b from slot 0. Card_a is still in slot 0 → still returnable.
    """
    _setup(
        scanner,
        current_pick=2,
        current_pack_cards=["card_a"],
        initial_pack={0: ["card_a", "card_b"]},
        picked_cards={0: ["card_b"]},
    )
    assert _returnable(scanner)["card_a"] == [9]


def test_picked_from_different_slot_does_not_suppress(scanner):
    """
    User picked card_a from slot 2 (a different slot). The copy in slot 0 is
    still there and should still be marked returnable.
    """
    # pick 3 → pack_index=2.  slot 0 returns at 9, slot 1 returns at 10.
    _setup(
        scanner,
        current_pick=3,
        current_pack_cards=["card_a"],
        initial_pack={0: ["card_a"], 1: ["card_x"]},
        picked_cards={2: ["card_a"]},   # picked from the current slot, not slot 0
    )
    assert _returnable(scanner)["card_a"] == [9]


# ---------------------------------------------------------------------------
# User's concrete example
# ---------------------------------------------------------------------------

def test_user_example_taken_pick1_no_returnable_at_pick2(scanner):
    """
    Card A taken at pick 1 (slot 0). At pick 2, card A appears in the pack.
    Slot 0 would return at pick 9 — but user already has it → no ⟳.
    """
    _setup(
        scanner,
        current_pick=2,
        current_pack_cards=["card_a", "card_b"],
        initial_pack={0: ["card_a", "card_c"]},
        picked_cards={0: ["card_a"]},
    )
    result = _returnable(scanner)
    assert result["card_a"] == [], "card_a was picked; should not be returnable"
    assert result["card_b"] == [], "card_b not in any other slot"


def test_user_example_not_taken_pick2_returnable_at_pick3(scanner):
    """
    Card A not taken at pick 2 (slot 1). At pick 3, card A appears in the pack.
    Slot 1 returns at pick 10 — user never took it → ⟳ at pick 10.
    """
    _setup(
        scanner,
        current_pick=3,
        current_pack_cards=["card_a", "card_b"],
        initial_pack={1: ["card_a", "card_c"]},
        picked_cards={},   # user picked nothing from slot 1
    )
    result = _returnable(scanner)
    assert result["card_a"] == [10], "card_a should be returnable at pick 10"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_return_pick_already_passed_not_returnable(scanner):
    """Slot whose return_pick <= current_pick is ignored."""
    # pick 10 → pack_index=1.  slot 0 returns at 9, which is <= 10 → not returnable.
    _setup(
        scanner,
        current_pick=10,
        current_pack_cards=["card_a"],
        initial_pack={0: ["card_a"]},
    )
    assert _returnable(scanner)["card_a"] == []


def test_multiple_returnable_slots(scanner):
    """Card appearing in two future slots → both return picks listed, sorted."""
    # pick 1 → pack_index=0.  slot 1 returns at 10, slot 2 returns at 11.
    _setup(
        scanner,
        current_pick=1,
        current_pack_cards=["card_a"],
        initial_pack={1: ["card_a"], 2: ["card_a"]},
    )
    assert _returnable(scanner)["card_a"] == [10, 11]


def test_multiple_returnable_slots_one_picked(scanner):
    """Card in two future slots but user picked it from one → only the other listed."""
    _setup(
        scanner,
        current_pick=1,
        current_pack_cards=["card_a"],
        initial_pack={1: ["card_a"], 2: ["card_a"]},
        picked_cards={1: ["card_a"]},
    )
    assert _returnable(scanner)["card_a"] == [11]


def test_current_pack_slot_excluded_from_returnable(scanner):
    """The slot currently being viewed is never counted as a return source."""
    # pick 1 → pack_index=0.  initial_pack[0] contains card_a but that's the
    # current slot — it must not create a spurious returnable entry.
    _setup(
        scanner,
        current_pick=1,
        current_pack_cards=["card_a"],
        initial_pack={0: ["card_a"]},   # same slot as pack_index
    )
    assert _returnable(scanner)["card_a"] == []


def test_unrelated_cards_in_other_slots_not_marked(scanner):
    """Cards present only in the current pack and not in any other slot → no returnable."""
    _setup(
        scanner,
        current_pick=2,
        current_pack_cards=["card_a", "card_b", "card_c"],
        initial_pack={0: ["card_x", "card_y"]},
    )
    result = _returnable(scanner)
    assert result["card_a"] == []
    assert result["card_b"] == []
    assert result["card_c"] == []

import pytest
from unittest.mock import MagicMock
from src.log_scanner import ArenaScanner
from src.constants import LIMITED_TYPE_DRAFT_PREMIER_V2


@pytest.fixture
def scanner():
    s = ArenaScanner("mock.log", MagicMock(), retrieve_unknown=False)
    s.draft_type = LIMITED_TYPE_DRAFT_PREMIER_V2
    return s


def test_stale_pool_wipe_different_draft_id(scanner):
    """If Arena logs a completely new Transaction ID, wipe everything immediately."""
    scanner.current_draft_id = "draft_A"
    scanner.taken_cards = ["1", "2", "3"]
    scanner.current_pack = 1
    scanner.current_pick = 3

    # Provide new draft ID
    scanner._check_and_wipe_stale_pool(
        pack=1, pick=1, current_cards=["4", "5"], draft_id="draft_B"
    )

    assert len(scanner.taken_cards) == 0
    assert scanner.current_pack == 0
    assert scanner.current_draft_id == "draft_B"


def test_stale_pool_wipe_time_travel_backwards(scanner):
    """If we see an older pack/pick than our current state, and the cards don't match our history, it's a stale restart."""
    scanner.current_draft_id = ""  # No ID provided by log
    scanner.current_pack = 2
    scanner.current_pick = 5
    scanner.taken_cards = ["1"] * 20

    # Force the scanner into the time-travel logic block by providing a new draft ID
    # but mocking _load_state to simulate a successful load (so wipe starts False)
    scanner._load_state = MagicMock(return_value=True)

    # We suddenly see Pack 1 Pick 1, but we already have 20 cards. WIPE!
    scanner._check_and_wipe_stale_pool(
        pack=1, pick=1, current_cards=["99", "100"], draft_id="draft_B"
    )

    assert len(scanner.taken_cards) == 0
    assert scanner.current_pack == 0


def test_load_state_normalizes_legacy_string_draft_type(tmp_path):
    """States saved before v4.19 could persist an event-name string (e.g.
    "ContenderDraft") as draft_type, which matches no parser dispatch branch.
    Loading must coerce it to the int type code."""
    import json
    from src import constants

    state_file = tmp_path / "active_draft_state.json"
    state_file.write_text(
        json.dumps(
            {
                "draft_type": "ContenderDraft",
                "current_draft_id": "draft_A",
                "event_string": "ContenderDraft_MSH_20260707",
            }
        )
    )

    s = ArenaScanner("mock.log", MagicMock(), retrieve_unknown=False)
    s.state_file = str(state_file)
    assert s._load_state() is True
    assert s.draft_type == constants.LIMITED_TYPE_DRAFT_CONTENDER


def test_stale_pool_no_wipe_historical_replay(scanner):
    """If we time-travel backwards but the cards MATCH our history exactly, DO NOT WIPE. We are just re-parsing the log."""
    scanner.current_draft_id = ""
    scanner.current_pack = 2
    scanner.current_pick = 5
    scanner.taken_cards = ["1"] * 20

    # Build a matching history
    scanner.draft_history = [{"Pack": 1, "Pick": 2, "Cards": ["A", "B", "C"]}]

    # We see P1P2 again, and the cards match our history.
    scanner._check_and_wipe_stale_pool(
        pack=1, pick=2, current_cards=["B"], draft_id=None
    )

    # Pool should NOT be wiped
    assert len(scanner.taken_cards) == 20


def test_idless_new_pack_resets_old_pool_even_with_shared_card(scanner):
    scanner.current_draft_id = ""
    scanner.current_pack = scanner.previous_scanned_pack = 3
    scanner.current_pick = 10
    scanner.taken_cards = ["old"] * 35
    scanner.draft_history = [{"Pack": 1, "Pick": 1, "Cards": ["shared", "old"]}]
    assert scanner._process_pack_data(1, 1, ["shared", "new"])
    assert scanner.taken_cards == []
    assert (scanner.current_pack, scanner.current_pick) == (1, 1)


def test_idless_p1p1_replay_preserves_completed_pool(scanner):
    scanner.current_draft_id = ""
    scanner.current_pack = scanner.previous_scanned_pack = 3
    scanner.current_pick = 10
    scanner.taken_cards = ["old"] * 35
    scanner.draft_history = [{"Pack": 1, "Pick": 1, "Cards": ["a", "b"]}]
    assert not scanner._process_pack_data(1, 1, ["a", "b"])
    assert len(scanner.taken_cards) == 35


def test_idless_first_pick_not_erased_by_repeated_first_pack(scanner):
    scanner.current_draft_id = ""
    scanner.current_pack = scanner.previous_scanned_pack = 1
    scanner.current_pick = 1
    scanner.taken_cards = ["a"]
    scanner.draft_history = [{"Pack": 1, "Pick": 1, "Cards": ["a", "b"]}]
    scanner._process_pack_data(1, 1, ["a", "b"])
    assert scanner.taken_cards == ["a"]


def test_idless_full_scan_keeps_picks_processed_before_pack_history(scanner):
    scanner.clear_draft(False)
    assert scanner._process_pick_data(1, 1, ["a"])
    assert scanner._process_pick_data(1, 2, ["b"])
    scanner._process_pack_data(1, 1, ["a", "other"])
    scanner._process_pack_data(1, 2, ["b", "new"])
    assert scanner.taken_cards == ["a", "b"]
    assert (scanner.current_pack, scanner.current_pick) == (1, 2)

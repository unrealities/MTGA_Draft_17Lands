"""
tests/test_log_scanner.py
Test suite for the ArenaScanner class logic.
"""

import pytest
import os
from unittest.mock import patch, MagicMock
from src.log_scanner import ArenaScanner
from tests.test_log_scanner_data import (
    TEST_SETS,
    TDM_PREMIER_DRAFT_ENTRIES_2025_4_8,
    OTJ_PREMIER_DRAFT_ENTRIES_2024_5_7,
    MKM_PREMIER_DRAFT_ENTRIES,
    OTJ_QUICK_DRAFT_ENTRIES,
    DMU_QUICK_DRAFT_ENTRIES_2024_5_7,
    TDM_QUICK_DRAFT_ENTRIES_2025_4_8,
    OTJ_TRAD_DRAFT_ENTRIES_2024_5_7,
    DSK_SEALED_ENTRIES_2024_9_24,
    ARENA_OPEN_TEST_ENTRIES,
    DSK_SEALED_NAVIGATION_ENTRY,
    OM1_PICK_TWO_PREMIER_DRAFT_ENTRIES,
    POWERED_CUBE_DRAFT_ENTRIES,
    # ADDED MISSING IMPORTS BELOW
    OTJ_EVENT_ENTRY,
    OTJ_P1P1_ENTRY,
    OTJ_P1P1_CARD_NAMES,
    OTJ_PREMIER_SNAPSHOT,
)

TEST_LOG_DIRECTORY = os.path.join(os.getcwd(), "tests")
TEST_LOG_FILE_LOCATION = os.path.join(os.getcwd(), "tests", "Player.log")
TEST_SETS_DIRECTORY = os.path.join(os.getcwd(), "tests", "data")


@pytest.fixture(name="session_scanner", scope="session")
def fixture_session_scanner():
    scanner = ArenaScanner(
        TEST_LOG_FILE_LOCATION,
        TEST_SETS,
        sets_location=TEST_LOG_DIRECTORY,
        retrieve_unknown=True,
    )
    scanner.log_enable(False)
    yield scanner
    if os.path.exists(TEST_LOG_FILE_LOCATION):
        os.remove(TEST_LOG_FILE_LOCATION)


@pytest.fixture(name="function_scanner", scope="function")
def fixture_function_scanner():
    if os.path.exists(TEST_LOG_FILE_LOCATION):
        os.remove(TEST_LOG_FILE_LOCATION)
    scanner = ArenaScanner(
        TEST_LOG_FILE_LOCATION,
        TEST_SETS,
        sets_location=TEST_SETS_DIRECTORY,
        retrieve_unknown=False,
    )
    scanner.log_enable(False)
    yield scanner
    if os.path.exists(TEST_LOG_FILE_LOCATION):
        os.remove(TEST_LOG_FILE_LOCATION)


def event_test_cases(
    input_scanner, event_label, entry_label, expected, entry_string, mock_ocr
):
    """Generic test cases for verifying the log events"""
    # Write the entry to the fake Player.log file
    with open(
        TEST_LOG_FILE_LOCATION, "a", encoding="utf-8", errors="replace"
    ) as log_file:
        log_file.write(f"{entry_string}\n")

    # Verify that a new event was detected
    new_event = input_scanner.draft_start_search()
    assert (
        expected.new_event == new_event
    ), f"Test Failed: New Event, Set: {event_label}, {entry_label}, Expected: {expected.new_event}, Actual: {new_event}"

    # Verify that new event data was collected
    data_update = input_scanner.draft_data_search(False, False)
    assert (
        expected.data_update == data_update
    ), f"Test Failed: Data Update, Set: {event_label}, {entry_label}, Expected: {expected.data_update}, Actual: {data_update}"

    # Verify the current set and event
    current_set, current_event = input_scanner.retrieve_current_limited_event()
    assert (expected.current_set, expected.current_event) == (
        current_set,
        current_event,
    ), f"Test Failed: Set and Event, Set: {event_label}, {entry_label}, Expected: {(expected.current_set, expected.current_event)}, Actual: {(current_set, current_event)}"

    # Verify the current pack, pick
    current_pack, current_pick = input_scanner.retrieve_current_pack_and_pick()
    assert (expected.current_pack, expected.current_pick) == (
        current_pack,
        current_pick,
    ), f"Test Failed: Pack/Pick, Set: {event_label}, {entry_label}, Expected: {(expected.current_pack, expected.current_pick)}, Actual: {(current_pack, current_pick)}"

    # Verify the pack cards
    pack = [x["name"] for x in input_scanner.retrieve_current_pack_cards()]
    assert (
        expected.pack == pack
    ), f"Test Failed: Pack Cards, Set: {event_label}, {entry_label}, Expected: {expected.pack}, Actual: {pack}"

    # Verify the card pool
    card_pool = [x["name"] for x in input_scanner.retrieve_taken_cards()]
    assert (
        expected.card_pool == card_pool
    ), f"Test Failed: Card Pool, Set: {event_label}, {entry_label}, Expected: {expected.card_pool}, Actual: {card_pool}"

    # Verify the missing cards
    missing = [x["name"] for x in input_scanner.retrieve_current_missing_cards()]
    assert (
        expected.missing == missing
    ), f"Test Failed: Missing, Set: {event_label}, {entry_label}, Expected: {expected.missing}, Actual: {missing}"

    # Verify picks
    picks = [x["name"] for x in input_scanner.retrieve_current_picked_cards()]
    assert (
        expected.picks == picks
    ), f"Test Failed: Picks, Set: {event_label}, {entry_label}, Expected: {expected.picks}, Actual: {picks}"

    # Verify that the OCR method wasn't called
    assert (
        mock_ocr.call_count == 0
    ), f"Test Failed: OCR Check, Set: {event_label}, {entry_label}, Expected: 0, Actual: {mock_ocr.call_count}"


@pytest.mark.parametrize(
    "entry_label, expected, entry_string", TDM_PREMIER_DRAFT_ENTRIES_2025_4_8
)
def test_tdm_premier_draft_new(session_scanner, entry_label, expected, entry_string):
    with (
        patch("src.log_scanner.OCR.get_pack") as mock_ocr,
        patch("src.log_scanner.capture_screen_base64str"),
    ):
        event_test_cases(
            session_scanner,
            "New TDM PremierDraft",
            entry_label,
            expected,
            entry_string,
            mock_ocr,
        )


@pytest.mark.parametrize(
    "entry_label, expected, entry_string", OTJ_PREMIER_DRAFT_ENTRIES_2024_5_7
)
def test_otj_premier_draft_new(session_scanner, entry_label, expected, entry_string):
    with (
        patch("src.log_scanner.OCR.get_pack") as mock_ocr,
        patch("src.log_scanner.capture_screen_base64str"),
    ):
        event_test_cases(
            session_scanner,
            "New OTJ PremierDraft",
            entry_label,
            expected,
            entry_string,
            mock_ocr,
        )


@pytest.mark.parametrize(
    "entry_label, expected, entry_string", MKM_PREMIER_DRAFT_ENTRIES
)
def test_mkm_premier_draft_old(session_scanner, entry_label, expected, entry_string):
    with (
        patch("src.log_scanner.OCR.get_pack") as mock_ocr,
        patch("src.log_scanner.capture_screen_base64str"),
    ):
        event_test_cases(
            session_scanner,
            "Old MKM PremierDraft",
            entry_label,
            expected,
            entry_string,
            mock_ocr,
        )


@pytest.mark.parametrize(
    "entry_label, expected, entry_string", TDM_QUICK_DRAFT_ENTRIES_2025_4_8
)
def test_tdm_quick_draft_new(session_scanner, entry_label, expected, entry_string):
    with (
        patch("src.log_scanner.OCR.get_pack") as mock_ocr,
        patch("src.log_scanner.capture_screen_base64str"),
    ):
        event_test_cases(
            session_scanner,
            "New TDM QuickDraft",
            entry_label,
            expected,
            entry_string,
            mock_ocr,
        )


@pytest.mark.parametrize(
    "entry_label, expected, entry_string", DMU_QUICK_DRAFT_ENTRIES_2024_5_7
)
def test_dmu_quick_draft_new(session_scanner, entry_label, expected, entry_string):
    with (
        patch("src.log_scanner.OCR.get_pack") as mock_ocr,
        patch("src.log_scanner.capture_screen_base64str"),
    ):
        event_test_cases(
            session_scanner,
            "New DMU QuickDraft",
            entry_label,
            expected,
            entry_string,
            mock_ocr,
        )


@pytest.mark.parametrize("entry_label, expected, entry_string", OTJ_QUICK_DRAFT_ENTRIES)
def test_mkm_quick_draft_old(session_scanner, entry_label, expected, entry_string):
    with (
        patch("src.log_scanner.OCR.get_pack") as mock_ocr,
        patch("src.log_scanner.capture_screen_base64str"),
    ):
        event_test_cases(
            session_scanner,
            "Old OTJ QuickDraft",
            entry_label,
            expected,
            entry_string,
            mock_ocr,
        )


@pytest.mark.parametrize(
    "entry_label, expected, entry_string", OTJ_TRAD_DRAFT_ENTRIES_2024_5_7
)
def test_quick_trad_draft_old(session_scanner, entry_label, expected, entry_string):
    with (
        patch("src.log_scanner.OCR.get_pack") as mock_ocr,
        patch("src.log_scanner.capture_screen_base64str"),
    ):
        event_test_cases(
            session_scanner,
            "New OTJ TradDraft",
            entry_label,
            expected,
            entry_string,
            mock_ocr,
        )


@pytest.mark.parametrize("entry_label, expected, entry_string", ARENA_OPEN_TEST_ENTRIES)
def test_arena_open(function_scanner, entry_label, expected, entry_string):
    with (
        patch("src.log_scanner.OCR.get_pack") as mock_ocr,
        patch("src.log_scanner.capture_screen_base64str"),
    ):
        event_test_cases(
            function_scanner,
            "Arena Open",
            entry_label,
            expected,
            entry_string,
            mock_ocr,
        )


@pytest.mark.parametrize(
    "entry_label, expected, entry_string", DSK_SEALED_ENTRIES_2024_9_24
)
def test_dsk_sealed(session_scanner, entry_label, expected, entry_string):
    with (
        patch("src.log_scanner.OCR.get_pack") as mock_ocr,
        patch("src.log_scanner.capture_screen_base64str"),
    ):
        event_test_cases(
            session_scanner,
            "New DSK Sealed",
            entry_label,
            expected,
            entry_string,
            mock_ocr,
        )


@pytest.mark.parametrize(
    "entry_label, expected, entry_string", DSK_SEALED_NAVIGATION_ENTRY
)
def test_dsk_sealed_navigation(function_scanner, entry_label, expected, entry_string):
    if "Duplicate" in entry_label:
        function_scanner.event_string = "Sealed_DSK_20240924"
        function_scanner.draft_sets = ["DSK"]
        function_scanner.draft_label = "Sealed"

    with (
        patch("src.log_scanner.OCR.get_pack") as mock_ocr,
        patch("src.log_scanner.capture_screen_base64str"),
    ):
        event_test_cases(
            function_scanner,
            "DSK Sealed Navigation",
            entry_label,
            expected,
            entry_string,
            mock_ocr,
        )


@pytest.mark.parametrize(
    "entry_label, expected, entry_string", OM1_PICK_TWO_PREMIER_DRAFT_ENTRIES
)
def test_om1_pick_two_premier(session_scanner, entry_label, expected, entry_string):
    with (
        patch("src.log_scanner.OCR.get_pack") as mock_ocr,
        patch("src.log_scanner.capture_screen_base64str"),
    ):
        event_test_cases(
            session_scanner,
            "Pick Two OM1 Premier Draft ",
            entry_label,
            expected,
            entry_string,
            mock_ocr,
        )


@pytest.mark.parametrize(
    "entry_label, expected, entry_string", POWERED_CUBE_DRAFT_ENTRIES
)
def test_powered_cube_premier(session_scanner, entry_label, expected, entry_string):
    with (
        patch("src.log_scanner.OCR.get_pack") as mock_ocr,
        patch("src.log_scanner.capture_screen_base64str"),
    ):
        event_test_cases(
            session_scanner,
            "Powered Cube Premier Draft ",
            entry_label,
            expected,
            entry_string,
            mock_ocr,
        )


@patch("src.log_scanner.OCR.get_pack")
@patch("src.log_scanner.capture_screen_base64str")
def test_otj_premier_p1p1_ocr_overwrite(mock_screenshot, mock_ocr, function_scanner):
    # Write the event entry to the fake Player.log file
    with open(
        TEST_LOG_FILE_LOCATION, "a", encoding="utf-8", errors="replace"
    ) as log_file:
        log_file.write(f"{OTJ_EVENT_ENTRY}\n")

    # Search for the event
    function_scanner.draft_start_search()

    # Open the dataset
    function_scanner.retrieve_set_data(OTJ_PREMIER_SNAPSHOT)

    # Mock the card names returned by the OCR get_pack method
    expected_names = ["Seraphic Steed", "Spinewoods Armadillo", "Sterling Keykeeper"]
    mock_ocr.return_value = expected_names
    mock_screenshot.return_value = 0

    function_scanner.draft_data_search(True, False)

    # Verify the current pack, pick
    current_pack, current_pick = function_scanner.retrieve_current_pack_and_pick()
    assert (1, 1) == (
        current_pack,
        current_pick,
    ), f"OCT Test Failed: OCR Pack/Pick, Set: OTJ, Expected: {(1,1)}, Actual: {(current_pack, current_pick)}"

    # Verify the pack cards
    card_names = [x["name"] for x in function_scanner.retrieve_current_pack_cards()]
    assert (
        expected_names == card_names
    ), f"OCR Test Failed: OCR Pack Cards, Set: OTJ, Expected: {expected_names}, Actual: {card_names}"

    # Write the P1P1 entry to the fake Player.log file
    with open(
        TEST_LOG_FILE_LOCATION, "a", encoding="utf-8", errors="replace"
    ) as log_file:
        log_file.write(f"{OTJ_P1P1_ENTRY}\n")

    # Update the ArenaScanner results
    function_scanner.draft_data_search(False, False)

    # Verify that P1P1 is overwritten when the log entry is received
    card_names = [x["name"] for x in function_scanner.retrieve_current_pack_cards()]
    assert (
        OTJ_P1P1_CARD_NAMES == card_names
    ), f"OCR Test Failed: Log Pack Cards, Set: OTJ, Expected: {OTJ_P1P1_CARD_NAMES}, Actual: {card_names}"

    # Verify that the OCR method was only called once
    assert mock_ocr.call_count == 1


@patch("src.log_scanner.OCR.get_pack")
@patch("src.log_scanner.capture_screen_base64str")
def test_otj_premier_p1p1_ocr_multiclick(mock_screenshot, mock_ocr, function_scanner):
    # Write the event entry to the fake Player.log file
    with open(
        TEST_LOG_FILE_LOCATION, "a", encoding="utf-8", errors="replace"
    ) as log_file:
        log_file.write(f"{OTJ_EVENT_ENTRY}\n")

    # Search for the event
    function_scanner.draft_start_search()

    # Open the dataset
    function_scanner.retrieve_set_data(OTJ_PREMIER_SNAPSHOT)

    # Mock the card names returned by the OCR get_pack method
    expected_names = ["Seraphic Steed", "Spinewoods Armadillo", "Sterling Keykeeper"]
    mock_ocr.return_value = expected_names
    mock_screenshot.return_value = 0

    function_scanner.draft_data_search(True, False)

    # Verify the current pack, pick
    current_pack, current_pick = function_scanner.retrieve_current_pack_and_pick()
    assert (1, 1) == (
        current_pack,
        current_pick,
    ), f"OCR Test Failed: OCR Pack/Pick, Set: OTJ, Expected: {(1,1)}, Actual: {(current_pack, current_pick)}"

    # Verify the pack cards
    card_names = [x["name"] for x in function_scanner.retrieve_current_pack_cards()]
    assert (
        expected_names == card_names
    ), f"OCR Test Failed: OCR Pack Cards, Set: OTJ, Expected: {expected_names}, Actual: {card_names}"

    # Simulate refresh clicks
    function_scanner.draft_data_search(True, False)
    function_scanner.draft_data_search(True, False)

    # Verify that the OCR method was only called once
    assert mock_ocr.call_count == 1


@patch("src.log_scanner.OCR.get_pack")
@patch("src.log_scanner.capture_screen_base64str")
def test_otj_premier_p1p1_ocr_disabled(mock_screenshot, mock_ocr, function_scanner):
    # Write the event entry to the fake Player.log file
    with open(
        TEST_LOG_FILE_LOCATION, "a", encoding="utf-8", errors="replace"
    ) as log_file:
        log_file.write(f"{OTJ_EVENT_ENTRY}\n")

    # Search for the event
    function_scanner.draft_start_search()

    # Open the dataset
    function_scanner.retrieve_set_data(OTJ_PREMIER_SNAPSHOT)

    # P1P1_OCR is disabled
    function_scanner.draft_data_search(False, False)

    # Verify that the OCR method was not called
    assert mock_ocr.call_count == 0
    mock_screenshot.return_value = 0


def test_scanner_retrieve_color_win_rate_mismatch_handling():
    """
    Verify that ArenaScanner correctly maps dataset keys to UI labels even if they are stored differently.
    """
    scanner = ArenaScanner("log.txt", MagicMock(), retrieve_unknown=False)

    # Mock dataset returning ratings with normalized keys (e.g., "WG")
    scanner.set_data.get_color_ratings = MagicMock(
        return_value={"WG": 55.5, "WR": 60.0}
    )

    # Mock constants to simulate the issue: DECK_FILTERS has "GW" (non-standard), data has "WG"
    with patch("src.constants.DECK_FILTERS", ["GW", "WR", "All Decks"]):
        deck_colors = scanner.retrieve_color_win_rate("Colors")

        # The key in the returned dict is the UI Label.
        # Since the code normalizes "GW" to "WG", the label becomes "WG (55.5%)"
        expected_label = "WG (55.5%)"

        # Verify the mapping exists: { Label : Original Filter Key }
        assert expected_label in deck_colors
        assert deck_colors[expected_label] == "GW"


def test_draft_history_recording(function_scanner):
    """
    Verify that draft history is recorded correctly across multiple packs/picks.
    """
    # 1. Simulate Event Start
    with open(
        TEST_LOG_FILE_LOCATION, "a", encoding="utf-8", errors="replace"
    ) as log_file:
        log_file.write(f"{OTJ_EVENT_ENTRY}\n")
    function_scanner.draft_start_search()

    # 2. Simulate P1P1 (Pack Data)
    with open(
        TEST_LOG_FILE_LOCATION, "a", encoding="utf-8", errors="replace"
    ) as log_file:
        log_file.write(f"{OTJ_P1P1_ENTRY}\n")
    function_scanner.draft_data_search(False, False)

    history = function_scanner.retrieve_draft_history()
    assert len(history) == 1
    assert history[0]["Pack"] == 1
    assert history[0]["Pick"] == 1
    # Check that card IDs are present (using OTJ_P1P1_ENTRY data)
    assert "90459" in history[0]["Cards"]  # Vadmir, New Blood

    # 3. Simulate P1P2 (Pack Data) - Note: Using the P1P2 entry that wasn't skipped
    P1P2_VALID_ENTRY = r'[UnityCrossThreadLogger]Draft.Notify {"draftId":"87b408d1-43e0-4fb5-8c74-a1257fde017c","SelfPick":2,"SelfPack":1,"PackCards":"90701,90416,90606,90524,90481,90588,90440,90418,90353,90494,90360,90609,90548"}'

    with open(
        TEST_LOG_FILE_LOCATION, "a", encoding="utf-8", errors="replace"
    ) as log_file:
        log_file.write(f"{P1P2_VALID_ENTRY}\n")
    function_scanner.draft_data_search(False, False)

    history = function_scanner.retrieve_draft_history()
    assert len(history) == 2
    assert history[1]["Pack"] == 1
    assert history[1]["Pick"] == 2
    assert "90701" in history[1]["Cards"]

    # 4. Verify Clear Draft resets history
    function_scanner.clear_draft(True)
    assert len(function_scanner.retrieve_draft_history()) == 0

import threading
from unittest.mock import MagicMock, patch

import pytest
from src import constants
from src.configuration import Configuration
from src.dataset_selection import select_event_dataset
from src.log_scanner import ArenaScanner
from src.ui.orchestrator import DraftOrchestrator
from src.utils import Result


@pytest.fixture
def scanner():
    scanner = MagicMock()
    scanner.lock = threading.RLock()
    scanner.draft_type = constants.LIMITED_TYPE_DRAFT_PREMIER_V2
    scanner.retrieve_current_limited_event.return_value = ("MH3", "PremierDraft")
    scanner.retrieve_data_sources.return_value = {
        "[MH3] Sealed (All)": "sealed.json",
        "[OTJ] PremierDraft (All)": "other-set.json",
        "[MH3] PremierDraft (Top)": "top.json",
        "[MH3] PremierDraft (All)": "premier.json",
    }
    scanner.set_data._dataset = None
    scanner.retrieve_set_data.return_value = Result.VALID
    return scanner


def test_selection_matches_event_and_prefers_all(scanner):
    assert select_event_dataset(scanner) == "premier.json"


def test_explicit_format_and_user_override_preferred_file(scanner):
    assert select_event_dataset(scanner, target_format="Sealed", target_user="All",
                                preferred_filename="premier.json") == "sealed.json"
    assert select_event_dataset(scanner, target_user="Top") == "top.json"
    assert select_event_dataset(scanner, target_user="Bottom") is None


def test_preferred_dataset_is_retained_only_for_matching_event(scanner):
    assert select_event_dataset(scanner, preferred_filename="top.json") == "top.json"
    assert select_event_dataset(scanner, preferred_filename="sealed.json") == "premier.json"


def test_missing_format_does_not_fall_back_to_another_event(scanner):
    scanner.retrieve_data_sources.return_value = {"[MH3] Sealed (All)": "sealed.json"}
    assert select_event_dataset(scanner) is None


def test_group_fallback_stays_within_same_event(scanner):
    scanner.retrieve_data_sources.return_value.pop("[MH3] PremierDraft (All)")
    assert select_event_dataset(scanner) == "top.json"


def test_special_event_uses_underlying_format(scanner):
    scanner.retrieve_current_limited_event.return_value = ("MH3", "OpenDay1")
    scanner.draft_type = constants.LIMITED_TYPE_SEALED
    assert select_event_dataset(scanner) == "sealed.json"


def test_bot_draft_alias_selects_quick_draft_statistics(scanner):
    scanner.retrieve_current_limited_event.return_value = ("MH3", "BotDraft")
    scanner.retrieve_data_sources.return_value = {"[MH3] QuickDraft (All)": "quick.json"}
    assert select_event_dataset(scanner) == "quick.json"
    assert select_event_dataset(scanner, target_format="BotDraft") == "quick.json"


def test_cube_and_custom_dataset_labels(scanner):
    scanner.retrieve_current_limited_event.return_value = ("Cube - Powered", "PremierDraft")
    scanner.retrieve_data_sources.return_value = {
        "[CUBE-POWERED] PremierDraft (All (Last Week))": "cube-custom.json",
    }
    assert select_event_dataset(scanner, target_user="All") == "cube-custom.json"


def test_newest_dataset_wins_among_equal_groups(scanner):
    scanner.retrieve_data_sources.return_value = {
        "[MH3] PremierDraft (All (Last Week))": "new.json",
        "[MH3] PremierDraft (All)": "old.json",
    }
    assert select_event_dataset(scanner) == "new.json"


def test_matching_format_is_ordered_before_newer_wrong_format(scanner):
    files = [
        ("MH3", "PremierDraft", "All", "2026-01-01", "2026-01-02", 100, "premier.json", "2026-01-02"),
        ("MH3", "Sealed", "All", "2026-01-01", "2026-01-03", 100, "sealed.json", "2026-01-03"),
    ]
    with patch("src.log_scanner.retrieve_local_set_list", return_value=(files, [])):
        sources = ArenaScanner.retrieve_data_sources(scanner)
    assert next(iter(sources)) == "[MH3] PremierDraft (All)"


@patch("src.ui.orchestrator.write_configuration")
def test_live_sync_honors_event_and_group(write_config, scanner):
    config = Configuration()
    orchestrator = DraftOrchestrator(scanner, config, MagicMock())
    assert orchestrator.sync_dataset_to_event(target_user="Top")
    scanner.retrieve_set_data.assert_called_once_with("top.json")
    assert config.card_data.latest_dataset == "top.json"
    write_config.assert_called_once_with(config)


@patch("src.ui.orchestrator.write_configuration")
def test_failed_load_is_not_recorded_as_selected(write_config, scanner):
    config = Configuration()
    config.card_data.latest_dataset = "old.json"
    scanner.retrieve_set_data.return_value = Result.ERROR_UNREADABLE_FILE
    orchestrator = DraftOrchestrator(scanner, config, MagicMock())
    assert not orchestrator.sync_dataset_to_event()
    assert config.card_data.latest_dataset == "old.json"
    write_config.assert_not_called()


def test_startup_uses_same_selection_policy(scanner):
    from main import load_event_dataset
    config = Configuration()
    assert load_event_dataset(scanner, config)
    scanner.retrieve_set_data.assert_called_once_with("premier.json")
    assert config.card_data.latest_dataset == "premier.json"


@patch("src.ui.orchestrator.write_configuration")
def test_missing_event_dataset_clears_prior_statistics(write_config, scanner):
    config = Configuration()
    config.card_data.latest_dataset = "sealed.json"
    scanner.retrieve_data_sources.return_value = {"[MH3] Sealed (All)": "sealed.json"}
    orchestrator = DraftOrchestrator(scanner, config, MagicMock())
    assert not orchestrator.sync_dataset_to_event()
    scanner.retrieve_set_data.assert_called_once_with("")
    assert config.card_data.latest_dataset == ""

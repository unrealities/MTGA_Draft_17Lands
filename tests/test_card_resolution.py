"""Card getters stay nonblocking; the resolver retries and discards stale work."""
import threading
from unittest.mock import Mock

import pytest

from src.dataset import Dataset


@pytest.fixture
def dataset(monkeypatch):
    monkeypatch.setattr(Dataset, "_load_custom_cache", lambda self: None)
    monkeypatch.setattr(Dataset, "_save_custom_cache", lambda self: None)
    result = Dataset(retrieve_unknown=True)
    result.skip_unresolved_ids = True
    return result


def response(status=200, cards=None):
    return Mock(status_code=status, json=lambda: {"data": cards or []})


CARD = {"arena_id": 999, "name": "Recovered Card", "type_line": "Creature",
        "colors": ["G"], "cmc": 2, "mana_cost": "{1}{G}"}


def finish(worker):
    assert worker is not None
    worker.join(timeout=3)
    assert not worker.is_alive()


@pytest.mark.parametrize("failure", [TimeoutError("offline"), response(503), response()])
def test_retry_without_log_growth(dataset, monkeypatch, failure):
    clock = [100.0]
    monkeypatch.setattr("src.dataset.time.monotonic", lambda: clock[0])
    post = Mock(side_effect=[failure, response(cards=[CARD])])
    monkeypatch.setattr("requests.post", post)
    refreshed = Mock()
    assert dataset.get_data_by_id([999]) == []
    post.assert_not_called()
    finish(dataset.start_resolution(refreshed))
    assert "999" not in dataset._fallback_ratings
    assert dataset.start_resolution(refreshed) is None
    refreshed.assert_not_called()
    clock[0] = 105.0
    finish(dataset.start_resolution(refreshed))
    assert [c["name"] for c in dataset.get_data_by_id([999, 999])] == ["Recovered Card"] * 2
    assert post.call_count == 2
    refreshed.assert_called_once()


def test_slow_resolution_does_not_block_reads_or_dataset_switch(dataset, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    def slow_post(*args, **kwargs):
        assert threading.current_thread() is not threading.main_thread()
        entered.set()
        assert release.wait(3)
        return response(cards=[CARD])
    monkeypatch.setattr("requests.post", slow_post)
    refreshed = Mock()
    dataset.get_data_by_id([999])
    worker = dataset.start_resolution(refreshed)
    try:
        assert entered.wait(3)
        assert dataset.get_data_by_id([999]) == []
        assert dataset.start_resolution(refreshed) is None
        dataset.clear()
    finally:
        release.set()
        finish(worker)
    assert dataset._fallback_ratings == {}
    refreshed.assert_not_called()


def test_legacy_numeric_cache_entries_are_retried(dataset, monkeypatch):
    dataset._fallback_ratings["999"] = {"name": "999"}
    monkeypatch.setattr("requests.post", Mock(return_value=response(cards=[CARD])))
    assert dataset.get_data_by_id([999]) == []
    finish(dataset.start_resolution(Mock()))
    assert dataset.get_data_by_id([999])[0]["name"] == "Recovered Card"


def test_cached_getter_never_queries_database(dataset, monkeypatch):
    lookup = Mock(side_effect=AssertionError("getter performed IO"))
    monkeypatch.setattr(dataset, "_resolve_unknown_id", lookup)
    assert dataset.get_data_by_id([999]) == []
    lookup.assert_not_called()


def test_diagnostic_placeholder_is_not_cached(dataset):
    dataset.skip_unresolved_ids = False
    assert dataset.get_data_by_id([999])[0]["name"] == "999"
    assert "999" not in dataset._fallback_ratings


def test_cached_alias_uses_current_dataset_statistics(dataset):
    old = {"name": "Known Card", "cmc": 2}
    current = {"name": "Known Card", "cmc": 3}
    dataset._fallback_ratings["999"] = old
    dataset._dataset = {"card_ratings": {"123": current}}
    dataset._name_index = {"Known Card": current}
    assert dataset.get_data_by_id([999]) == [current]


def test_resolution_preserves_existing_rating_snapshot(dataset, monkeypatch):
    dataset._dataset = {"card_ratings": {"123": {"name": "Known Card"}}}
    snapshot = dataset.get_card_ratings()
    monkeypatch.setattr("requests.post", Mock(return_value=response(cards=[CARD])))
    dataset.get_data_by_id([999])
    finish(dataset.start_resolution(Mock()))
    assert "999" not in snapshot
    assert dataset.get_card_ratings()["999"]["name"] == "Recovered Card"


def test_cached_basic_land_normalization_preserved(dataset):
    raw = {"name": "Snow-Covered Island", "types": ["Land"], "colors": []}
    dataset._dataset = {"card_ratings": {"123": raw}}
    card = dataset.get_data_by_id([123])[0]
    assert card["types"] == ["Land", "Basic"]
    assert card["colors"] == ["U"]
    assert raw["colors"] == []


def test_retry_delay_increases_and_is_capped(dataset, monkeypatch):
    clock = [100.0]
    monkeypatch.setattr("src.dataset.time.monotonic", lambda: clock[0])
    monkeypatch.setattr("requests.post", Mock(return_value=response(503)))
    dataset.get_data_by_id([999])
    for delay in [5, 10, 20, 40, 80, 160, 300, 300]:
        finish(dataset.start_resolution(Mock()))
        assert dataset._retry_after["999"] == clock[0] + delay
        clock[0] += delay


def test_load_cache_discards_legacy_failed_lookups(tmp_path, monkeypatch):
    import json
    monkeypatch.setattr("src.constants.SETS_FOLDER", str(tmp_path))
    (tmp_path / "custom_cards.json").write_text(json.dumps({
        "999": {"name": "999"}, "123": {"name": "Known Card"},
    }))
    loaded = Dataset(retrieve_unknown=True)
    assert loaded._fallback_ratings == {"123": {"name": "Known Card"}}

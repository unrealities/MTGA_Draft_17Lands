"""Format-wide regressions for event identity, cached ratings and pick advice.

The real-log fixtures in test_log_scanner.py additionally cover legacy Premier,
human, bot, Sealed, Cube and dynamically detected Pick-Two log protocols.
"""

import json
from unittest.mock import Mock

import pytest

from src import constants as c
from src.advisor.engine import DraftAdvisor
from src.dataset import Dataset
from src.dataset_selection import select_event_dataset
from src.limited_sets import SetDictionary, SetInfo
from src.log_scanner import ArenaScanner
from src.utils import Result


# Explicit expectations, so adding a registered format requires test coverage.
# Event label, scanner type, cards per pick, seats, dataset format.
FORMATS = [
    ("PremierDraft", c.LIMITED_TYPE_DRAFT_PREMIER_V2, 1, 8, "PremierDraft"),
    ("QuickDraft", c.LIMITED_TYPE_DRAFT_QUICK, 1, 8, "QuickDraft"),
    ("BotDraft", c.LIMITED_TYPE_DRAFT_QUICK, 1, 8, "QuickDraft"),
    ("TradDraft", c.LIMITED_TYPE_DRAFT_TRADITIONAL, 1, 8, "TradDraft"),
    ("Sealed", c.LIMITED_TYPE_SEALED, 1, 8, "Sealed"),
    ("TradSealed", c.LIMITED_TYPE_SEALED_TRADITIONAL, 1, 8, "TradSealed"),
    ("PickTwoDraft", c.LIMITED_TYPE_DRAFT_PICK_TWO, 2, 4, "PickTwoDraft"),
    ("PickTwoTradDraft", c.LIMITED_TYPE_DRAFT_PICK_TWO_TRAD, 2, 4, "PickTwoTradDraft"),
    ("PickTwoQuickDraft", c.LIMITED_TYPE_DRAFT_PICK_TWO_QUICK, 2, 4, "PickTwoQuickDraft"),
    ("ContenderDraft", c.LIMITED_TYPE_DRAFT_CONTENDER, 1, 8, "ContenderDraft"),
]
FORMAT_PARAMS = pytest.mark.parametrize(
    "event,kind,cards_per_pick,seats,dataset_format", FORMATS,
    ids=[f[0] for f in FORMATS],
)


def test_format_matrix_covers_registry():
    assert {f[0] for f in FORMATS} == set(c.LIMITED_TYPES_DICT)
    assert set(c.LIMITED_TYPE_LIST) <= {f[0] for f in FORMATS}
    assert {f[1] for f in FORMATS} | {c.LIMITED_TYPE_DRAFT_PREMIER_V1} == {
        value for name, value in vars(c).items()
        if name.startswith(("LIMITED_TYPE_DRAFT_", "LIMITED_TYPE_SEALED"))
        and isinstance(value, int)
    }


@pytest.fixture
def scanner(tmp_path, monkeypatch):
    monkeypatch.setattr(c, "TEMP_FOLDER", str(tmp_path))
    monkeypatch.setattr(c, "SETS_FOLDER", str(tmp_path))
    log = tmp_path / "Player.log"
    log.write_text("")
    sets = SetDictionary(data={
        "OTJ": SetInfo(set_code="OTJ"),
        "Cube - Powered": SetInfo(set_code="CUBE-POWERED"),
    })
    for event in sets.special_events:
        event.set_code = "OTJ"
    return ArenaScanner(str(log), sets, sets_location=str(tmp_path))


def join_event(scanner, event_name):
    request = json.dumps({"EventName": event_name})
    with open(scanner.arena_file, "w") as log:
        log.write("[UnityCrossThreadLogger]==> Event_Join " + json.dumps({
            "id": "format-regression", "request": request,
        }) + "\n")
    assert scanner.draft_start_search()


@FORMAT_PARAMS
def test_event_join_selects_format_and_matching_dataset(
    scanner, event, kind, cards_per_pick, seats, dataset_format,
):
    join_event(scanner, f"{event}_OTJ_20240416")
    assert scanner.draft_type == kind
    assert scanner.cards_per_pick == cards_per_pick
    assert scanner.number_of_players == seats
    scanner.retrieve_data_sources = Mock(return_value={
        f"[OTJ] {fmt} (All)": f"{fmt}.json" for fmt in c.LIMITED_TYPES_DICT
        if fmt != "BotDraft"
    })
    assert select_event_dataset(scanner) == f"{dataset_format}.json"


@pytest.mark.parametrize("event_name,set_code,label,kind,fmt", [
    ("PremierDraft_Cube-Powered_20260401", "CUBE-POWERED", "PremierDraft",
     c.LIMITED_TYPE_DRAFT_PREMIER_V2, "PremierDraft"),
    ("ArenaOpen_OTJ_Day1", "OTJ", "OpenDay1", c.LIMITED_TYPE_SEALED, "Sealed"),
    ("ArenaOpen_OTJ_Day2", "OTJ", "OpenDay2", c.LIMITED_TYPE_DRAFT_PREMIER_V2, "PremierDraft"),
    ("Qualifier_OTJ", "OTJ", "QualSealed", c.LIMITED_TYPE_SEALED, "Sealed"),
    ("Qualifier_Draft_OTJ", "OTJ", "QualDraft", c.LIMITED_TYPE_DRAFT_PREMIER_V2, "PremierDraft"),
    ("Sealed_Trad_OTJ_20240416", "OTJ", "TradSealed", c.LIMITED_TYPE_SEALED_TRADITIONAL, "TradSealed"),
])
def test_cube_and_special_events_keep_their_underlying_format(
    scanner, event_name, set_code, label, kind, fmt,
):
    join_event(scanner, event_name)
    assert scanner.retrieve_current_limited_event() == (set_code, label)
    assert scanner.draft_type == kind
    assert scanner.cards_per_pick == 1
    assert scanner.number_of_players == 8
    scanner.retrieve_data_sources = Mock(return_value={
        f"[{set_code}] {name} (All)": f"{name}.json" for name in c.LIMITED_TYPES_DICT
    })
    assert select_event_dataset(scanner) == f"{fmt}.json"


def test_legacy_premier_protocol_still_takes_one_card(scanner):
    scanner.draft_type = c.LIMITED_TYPE_DRAFT_PREMIER_V1
    assert scanner.cards_per_pick == 1
    assert scanner.number_of_players == 8


@pytest.mark.parametrize(
    "event,kind,cards_per_pick,seats,dataset_format",
    FORMATS + [("PremierDraft", c.LIMITED_TYPE_DRAFT_PREMIER_V1, 1, 8, "PremierDraft")],
    ids=[f[0] for f in FORMATS] + ["legacy-Premier"],
)
def test_format_log_pipeline_preserves_picks_pools_and_returned_packs(
    scanner, event, kind, cards_per_pick, seats, dataset_format,
):
    """Exercise each registered format's real dispatch, not just its label."""
    join_event(scanner, f"{event}_OTJ_20240416")
    scanner.draft_type = kind  # Also exercise the old Premier log protocol.

    def append(prefix, payload):
        with open(scanner.arena_file, "a") as log:
            log.write(prefix + json.dumps(payload, separators=(",", ":")) + "\n")

    if kind in (c.LIMITED_TYPE_SEALED, c.LIMITED_TYPE_SEALED_TRADITIONAL):
        append("[UnityCrossThreadLogger] ", {
            "InternalEventName": scanner.event_string, "CardPool": [101, 101, 102],
        })
        assert scanner.draft_data_search()
        assert scanner.taken_cards == ["101", "101", "102"]
        assert scanner.retrieve_current_pack_and_pick() == (0, 0)
        return

    ids = list(range(101, 115))
    picked = ids[:cards_per_pick]
    is_bot = kind in (c.LIMITED_TYPE_DRAFT_QUICK, c.LIMITED_TYPE_DRAFT_PICK_TWO_QUICK)

    def append_pack(pick, cards):
        if is_bot:
            append("[UnityCrossThreadLogger] ", {
                "DraftStatus": "PickNext", "DraftPack": cards,
                "PackNumber": 0, "PickNumber": pick - 1,
            })
        else:
            append(c.DRAFT_PACK_STRING_PREMIER, {
                "draftId": "draft-regression", "SelfPack": 1, "SelfPick": pick,
                "PackCards": ",".join(map(str, cards)),
            })

    append_pack(1, ids)
    assert scanner.draft_data_search()
    assert scanner.retrieve_current_pack_and_pick() == (1, 1)
    if is_bot:
        pick_prefix = c.DRAFT_PICK_STRING_QUICK
        payload = {"PackNumber": 0, "PickNumber": 0, "CardIds": picked}
    else:
        pick_prefix = (c.DRAFT_PICK_STRING_PREMIER_OLD
                       if kind == c.LIMITED_TYPE_DRAFT_PREMIER_V1
                       else c.DRAFT_PICK_STRING_PREMIER)
        payload = {"DraftId": "draft-regression", "Pack": 1, "Pick": 1}
        payload["GrpIds" if cards_per_pick == 2 else "GrpId"] = (
            picked if cards_per_pick == 2 else picked[0]
        )
    append(pick_prefix, {"request": json.dumps(payload)})
    assert scanner.draft_data_search()
    assert scanner.taken_cards == list(map(str, picked))
    append(pick_prefix, {"request": json.dumps(payload)})
    scanner.draft_data_search()
    assert scanner.taken_cards == list(map(str, picked))  # duplicate log is harmless

    returned = ids[seats * cards_per_pick:]
    append_pack(seats + 1, returned)
    assert scanner.draft_data_search()
    assert scanner.number_of_players == seats
    assert scanner.initial_pack[0] == list(map(str, ids))
    assert scanner.pack_cards[0] == list(map(str, returned))


def write_dataset(path, fmt, rate, *, include_card=True, set_code="OTJ", **meta):
    cards = {str(i): {"name": f"Filler {i}"} for i in range(10)}
    if include_card:
        cards["123"] = {
            "name": "Shared Card", "colors": ["G"], "types": ["Creature"],
            "mana_cost": "{1}{G}", "cmc": 2,
            "deck_colors": {"All Decks": {"gihwr": rate, "alsa": 4.0}},
        }
    path.write_text(json.dumps({
        "meta": {"version": 1, "set": set_code, "event": fmt, **meta},
        "card_ratings": cards,
    }))
    return str(path)


@FORMAT_PARAMS
@pytest.mark.parametrize("include_card", [True, False], ids=["rated", "metadata-only"])
def test_cached_alias_never_reuses_another_formats_statistics(
    tmp_path, monkeypatch, event, kind, cards_per_pick, seats, dataset_format,
    include_card,
):
    monkeypatch.setattr(c, "SETS_FOLDER", str(tmp_path))
    # This was the old on-disk cache shape: a full card with event-specific WR.
    legacy = {
        "name": "Shared Card", "colors": ["G"], "types": ["Creature"],
        "mana_cost": "{1}{G}", "cmc": 2, "tags": ["removal"],
        "deck_colors": {"All Decks": {"gihwr": 99.0, "alsa": 1.0}},
    }
    (tmp_path / "custom_cards.json").write_text(json.dumps({"999": legacy}))
    data = Dataset(retrieve_unknown=True)
    # No dataset, including just after clear(), must expose cached WR either.
    for read in (data.get_data_by_id, data.resolve_data_by_id):
        assert not read([999])[0].get("deck_colors")
    path = write_dataset(tmp_path / "current.json", dataset_format, 53.0,
                         include_card=include_card)
    assert data.open_file(path) == Result.VALID
    for read in (data.get_data_by_id, data.resolve_data_by_id):
        result = read([999, 999])
        assert [card["name"] for card in result] == ["Shared Card"] * 2
        if include_card:
            assert result[0]["deck_colors"]["All Decks"]["gihwr"] == 53.0
        else:
            assert not result[0].get("deck_colors")
            assert result[0]["mana_cost"] == "{1}{G}"
            assert result[0]["tags"] == ["removal"]
    assert data.start_resolution(Mock()) is None  # cached metadata needs no IO
    data._save_custom_cache()
    saved = json.loads((tmp_path / "custom_cards.json").read_text())
    assert "deck_colors" not in saved["999"]
    data.clear()
    assert not data.get_data_by_id([999])[0].get("deck_colors")


@pytest.mark.parametrize("change", ["set", "user_group", "time_period", "same-format-refresh"])
def test_cached_alias_rebinds_on_dataset_change(tmp_path, monkeypatch, change):
    monkeypatch.setattr(c, "SETS_FOLDER", str(tmp_path))
    data = Dataset(retrieve_unknown=True)
    assert data.open_file(write_dataset(tmp_path / "first.json", "PremierDraft", 61.0)) == Result.VALID
    # Resolve an alternate Arena ID through the local DB, then persist it.
    monkeypatch.setattr(data, "_resolve_unknown_id", lambda aid: "Shared Card")
    data.get_data_by_id([999])
    worker = data.start_resolution(Mock())
    worker.join(3)
    assert not worker.is_alive()
    assert data.get_data_by_id([999])[0]["deck_colors"]["All Decks"]["gihwr"] == 61.0
    old_snapshot = data.get_card_ratings()
    metadata = {"set_code": "MKM"} if change == "set" else {change: "new"}
    assert data.open_file(write_dataset(tmp_path / "second.json", "PremierDraft", 48.0,
                                        **metadata)) == Result.VALID
    assert data.get_data_by_id([999])[0]["deck_colors"]["All Decks"]["gihwr"] == 48.0
    assert old_snapshot["999"]["deck_colors"]["All Decks"]["gihwr"] == 61.0
    # A new process must resolve the persisted alias against its own dataset.
    reopened = Dataset()
    assert not reopened.get_data_by_id([999])[0].get("deck_colors")
    assert reopened.open_file(str(tmp_path / "second.json")) == Result.VALID
    assert reopened.get_data_by_id([999])[0]["deck_colors"]["All Decks"]["gihwr"] == 48.0


def card(name, color, wr=55.0):
    return {"name": name, "colors": [color], "types": ["Creature"], "cmc": 3,
            "mana_cost": "{2}{" + color + "}",
            "deck_colors": {"All Decks": {"gihwr": wr, "alsa": 12.0}}}


@FORMAT_PARAMS
@pytest.mark.parametrize("pick", [1, 3, 5, 7])
def test_draft_advice_uses_format_progress_and_supported_wheels(
    event, kind, cards_per_pick, seats, dataset_format, pick,
):
    metrics = Mock()
    metrics.get_metrics.return_value = (55.0, 4.0)
    pool = [card("White", "W", 62.0)] * 5 + [card("Blue", "U", 61.0)] * 5
    pack = [card(f"Green {i}", "G", 55.0 + i / 10) for i in range(12)]
    advisor = DraftAdvisor(metrics, pool)
    assert advisor.main_archetype == "WU"
    if kind in (c.LIMITED_TYPE_SEALED, c.LIMITED_TYPE_SEALED_TRADITIONAL):
        assert advisor.evaluate_pack([], 0, current_pack=0) == []
        return
    # Pick-Two pick 5 must have the same scoring progress as ordinary pick 9.
    effective_pick = (pick - 1) * cards_per_pick + 1
    actual = advisor.evaluate_pack(pack, pick, cards_per_pick=cards_per_pick,
                                   number_of_players=seats)
    reference = advisor.evaluate_pack(pack, effective_pick)
    assert [r.contextual_score for r in actual] == [r.contextual_score for r in reference]
    assert any(r.wheel_chance > 0 for r in actual) is (cards_per_pick == 1)


@pytest.mark.parametrize("seats", [2, 4, 6, 10])
def test_custom_pods_do_not_show_standard_wheel_percentages(seats):
    metrics = Mock()
    metrics.get_metrics.return_value = (55.0, 4.0)
    pack = [card(f"Card {i}", "G") for i in range(12)]
    recs = DraftAdvisor(metrics, []).evaluate_pack(pack, 2, number_of_players=seats)
    assert len(recs) == len(pack)
    assert all(r.wheel_chance == 0 for r in recs)

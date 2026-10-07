from datetime import date
from unittest.mock import MagicMock

import pytest

from server.events import build_event_calendar, fetch_event_calendar, get_scheduled_events


TODAY = date(2026, 10, 6)
FILTERS = {
    "expansions": ["FRA", "WOE", "Y26FRA", "Cube - Powered"],
    "formats": ["PremierDraft", "TradDraft", "QuickDraft", "PickTwoDraft",
                "Sealed", "TradSealed", "ContenderDraft", "ArenaDirect_Sealed"],
}
SETS = {"data": [
    {"name": "Reality Fracture", "code": "fra"},
    {"name": "Wilds of Eldraine", "code": "woe"},
    {"name": "Alchemy: Reality Fracture", "code": "yfra",
     "set_type": "alchemy", "parent_set_code": "fra"},
]}


def event(title="Premier Draft", set_name="Reality Fracture", **fields):
    return {
        "title": title, "category": "limited", "set": set_name,
        "start": "2026-09-29", "end": "2026-11-09",
        "url": "https://magic.wizards.com/en/news/mtg-arena/reality-fracture-event-schedule",
        **fields,
    }


def calendar(events, **feed_fields):
    return build_event_calendar(
        {"as_of": "2026-10-05", "events": events, **feed_fields},
        FILTERS, SETS, today=TODAY,
    )


def test_mtgpile_schedule_maps_sets_formats_and_active_windows():
    normalized = calendar([
        event(), event("Traditional Draft"), event("Pick-Two Draft"),
        event("Sealed Best-of-One", end="2026-10-27"),
        event("Traditional Sealed", end="2026-10-13"),
        event("Quick Draft", "Wilds of Eldraine", end="2026-10-07"),
        event("Contender Draft", start="2026-10-13"),
        event("Flashback Premier Draft", "Wilds of Eldraine", end="2026-10-05"),
    ])
    active = get_scheduled_events(normalized, today=TODAY)
    assert active == {
        "FRA": {"formats": ["PickTwoDraft", "PremierDraft", "Sealed", "TradDraft", "TradSealed"],
                "start_date": "2026-09-29"},
        "WOE": {"formats": ["QuickDraft"], "start_date": "2026-09-29"},
    }
    assert normalized["source_url"] == "https://mtgpile.com/api/v1/events/arena/all.json"
    assert "mtgpile.com" in normalized["attribution"]
    assert len(normalized["events"]) == 8


def test_mtgpile_alchemy_cube_and_special_formats():
    normalized = calendar([
        event(set_name="Alchemy: Reality Fracture"),
        event("Arena Powered Cube", None),
        event("Arena Direct"),
    ])
    active = get_scheduled_events(normalized, today=TODAY)
    assert active["Y26FRA"]["formats"] == ["PremierDraft"]
    assert active["Cube - Powered"]["formats"] == ["PremierDraft", "TradDraft"]
    assert active["FRA"]["formats"] == ["ArenaDirect_Sealed"]


def test_mtgpile_resolves_announced_short_set_names():
    filters = {**FILTERS, "expansions": ["DSK", "STX"]}
    sets = {"data": [
        {"name": "Duskmourn: House of Horror", "code": "dsk"},
        {"name": "Strixhaven: School of Mages", "code": "stx"},
    ]}
    normalized = build_event_calendar(
        {"as_of": "2026-10-05", "events": [
            event("Quick Draft", "Duskmourn"),
            event("Flashback Premier Draft", "Strixhaven"),
        ]}, filters, sets, today=TODAY,
    )
    assert get_scheduled_events(normalized, today=TODAY) == {
        "DSK": {"formats": ["QuickDraft"], "start_date": "2026-09-29"},
        "STX": {"formats": ["PremierDraft"], "start_date": "2026-09-29"},
    }


def test_mtgpile_skips_unknown_unsourced_and_invalid_events(caplog):
    normalized = calendar([
        event(),
        event(set_name="Unknown Set"),
        event("Midweek Magic (Momir)"),
        event("Limited Open"),
        event(end=None), event(start="2026-02-30"),
        event(end="2026-09-28"), event(url=None),
        event(category="constructed"),
        event(set_name=None, during_set_event_schedule="Reality Fracture"),
    ])
    assert len(normalized["events"]) == 1
    assert "Unknown Set" in caplog.text


@pytest.mark.parametrize("stamp", [None, "invalid", "2026-09-01", "2026-10-08"])
def test_mtgpile_rejects_missing_stale_or_future_freshness(stamp):
    with pytest.raises(ValueError):
        calendar([event()], as_of=stamp)


@pytest.mark.parametrize("feed", [{}, {"as_of": "2026-10-05", "events": []},
                                   {"as_of": "2026-10-05", "events": "broken"}])
def test_mtgpile_rejects_invalid_feed(feed):
    with pytest.raises(ValueError):
        build_event_calendar(feed, FILTERS, SETS, today=TODAY)


def test_mtgpile_fetch_uses_shared_client_and_never_falls_back_to_local_calendar():
    client = MagicMock()
    client.respectful_get.return_value.json.side_effect = [
        {"as_of": "2026-10-05", "events": [event()]}, FILTERS, SETS,
    ]
    normalized = fetch_event_calendar(client, today=TODAY)
    assert normalized["events"][0]["set_code"] == "FRA"
    assert [call.args[0] for call in client.respectful_get.call_args_list] == [
        "https://mtgpile.com/api/v1/events/arena/all.json",
        "https://api.17lands.com/data/filters", "https://api.scryfall.com/sets",
    ]
    client.respectful_get.side_effect = RuntimeError("MTGpile unavailable")
    with pytest.raises(RuntimeError, match="MTGpile unavailable"):
        fetch_event_calendar(client, today=TODAY)


def test_scheduled_events_merge_duplicates_and_use_inclusive_dates():
    active = get_scheduled_events({"events": [
        {"set_code": "FRA", "formats": ["PremierDraft"],
         "start_date": "2026-10-06", "end_date": "2026-10-06"},
        {"set_code": "FRA", "formats": ["PremierDraft", "TradDraft"],
         "start_date": "2026-09-29", "end_date": "2026-10-06"},
    ]}, today=TODAY)
    assert active == {"FRA": {"formats": ["PremierDraft", "TradDraft"], "start_date": "2026-09-29"}}

"""Resolve MTGpile's announced Arena schedule into supported 17Lands jobs."""

import logging
import re
from datetime import date, datetime, timezone

logger = logging.getLogger(__name__)

SOURCE_URL = "https://mtgpile.com/api/v1/events/arena/all.json"
MAX_FEED_AGE_DAYS = 7

# Use 17Lands event types, not MTGA display names. Ambiguous multi-stage
# events (Limited Open, championship weekends, etc.) are deliberately omitted.
FORMAT_TITLES = {
    "Premier Draft": ["PremierDraft"],
    "Flashback Premier Draft": ["PremierDraft"],
    "Traditional Draft": ["TradDraft"],
    "Quick Draft": ["QuickDraft"],
    "Pick-Two Draft": ["PickTwoDraft"],
    "Contender Draft": ["ContenderDraft"],
    "Sealed": ["Sealed"],
    "Sealed Best-of-One": ["Sealed"],
    "Traditional Sealed": ["TradSealed"],
    "Traditional Sealed (Best-of-Three)": ["TradSealed"],
    "Arena Direct": ["ArenaDirect_Sealed"],
    "Arena Championship Qualifier Play-In (Sealed BO1)": ["QualifierPlayInSealed"],
    "Arena Championship Qualifier Play-In (Sealed BO3)": ["QualifierPlayInTradSealed"],
    "Arena Powered Cube": ["PremierDraft", "TradDraft"],
    "Planar Cube Draft": ["PremierDraft"],
}
CUBE_TITLES = {
    "Arena Powered Cube": "Cube - Powered",
    "Planar Cube Draft": "Cube - Planar",
}
SET_NAME_ALIASES = {
    "duskmourn": "duskmourn: house of horror",
    "strixhaven": "strixhaven: school of mages",
}


def _parse_date(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def build_event_calendar(feed, filters, scryfall_sets, today=None):
    """Normalize sourced, dated Limited events without guessing missing fields.

    The supported set/format catalogs come from 17Lands; Scryfall translates
    display names to codes. Alchemy codes are resolved against 17Lands rather
    than inferred from a release year. Unknown events are logged and skipped.
    Missing/stale feed metadata and unreadable catalogs fail the ETL run.
    """
    today = today or datetime.now(timezone.utc).date()
    as_of = _parse_date(feed.get("as_of"))
    if as_of is None or not 0 <= (today - as_of).days <= MAX_FEED_AGE_DAYS:
        raise ValueError("MTGpile schedule has missing, stale, or future as_of metadata")
    raw_events = feed.get("events")
    if not isinstance(raw_events, list) or not raw_events:
        raise ValueError("MTGpile schedule must contain an events array")
    expansions = filters.get("expansions")
    formats = filters.get("formats")
    sets = scryfall_sets.get("data")
    if not expansions or not formats or not isinstance(sets, list) or not sets:
        raise ValueError("Cannot resolve schedule without 17Lands and Scryfall catalogs")

    set_codes = {}
    for card_set in sets:
        code = card_set["code"].upper()
        if code not in expansions and card_set.get("set_type") == "alchemy":
            parent = card_set.get("parent_set_code", "").upper()
            candidates = [c for c in expansions if parent and re.fullmatch(r"Y\d{2}" + re.escape(parent), c)]
            code = candidates[0] if len(candidates) == 1 else ""
        if code in expansions:
            set_codes[card_set["name"].strip().casefold()] = code

    events = []
    for entry in raw_events:
        if not isinstance(entry, dict) or entry.get("category") != "limited":
            continue
        title = entry.get("title")
        supported_formats = [fmt for fmt in FORMAT_TITLES.get(title, []) if fmt in formats]
        if not supported_formats:
            logger.warning("Skipping unsupported MTGpile event: %s", title)
            continue
        start, end = _parse_date(entry.get("start")), _parse_date(entry.get("end"))
        if start is None or end is None or end < start or not entry.get("url"):
            logger.warning("Skipping MTGpile event without a sourced date window: %s", title)
            continue
        set_name = entry.get("set") or ""
        normalized_name = set_name.strip().casefold()
        normalized_name = SET_NAME_ALIASES.get(normalized_name, normalized_name)
        code = CUBE_TITLES.get(title) or set_codes.get(normalized_name)
        if code not in expansions:
            logger.warning("Skipping MTGpile event with unresolved set: %s (%s)", set_name, title)
            continue
        events.append({
            "set_code": code, "formats": supported_formats,
            "start_date": start.isoformat(), "end_date": end.isoformat(),
            "source_url": entry["url"],
        })
    if not events:
        raise ValueError("MTGpile schedule contains no resolvable Limited events")
    events.sort(key=lambda e: (e["start_date"], e["set_code"], e["formats"], e["end_date"]))
    return {
        "as_of": as_of.isoformat(), "source_url": SOURCE_URL,
        "attribution": "Event schedule from mtgpile.com, compiled from Wizards of the Coast's published MTG Arena event-schedule articles.",
        "events": events,
    }


def fetch_event_calendar(client, today=None):
    """Use the shared HTTP client's retries, headers, throttling and 12h cache."""
    feed = client.respectful_get(SOURCE_URL).json()
    filters = client.respectful_get("https://api.17lands.com/data/filters").json()
    sets = client.respectful_get("https://api.scryfall.com/sets").json()
    return build_event_calendar(feed, filters, sets, today=today)


def get_scheduled_events(calendar, today=None):
    today = today or datetime.now(timezone.utc).date()
    active_sets = {}
    for event in calendar["events"]:
        if event["start_date"] <= today.isoformat() <= event["end_date"]:
            code = event["set_code"]
            data = active_sets.setdefault(code, {"formats": set(), "start_date": event["start_date"]})
            data["formats"].update(event["formats"])
            data["start_date"] = min(data["start_date"], event["start_date"])
    for data in active_sets.values():
        data["formats"] = sorted(data["formats"])
    return active_sets

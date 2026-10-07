"""One event-aware dataset selection policy for startup and live scanning."""

import os
import re
from src import constants


def select_event_dataset(
    scanner, target_set=None, target_format=None, target_user=None,
    preferred_filename="",
):
    event_set, event_format = scanner.retrieve_current_limited_event()
    set_code = target_set or event_set
    if not set_code:
        return None
    format_name = target_format or event_format
    if format_name in constants.LIMITED_TYPES_DICT:
        formats = {
            fmt for fmt, kind in constants.LIMITED_TYPES_DICT.items()
            if kind == constants.LIMITED_TYPES_DICT[format_name]
        }
    elif target_format:
        formats = {target_format}
    else:
        # Special event display labels (e.g. OpenDay1) are not format identifiers.
        formats = {
            fmt for fmt, kind in constants.LIMITED_TYPES_DICT.items()
            if kind == scanner.draft_type
        }

    def normalize(code):
        return re.sub(r"[\s._/-]", "", code).upper()

    candidates = []
    for label, path in scanner.retrieve_data_sources().items():
        match = re.fullmatch(r"\[([^\]]+)\] ([^()]+) \((.+)\)", label)
        if not match:
            continue
        code, fmt, group = match.groups()
        group = group.split(" (", 1)[0]
        if normalize(code) != normalize(set_code) or fmt not in formats:
            continue
        if target_user and group != target_user:
            continue
        candidates.append(
            (os.path.basename(path) != preferred_filename, group != "All", path)
        )
    # Sources already order newer datasets first; preserve that order on ties.
    candidates.sort(key=lambda candidate: candidate[:2])
    return candidates[0][2] if candidates else None

import pytest
from src.utils import process_json, json_find, detect_string


def test_process_json_valid_nested():
    """Verify standard valid JSON parsing."""
    raw = '{"key1": "value1", "key2": {"inner": 42}}'
    result = process_json(raw)
    assert result["key1"] == "value1"
    assert result["key2"]["inner"] == 42


def test_process_json_mtga_malformed():
    """Verify MTGA's specific unescaped string JSON bug is intercepted and fixed."""
    # MTGA sometimes outputs a JSON string INSIDE a value without escaping quotes
    malformed = '{"id":"1","request":"{"EventName":"PremierDraft_OTJ_20240416"}"}'
    result = process_json(malformed)

    assert isinstance(result, dict)
    assert "request" in result
    assert isinstance(result["request"], dict)
    assert result["request"]["EventName"] == "PremierDraft_OTJ_20240416"

    malformed_payload = '{"CurrentModule":"Draft","Payload":"{"DraftId":"123"}"}'
    result_payload = process_json(malformed_payload)
    assert str(result_payload["Payload"]["DraftId"]) == "123"


def test_process_json_completely_broken():
    """Verify completely unparseable garbage doesn't crash the app."""
    garbage = '{"key": "value", broken_json'
    result = process_json(garbage)
    assert result == garbage  # Should safely return the original string


def test_json_find_recursive():
    """Verify recursive key searching across nested dicts."""
    obj = {
        "level1": "ignore",
        "level2": {"level3": {"TargetKey": "FoundMe!"}, "OtherKey": "IgnoreMe"},
    }
    assert json_find("TargetKey", obj) == "FoundMe!"
    assert json_find("MissingKey", obj) is None


def test_detect_string_robustness():
    """Verify string detection handles casing, underscores, and spacing anomalies."""
    targets = ["Event_Join", "Draft.Notify"]

    # Standard match
    assert detect_string('==> Event_Join {"data": 1}', targets) != -1

    # No JSON brace -> should fail fast
    assert detect_string("==> Event_Join NO BRACE HERE", targets) == -1

    # Mismatched casing and spacing (WOTC changes this frequently)
    assert detect_string('==> E V E N T J O I N {"data": 1}', targets) != -1

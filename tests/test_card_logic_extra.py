import pytest
from src.card_logic import (
    get_functional_cmc,
    format_types_for_ui,
    get_card_colors,
    row_color_tag,
)


def test_get_functional_cmc():
    assert get_functional_cmc({"cmc": 5, "text": "landcycling"}) == 2
    assert get_functional_cmc({"cmc": 4, "text": "morph {3}"}) == 3
    assert get_functional_cmc({"cmc": 6, "text": "channel —"}) == 2
    assert get_functional_cmc({"cmc": 6, "text": "costs {2} less"}) == 4
    assert get_functional_cmc({"cmc": 5, "text": "evoke {2}"}) == 3
    assert get_functional_cmc({"cmc": 2, "text": ""}) == 2
    assert get_functional_cmc({"cmc": 0, "text": "prototype {1}"}) == 0


def test_format_types_for_ui():
    assert (
        format_types_for_ui(["Enchantment", "Creature", "Legendary"])
        == "Creature Enchantment"
    )
    assert format_types_for_ui(["Artifact", "Land"]) == "Land Artifact"
    assert format_types_for_ui([]) == ""


def test_get_card_colors():
    colors = get_card_colors("{1}{W}{U}{U}")
    assert colors["W"] == 1
    assert colors["U"] == 2
    assert "R" not in colors

    assert get_card_colors("") == {}


def test_row_color_tag():
    assert row_color_tag("{1}{W}") == "white_card"
    assert row_color_tag("{1}{W}{U}") == "gold_card"
    assert row_color_tag("{2}") == "colorless_card"
    assert row_color_tag("{1}{B}") == "black_card"

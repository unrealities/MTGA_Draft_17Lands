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
    # List comprehension preserves original array order
    assert format_types_for_ui(["Artifact", "Land"]) == "Artifact Land"
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


def test_get_deck_metrics_empty():
    from src.card_logic import get_deck_metrics

    metrics = get_deck_metrics([])
    assert metrics.total_cards == 0
    assert metrics.cmc_average == 0.0
    assert sum(metrics.distribution_all) == 0


def test_get_deck_metrics_only_lands():
    from src.card_logic import get_deck_metrics

    # Simulate a user putting 40 lands into the deck builder
    deck = [{"name": "Plains", "types": ["Land", "Basic"]} for _ in range(40)]

    metrics = get_deck_metrics(deck)
    assert metrics.total_cards == 40
    assert metrics.total_non_land_cards == 0
    assert metrics.cmc_average == 0.0  # Should safely handle division by zero


def test_get_deck_metrics_creatures_and_spells():
    from src.card_logic import get_deck_metrics

    deck = [
        {"name": "Bear", "types": ["Creature"], "cmc": 2},
        {"name": "Bear", "types": ["Creature"], "cmc": 2},
        {"name": "Bolt", "types": ["Instant"], "cmc": 1},
        {
            "name": "Big Spell",
            "types": ["Sorcery"],
            "cmc": 10,
        },  # CMC > 7 gets clamped to 7 bucket
    ]

    metrics = get_deck_metrics(deck)
    assert metrics.total_non_land_cards == 4
    assert metrics.creature_count == 2
    assert metrics.noncreature_count == 2

    # Expected average: (2+2+1+10) / 4 = 15 / 4 = 3.75
    assert metrics.cmc_average == 3.75

    # Check distribution buckets
    assert metrics.distribution_creatures[2] == 2
    assert metrics.distribution_noncreatures[1] == 1
    assert metrics.distribution_noncreatures[7] == 1  # 10 cmc clamped to bucket 7

import pytest
from unittest.mock import MagicMock
from src.advisor.engine import DraftAdvisor
from src.advisor.schema import Recommendation


@pytest.fixture
def mock_metrics():
    metrics = MagicMock()
    # Mocking format_texture for VOR (Value Over Replacement) tests
    metrics.format_texture = {
        "R": {"2-drop": 1, "removal": 10},  # Extremely scarce red 2-drops
        "G": {"2-drop": 10, "removal": 1},  # Extremely scarce green removal
    }
    # get_metrics returns (mean, std)
    metrics.get_metrics.return_value = (55.0, 4.0)
    return metrics


def test_identify_main_colors(mock_metrics):
    pool = [
        {"colors": ["W"], "deck_colors": {"All Decks": {"gihwr": 60.0}}},
        {"colors": ["W"], "deck_colors": {"All Decks": {"gihwr": 60.0}}},
        {"colors": ["U"], "deck_colors": {"All Decks": {"gihwr": 55.0}}},
        {"colors": ["R"], "deck_colors": {"All Decks": {"gihwr": 40.0}}},
    ]
    advisor = DraftAdvisor(mock_metrics, pool)

    # Because White has high WR and multiple cards, it should be top
    assert "W" in advisor.main_colors


def test_analyze_pool(mock_metrics):
    # Establish a definitive "White Lane" by padding the pool > 15 cards
    pool = [
        {
            "colors": ["W"],
            "types": ["Creature"],
            "cmc": 2,
            "deck_colors": {"All Decks": {"gihwr": 60.0}},
        }
        for _ in range(15)
    ]

    # Add a black removal spell (not a bomb, just utility)
    pool.append(
        {
            "colors": ["B"],
            "tags": ["removal"],
            "cmc": 4,
            "deck_colors": {"All Decks": {"gihwr": 55.0}},
        }
    )

    # Add a green fixing bomb. Because we are definitively in White, this will trigger the splash logic.
    pool.append(
        {
            "colors": ["G"],
            "tags": ["fixing_ramp"],
            "cmc": 1,
            "deck_colors": {"All Decks": {"gihwr": 65.0}},
        }
    )

    advisor = DraftAdvisor(mock_metrics, pool)

    assert advisor.pool_metrics["early_plays"] == 15
    assert advisor.pool_metrics["hard_removal_count"] == 1
    assert advisor.pool_metrics["fixing_count"] == 1

    # 65.0 > 55.0 + (1.5 * 4.0) = 61.0, so 'G' triggers as a premium splash target
    assert "G" in advisor.pool_metrics["splash_targets"]


def test_calculate_castability_v5(mock_metrics):
    advisor = DraftAdvisor(mock_metrics, [])
    advisor.main_colors = ["W", "U"]
    advisor.pool_metrics = {"fixing_count": 0}

    # On lane card
    mult, _ = advisor._calculate_castability_v5(
        {"colors": ["W"]}, pack=2, pick=1, z_score=0.0
    )
    assert mult == 1.0

    # Off lane card, double pip (uncastable)
    mult, _ = advisor._calculate_castability_v5(
        {"colors": ["B"], "mana_cost": "{B}{B}"}, pack=2, pick=1, z_score=0.0
    )
    assert mult == 0.01

    # Splashable bomb
    mult, _ = advisor._calculate_castability_v5(
        {"colors": ["R"], "mana_cost": "{R}"}, pack=2, pick=1, z_score=2.0
    )

    # Without fixing in the pool, it's heavily penalized even if it's a bomb
    assert mult == 0.05


def test_check_relative_wheel(mock_metrics):
    advisor = DraftAdvisor(mock_metrics, [])
    # Should wheel if ALSA is greater than the current pick
    mult, reason, pct = advisor._check_relative_wheel(
        {"deck_colors": {"All Decks": {"alsa": 10.0}}}, pick=2, rank_in_pack=5
    )

    assert pct > 0.0
    assert mult == 0.8
    assert "Wheels" in reason


def test_evaluate_pack_elite_detection(mock_metrics):
    # Establish a baseline pool
    pool = [
        {
            "name": "Grizzly Bears",
            "colors": ["G"],
            "types": ["Creature"],
            "cmc": 2,
            "deck_colors": {"All Decks": {"gihwr": 55.0}},
        }
    ] * 10
    advisor = DraftAdvisor(mock_metrics, pool)

    # Construct a pack with a massive outlier (Bomb) and filler
    pack = [
        {
            "name": "Bomb",
            "colors": ["G"],
            "types": ["Creature"],
            "cmc": 4,
            "deck_colors": {"All Decks": {"gihwr": 75.0, "iwd": 5.0, "alsa": 2.0}},
        },
        {
            "name": "Filler1",
            "colors": ["G"],
            "types": ["Creature"],
            "cmc": 2,
            "deck_colors": {"All Decks": {"gihwr": 50.0, "iwd": 1.0, "alsa": 4.0}},
        },
        {
            "name": "Filler2",
            "colors": ["G"],
            "types": ["Creature"],
            "cmc": 2,
            "deck_colors": {"All Decks": {"gihwr": 50.0, "iwd": 1.0, "alsa": 4.0}},
        },
        {
            "name": "Filler3",
            "colors": ["G"],
            "types": ["Creature"],
            "cmc": 2,
            "deck_colors": {"All Decks": {"gihwr": 50.0, "iwd": 1.0, "alsa": 4.0}},
        },
    ]

    recs = advisor.evaluate_pack(pack, current_pick=1)

    assert len(recs) == 4
    assert recs[0].card_name == "Bomb"
    # Elite designation triggers because Z-score > 1.5, IWD > 4.5, and it is on-color
    assert recs[0].is_elite is True


def test_evaluate_value_over_replacement(mock_metrics):
    advisor = DraftAdvisor(mock_metrics, [])
    advisor.main_colors = ["R"]
    advisor.global_mean = 55.0
    advisor.global_std = 4.0

    # A playable red 2-drop. Because we defined Red 2-drops as incredibly scarce
    # in the mock_metrics fixture above, this card should trigger a VOR bonus!
    pack = [
        {
            "name": "Scarce Red 2-Drop",
            "colors": ["R"],
            "types": ["Creature"],
            "cmc": 2,
            "tags": ["evasion"],
            "deck_colors": {"All Decks": {"gihwr": 54.0}},
        }
    ]

    recs = advisor.evaluate_pack(pack, current_pick=1)

    assert len(recs) == 1
    assert any("High VOR: Scarce R 2-Drops" in reason for reason in recs[0].reasoning)

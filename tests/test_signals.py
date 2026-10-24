import pytest
from unittest.mock import MagicMock
from src.signals import SignalCalculator
from src import constants


@pytest.fixture
def mock_metrics():
    metrics = MagicMock()
    # get_metrics returns (mean, std)
    metrics.get_metrics.return_value = (55.0, 0.0)
    return metrics


def test_signal_calculation_logic(mock_metrics):
    calculator = SignalCalculator(mock_metrics)

    # Current Pick: 5
    current_pick = 5

    # 1. Good Card, Late (Signal!)
    # White Card: 60% WR (5% > Avg), ATA 2.0 (3 picks late)
    # Score = 3.0 * 5.0 = 15.0
    card_signal = {
        constants.DATA_FIELD_COLORS: ["W"],
        constants.DATA_FIELD_DECK_COLORS: {
            constants.FILTER_OPTION_ALL_DECKS: {
                constants.DATA_FIELD_GIHWR: 60.0,
                constants.DATA_FIELD_ATA: 2.0,
            }
        },
    }

    # 2. Bad Card, Late (Noise - Should be ignored)
    # Blue Card: 50% WR (5% < Avg), ATA 2.0
    card_bad = {
        constants.DATA_FIELD_COLORS: ["U"],
        constants.DATA_FIELD_DECK_COLORS: {
            constants.FILTER_OPTION_ALL_DECKS: {
                constants.DATA_FIELD_GIHWR: 50.0,
                constants.DATA_FIELD_ATA: 2.0,
            }
        },
    }

    # 3. Good Card, Early (Normal - Should be ignored)
    # Red Card: 60% WR, ATA 7.0 (Seen at pick 5, so it's early/on time)
    card_early = {
        constants.DATA_FIELD_COLORS: ["R"],
        constants.DATA_FIELD_DECK_COLORS: {
            constants.FILTER_OPTION_ALL_DECKS: {
                constants.DATA_FIELD_GIHWR: 60.0,
                constants.DATA_FIELD_ATA: 7.0,
            }
        },
    }

    # 4. Multi-Color Good Card, Late
    # Green/Black: 57% WR (2% > Avg), ATA 4.0 (1 pick late)
    # Score = 1.0 * 2.0 = 2.0 (Added to G and B)
    card_gold = {
        constants.DATA_FIELD_COLORS: ["G", "B"],
        constants.DATA_FIELD_DECK_COLORS: {
            constants.FILTER_OPTION_ALL_DECKS: {
                constants.DATA_FIELD_GIHWR: 57.0,
                constants.DATA_FIELD_ATA: 4.0,
            }
        },
    }

    pack = [card_signal, card_bad, card_early, card_gold]

    scores = calculator.calculate_pack_signals(pack, current_pick)

    # Assertions
    assert scores["W"] == 15.0
    assert scores["U"] == 0.0  # Bad card ignored
    assert scores["R"] == 0.0  # Early card ignored
    assert scores["G"] == 2.0  # Gold card contribution
    assert scores["B"] == 2.0  # Gold card contribution

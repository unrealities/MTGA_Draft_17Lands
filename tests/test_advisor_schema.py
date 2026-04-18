import pytest
from src.advisor.schema import Recommendation


def test_recommendation_schema():
    rec = Recommendation(
        card_name="Test Card",
        base_win_rate=55.0,
        contextual_score=80.0,
        z_score=1.5,
        cast_probability=1.0,
        wheel_chance=0.0,
        functional_cmc=2.0,
        reasoning=["Good card"],
    )
    assert rec.card_name == "Test Card"
    assert rec.is_elite is False
    assert rec.archetype_fit == "Neutral"
    assert rec.tags == []

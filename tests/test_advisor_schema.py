import pytest
from src.advisor.schema import Recommendation


def test_recommendation_schema():
    rec = Recommendation(
        card_name="Test Card",
        contextual_score=80.0,
        z_score=1.5,
        wheel_chance=0.0,
        reasoning=["Good card"],
    )
    assert rec.card_name == "Test Card"
    assert rec.is_elite is False
    assert rec.tags == []

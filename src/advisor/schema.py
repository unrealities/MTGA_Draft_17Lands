"""
src/advisor/schema.py
Data models for the Draft Advisor's recommendations.
"""

from typing import List, Optional
from pydantic import BaseModel


class Recommendation(BaseModel):
    card_name: str
    base_win_rate: float
    contextual_score: float
    z_score: float
    cast_probability: float  # 0.0 to 1.0 (Karsten math)
    wheel_chance: float  # 0.0 to 100.0 (Polynomial probability)
    functional_cmc: float  # e.g., Landcycler might be 0.5
    reasoning: List[str]  # e.g. ["Uncastable (Double Pip)", "Wheels 80%"]
    is_elite: bool = False
    archetype_fit: str = "Neutral"
    tags: List[str] = []

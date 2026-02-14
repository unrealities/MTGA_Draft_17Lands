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
    z_score: float  # Power level relative to the pack
    reasoning: List[str]  # e.g. ["Splashable Bomb", "Need Creatures"]
    is_elite: bool = False  # Is this a statistical outlier?
    archetype_fit: str = "Neutral"  # 'High', 'Neutral', or 'Low' based on color pair

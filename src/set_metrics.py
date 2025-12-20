import statistics as stats
from typing import Tuple
from pydantic import BaseModel
from src.dataset import Dataset
from src.constants import (
    DECK_COLORS,
    DATA_FIELD_NAME,
    DATA_FIELD_DECK_COLORS,
    WIN_RATE_OPTIONS
)

class ColorMetrics(BaseModel):
    mean: float = 0.0
    std: float = 0.0

class SetMetrics:
    """
    This class is used to calculate the mean, standard deviation for a MTG set dataset.
    """
    def __init__(self, dataset: Dataset, digits: int = 2):
        self._color_metrics: dict = {}
        self._digits: int = digits
        self.generate_metrics(dataset)

    def get_metrics(self, color: str, field: str) -> Tuple[float, float]:
        """
        Get the mean and standard deviation metrics for a specific color and field.
        """
        mean, std = (0.0, 0.0)

        if field in self._color_metrics and color in self._color_metrics[field]:
            mean = self._color_metrics[field][color].mean
            std = self._color_metrics[field][color].std

        return round(mean, self._digits), round(std, self._digits)

    def calculate_percentile(self, winrate: float, colors: str, field: str) -> float:
        """
        Calculate the percentile for a given win rate, color, and field using the cumulative distribution function (CDF) of a normal distribution.
        """
        mean, std = self.get_metrics(colors, field)

        percentile = round(stats.NormalDist(mu=mean, sigma=std).cdf(winrate) * 100, 2)

        return percentile

    def generate_metrics(self, dataset: Dataset) -> None:
        """
        Calculate the mean and standard deviation for all of the supported colors and win rate fields
        """
        if not dataset:
            return

        # Iterate over the supported colors and generate the metrics for each color
        for field in WIN_RATE_OPTIONS:
            self._color_metrics[field] = {}
            for color in DECK_COLORS:
                self._color_metrics[field][color] = self.generate_color_metrics(color, field, dataset)

    def generate_color_metrics(self, color: str, field: str, dataset: Dataset) -> ColorMetrics:
        """
        Calculate the mean and standard deviation for a specific color and field
        """
        metrics = ColorMetrics()

        processed_cards = []
        unique_gihwr = []
        dataset = dataset.get_card_ratings()
        
        if not dataset:
            return metrics
            
        # Iterate over the card list and retrieve the GIHWR for unique cards (remove duplicates and 0.0 values)
        for card_data in dataset.values():
            card_name = card_data[DATA_FIELD_NAME]
            if card_name not in processed_cards:
                processed_cards.append(card_name)

                from src.utils import normalize_color_string
                std_color = normalize_color_string(color)
                
                deck_stats = card_data.get(DATA_FIELD_DECK_COLORS, {})
                if std_color not in deck_stats:
                    continue
                
                color_stats = deck_stats[std_color]
                if field not in color_stats:
                    continue
                
                val = color_stats[field]
                if val != 0.0:
                    unique_gihwr.append(round(val, self._digits))

        if not unique_gihwr:
            return metrics

        metrics.mean = stats.mean(unique_gihwr)
        metrics.std = stats.pstdev(unique_gihwr)

        return metrics

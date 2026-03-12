import statistics as stats
from typing import Tuple
from pydantic import BaseModel
from src.dataset import Dataset
from src.constants import (
    DECK_COLORS,
    DATA_FIELD_NAME,
    DATA_FIELD_DECK_COLORS,
    WIN_RATE_OPTIONS,
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
        self.format_texture: dict = {}
        self.generate_metrics(dataset)
        self._build_format_texture(dataset)

    def _build_format_texture(self, dataset: Dataset) -> None:
        """
        Analyzes the set to determine the scarcity of specific roles (Removal, 2-Drops, etc.)
        Only counts 'Playable' Commons and Uncommons (GIHWR > baseline).
        """
        if not dataset:
            return

        baseline_wr, std = self.get_metrics("All Decks", "gihwr")
        if baseline_wr == 0.0:
            return

        # A card is "playable" if it's within 1 standard deviation of the mean
        playable_threshold = baseline_wr - std

        from src.constants import CARD_COLORS

        # Initialize texture map
        self.format_texture = {
            c: {
                "removal": 0,
                "2-drop": 0,
                "evasion": 0,
                "fixing_ramp": 0,
                "card_advantage": 0,
            }
            for c in CARD_COLORS
        }

        dataset_dict = dataset.get_card_ratings()
        if not dataset_dict:
            return

        for card in dataset_dict.values():
            rarity = str(card.get("rarity", "common")).lower()
            if rarity not in ["common", "uncommon"]:
                continue

            gihwr = float(
                card.get("deck_colors", {}).get("All Decks", {}).get("gihwr", 0.0)
            )
            if gihwr < playable_threshold:
                continue

            colors = card.get("colors", [])
            # Skip colorless or 3+ color cards for raw texture counting to keep it focused on base colors
            if not colors or len(colors) > 2:
                continue

            tags = card.get("tags", [])
            cmc = int(card.get("cmc", 0))
            types = card.get("types", [])

            is_2_drop = "Creature" in types and cmc <= 2

            for color in colors:
                if color not in self.format_texture:
                    continue
                if is_2_drop:
                    self.format_texture[color]["2-drop"] += 1
                if "removal" in tags:
                    self.format_texture[color]["removal"] += 1
                if "evasion" in tags:
                    self.format_texture[color]["evasion"] += 1
                if "fixing_ramp" in tags:
                    self.format_texture[color]["fixing_ramp"] += 1
                if "card_advantage" in tags:
                    self.format_texture[color]["card_advantage"] += 1

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
                self._color_metrics[field][color] = self.generate_color_metrics(
                    color, field, dataset
                )

    def generate_color_metrics(
        self, color: str, field: str, dataset: Dataset
    ) -> ColorMetrics:
        """
        Calculate the mean and standard deviation for a specific color and field
        """
        metrics = ColorMetrics()

        processed_cards = set()
        unique_gihwr = []

        # Use a localized variable to avoid masking the dataset argument
        dataset_dict = dataset.get_card_ratings()

        if not dataset_dict:
            return metrics

        from src.utils import normalize_color_string

        std_color = normalize_color_string(color)

        # Iterate over the card list and retrieve the GIHWR for unique cards
        for card_data in dataset_dict.values():
            card_name = card_data.get(DATA_FIELD_NAME)
            if not card_name:
                continue

            # O(1) hash lookup prevents fatal hangs when processing massive Day 1 datasets
            if card_name not in processed_cards:
                processed_cards.add(card_name)

                deck_stats = card_data.get(DATA_FIELD_DECK_COLORS, {})
                if std_color not in deck_stats:
                    continue

                color_stats = deck_stats[std_color]
                if field not in color_stats:
                    continue

                val = color_stats[field]
                # Only include valid data points to avoid calculating empty metrics
                if val != 0.0:
                    unique_gihwr.append(round(val, self._digits))

        if not unique_gihwr:
            return metrics

        metrics.mean = stats.mean(unique_gihwr)
        metrics.std = stats.pstdev(unique_gihwr)

        return metrics

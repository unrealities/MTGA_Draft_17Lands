from src import constants
from src.card_logic import get_card_colors


class SignalCalculator:
    def __init__(self, set_metrics):
        self.metrics = set_metrics
        # Get the global average win rate for "All Decks" to use as a baseline
        self.baseline_wr, _ = self.metrics.get_metrics(
            constants.FILTER_OPTION_ALL_DECKS, constants.DATA_FIELD_GIHWR
        )

        # Fallback if metrics aren't loaded or valid
        if self.baseline_wr == 0.0:
            self.baseline_wr = 54.0  # A conservative 17Lands average

    def calculate_pack_signals(self, pack_cards, current_pick):
        """
        Scans a list of cards and calculates signal scores for each color.
        Signal Score = (Lateness) * (Quality vs Baseline)
        """
        # Initialize scores: W, U, B, R, G
        color_signals = {c: 0.0 for c in constants.CARD_COLORS}

        for card in pack_cards:
            try:
                # 1. Get Stats from "All Decks" bucket
                deck_stats = card.get(constants.DATA_FIELD_DECK_COLORS, {}).get(
                    constants.FILTER_OPTION_ALL_DECKS, {}
                )
                gihwr = deck_stats.get(constants.DATA_FIELD_GIHWR, 0.0)
                ata = deck_stats.get(constants.DATA_FIELD_ATA, 0.0)

                # 2. Data Validation
                if gihwr == 0.0 or ata == 0.0:
                    continue

                # 3. Quality Filter
                # If a card has a win rate below the set average, seeing it late is not a signal
                if gihwr <= self.baseline_wr:
                    continue

                # 4. Lateness Calculation
                lateness = current_pick - ata

                if lateness <= 0:
                    continue

                # 5. Score Calculation
                quality_diff = gihwr - self.baseline_wr
                card_score = lateness * quality_diff

                # 6. Color Attribution
                card_colors = card.get(constants.DATA_FIELD_COLORS, [])

                # Handle colorless cards with colored mana costs
                if not card_colors and constants.DATA_FIELD_MANA_COST in card:
                    mana_colors = get_card_colors(card[constants.DATA_FIELD_MANA_COST])
                    card_colors = list(mana_colors.keys())

                # Distribute score to each color
                for color in card_colors:
                    if color in color_signals:
                        color_signals[color] += card_score

            except Exception:
                continue

        return color_signals

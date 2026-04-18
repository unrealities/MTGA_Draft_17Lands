from src import constants
from src.card_logic import get_card_colors


class SignalCalculator:
    def __init__(self, set_metrics):
        self.metrics = set_metrics
        # Get the global average win rate for "All Decks" to use as a baseline
        self.baseline_wr, _ = self.metrics.get_metrics(
            constants.FILTER_OPTION_ALL_DECKS, constants.DATA_FIELD_GIHWR
        )
        if self.baseline_wr == 0.0:
            self.baseline_wr = 54.0

    def calculate_pack_signals(self, pack_cards, current_pick):
        """
        Standard lateness signal (seeing good cards late).
        """
        color_signals = {c: 0.0 for c in constants.CARD_COLORS}

        for card in pack_cards:
            try:
                deck_stats = card.get(constants.DATA_FIELD_DECK_COLORS, {}).get(
                    constants.FILTER_OPTION_ALL_DECKS, {}
                )
                gihwr = deck_stats.get(constants.DATA_FIELD_GIHWR, 0.0)
                ata = deck_stats.get(constants.DATA_FIELD_ATA, 0.0)

                if gihwr <= self.baseline_wr or ata == 0.0:
                    continue

                lateness = current_pick - ata
                if lateness <= 0:
                    continue

                quality_diff = gihwr - self.baseline_wr
                card_score = lateness * quality_diff

                # Distribute score
                self._distribute_score(card, card_score, color_signals)

            except Exception:
                continue

        return color_signals

    def calculate_wheel_signals(self, current_pack_cards, original_pack_ids, dataset):
        """
        v4 Logic: Compares P1P9 content to P1P1 content.
        Calculates the 'Retention Rate' of quality for each color.

        If High Quality cards returned -> Open Lane.
        If only trash returned -> Closed Lane.
        """
        original_cards = dataset.get_data_by_id(original_pack_ids)

        # 1. Sum 'Quality' (WR > Baseline) for P1P1 by color
        p1_quality = {c: 0.0 for c in constants.CARD_COLORS}
        for card in original_cards:
            self._add_card_quality(card, p1_quality)

        # 2. Sum 'Quality' for P1P9 (Current Pack) by color
        p9_quality = {c: 0.0 for c in constants.CARD_COLORS}
        for card in current_pack_cards:
            self._add_card_quality(card, p9_quality)

        # 3. Calculate Retention
        signals = {c: 0.0 for c in constants.CARD_COLORS}
        for c in constants.CARD_COLORS:
            if p1_quality[c] > 0:
                retention = p9_quality[c] / p1_quality[c]
                # If > 30% of the quality wheeled, that's a strong signal
                if retention > 0.3:
                    signals[c] = retention * 20.0  # Scale to match normal signal scores

        return signals

    def _add_card_quality(self, card, bucket):
        stats = card.get("deck_colors", {}).get(constants.FILTER_OPTION_ALL_DECKS, {})
        wr = float(stats.get(constants.DATA_FIELD_GIHWR, 0.0))
        if wr > self.baseline_wr:
            val = wr - self.baseline_wr
            self._distribute_score(card, val, bucket)

    def _distribute_score(self, card, score, bucket):
        card_colors = card.get(constants.DATA_FIELD_COLORS, [])
        if not card_colors and constants.DATA_FIELD_MANA_COST in card:
            mana_colors = get_card_colors(card[constants.DATA_FIELD_MANA_COST])
            card_colors = list(mana_colors.keys())

        for color in card_colors:
            if color in bucket:
                bucket[color] += score

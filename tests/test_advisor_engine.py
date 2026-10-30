from unittest.mock import MagicMock

import pytest

from src.advisor.engine import BASE_SCORE, LANE_PRIOR_GAMES, WEIGHTS, DraftAdvisor


@pytest.fixture
def mock_metrics():
    metrics = MagicMock()
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


@pytest.mark.parametrize(
    "first,second,expected",
    [("B", "U", "UB"), ("U", "B", "UB"), ("G", "W", "WG"), ("R", "G", "RG")],
)
def test_main_archetype_uses_wubrg_key(mock_metrics, first, second, expected):
    """main_archetype is used to look up deck_colors stats, whose keys are
    WUBRG-ordered; it must not be alphabetically sorted (issue #203)."""
    pool = [
        {"colors": [first], "deck_colors": {"All Decks": {"gihwr": 62.0}}}
        for _ in range(4)
    ] + [
        {"colors": [second], "deck_colors": {"All Decks": {"gihwr": 60.0}}}
        for _ in range(3)
    ]
    advisor = DraftAdvisor(mock_metrics, pool)

    assert set(advisor.main_colors[:2]) == {first, second}
    assert advisor.main_archetype == expected


def test_wheel_chance(mock_metrics):
    advisor = DraftAdvisor(mock_metrics, [])
    # Should wheel if ALSA is greater than the current pick
    pct = advisor._wheel_chance(
        {"deck_colors": {"All Decks": {"alsa": 10.0}}}, pick=2, rank_in_pack=5
    )

    assert pct > 0.0


@pytest.mark.parametrize("pick, pack_size", [(6, 8), (7, 8), (8, 7)])
def test_wheel_chance_needs_nine_cards(mock_metrics, pick, pack_size):
    """A pack with fewer than 9 cards can't come back, whatever the pick."""
    advisor = DraftAdvisor(mock_metrics, [])
    pct = advisor._wheel_chance(
        {"deck_colors": {"All Decks": {"alsa": 8.5}}},
        pick=pick,
        rank_in_pack=5,
        pack_size=pack_size,
    )

    assert pct == 0.0


def test_wheel_chance_allows_last_wheelable_pick(mock_metrics):
    advisor = DraftAdvisor(mock_metrics, [])
    pct = advisor._wheel_chance(
        {"deck_colors": {"All Decks": {"alsa": 8.5}}},
        pick=6,
        rank_in_pack=5,
        pack_size=9,
    )

    assert pct > 0.0


@pytest.mark.parametrize("pack_size, wheels", [(8, False), (9, True)])
def test_evaluate_pack_wheel_chance_uses_pack_size(mock_metrics, pack_size, wheels):
    """Pick 7 of a 14-card pack (8 cards) can't wheel; pick 7 of 15 (9 cards) can."""
    advisor = DraftAdvisor(mock_metrics, [])
    pack = [
        {
            "name": f"Filler{i}",
            "colors": ["G"],
            "types": ["Creature"],
            "cmc": 2,
            "deck_colors": {"All Decks": {"gihwr": 50.0, "alsa": 8.5}},
        }
        for i in range(pack_size)
    ]

    recs = advisor.evaluate_pack(pack, current_pick=7)

    assert any(r.wheel_chance > 0 for r in recs) is wheels


def test_wheel_chance_does_not_change_score(mock_metrics):
    """The wheel chance is shown, but a likely wheel isn't marked down."""
    advisor = DraftAdvisor(mock_metrics, [])
    pack = [
        {
            "name": f"Card{i}",
            "colors": ["G"],
            "types": ["Creature"],
            "cmc": 3,
            "deck_colors": {"All Decks": {"gihwr": 55.0, "alsa": alsa}},
        }
        for i, alsa in enumerate([1.5, 1.5, 1.5, 1.5, 1.5, 12.0, 12.0, 12.0, 12.0])
    ]

    recs = {r.card_name: r for r in advisor.evaluate_pack(pack, current_pick=2)}

    assert recs["Card8"].wheel_chance >= 75.0
    assert recs["Card8"].contextual_score == recs["Card0"].contextual_score


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


def card(name, colors, gihwr, types=("Creature",), **pairs):
    """A card with an all-decks GIH WR and optional pair stats as (gihwr, samples)."""
    deck_colors = {"All Decks": {"gihwr": gihwr}}
    for pair, (wr, samples) in pairs.items():
        deck_colors[pair] = {"gihwr": wr, "samples": samples}
    return {
        "name": name,
        "colors": list(colors),
        "types": list(types),
        "deck_colors": deck_colors,
    }


def test_color_strength_counts_card_quality(mock_metrics):
    """An average card counts 1, a card one SD better 2, a bad card 0, a land 0."""
    pool = [
        card("Average", "W", 55.0),
        card("Good", "W", 59.0),
        card("Bad", "U", 47.0),
        card("Dual", "UB", 55.0, types=("Land",)),
    ]
    strength = DraftAdvisor(mock_metrics, pool).color_strength

    assert strength["W"] == pytest.approx(3.0)
    assert strength["U"] == 0.0
    assert strength["B"] == 0.0


def test_color_gap(mock_metrics):
    """How far a card's colors are behind the pool's second color."""
    pool = [card(f"W{i}", "W", 55.0) for i in range(5)]
    pool += [card(f"U{i}", "U", 55.0) for i in range(3)]
    pool += [card("B0", "B", 55.0)]
    advisor = DraftAdvisor(mock_metrics, pool)

    def gap(colors):
        return advisor.pick_features(card("X", colors, 55.0))["color_gap"]

    assert advisor.main_colors == ["W", "U"]
    assert gap("W") == gap("U") == gap("WU") == gap("") == 0.0
    assert gap("B") == pytest.approx(2.0)
    assert gap("R") == pytest.approx(3.0)
    assert gap("BR") == pytest.approx(5.0)


def test_color_support(mock_metrics):
    """The pool's strength in the card's colors, both colors for a gold card."""
    pool = [card(f"W{i}", "W", 55.0) for i in range(5)]
    pool += [card(f"U{i}", "U", 55.0) for i in range(3)]
    advisor = DraftAdvisor(mock_metrics, pool)

    def support(colors):
        return advisor.pick_features(card("X", colors, 55.0))["color_support"]

    assert support("W") == pytest.approx(5.0)
    assert support("WU") == pytest.approx(8.0)
    assert support("B") == support("") == 0.0


def test_one_color_pool_has_no_gap(mock_metrics):
    """With one color in the pool, any second color is still open."""
    advisor = DraftAdvisor(mock_metrics, [card("W0", "W", 60.0)])

    assert advisor.main_archetype == "All Decks"
    assert advisor.pick_features(card("X", "R", 55.0))["color_gap"] == 0.0


def test_lane_shrinks_with_few_games(mock_metrics):
    pool = [card(f"W{i}", "W", 55.0) for i in range(3)]
    pool += [card(f"U{i}", "U", 55.0) for i in range(2)]
    advisor = DraftAdvisor(mock_metrics, pool)

    many = advisor.pick_features(card("X", "W", 55.0, WU=(59.0, 1_000_000)))
    some = advisor.pick_features(card("X", "W", 55.0, WU=(59.0, LANE_PRIOR_GAMES)))
    other_pair = advisor.pick_features(card("X", "W", 55.0, WB=(59.0, 1_000_000)))

    assert many["lane"] == pytest.approx(1.0, abs=0.01)
    assert some["lane"] == pytest.approx(0.5)
    assert other_pair["lane"] == 0.0


def test_unrated_card(mock_metrics):
    features = DraftAdvisor(mock_metrics, []).pick_features(card("New", "G", 0.0))

    assert features["quality"] == 0.0
    assert features["unrated"] == 1.0


def test_score_is_the_weighted_sum(mock_metrics):
    pool = [card(f"W{i}", "W", 55.0) for i in range(5)]
    pool += [card(f"U{i}", "U", 55.0) for i in range(3)]
    advisor = DraftAdvisor(mock_metrics, pool)
    pack = [
        card("On", "W", 59.0, WU=(60.0, 1_000_000)),
        card("Off", "B", 63.0),
    ]

    recs = {r.card_name: r for r in advisor.evaluate_pack(pack, current_pick=3)}

    for c in pack:
        features = advisor.pick_features(c)
        expected = BASE_SCORE + sum(WEIGHTS[k] * v for k, v in features.items())
        assert recs[c["name"]].contextual_score == pytest.approx(expected, abs=0.05)
    assert any(r.startswith("Off-Color") for r in recs["Off"].reasoning)
    assert recs["Off"].archetype_fit == "Splash/Speculative"
    assert recs["On"].archetype_fit == "WU"


def test_basic_land_scores_zero(mock_metrics):
    advisor = DraftAdvisor(mock_metrics, [])
    pack = [
        {"name": "Forest", "types": ["Basic", "Land"], "colors": []},
        card("Bear", "G", 55.0),
    ]

    recs = advisor.evaluate_pack(pack, current_pick=14)

    assert [r.card_name for r in recs] == ["Bear", "Forest"]
    assert recs[1].contextual_score == 0.0
    assert recs[1].reasoning == ["Basic Land (Skip)"]

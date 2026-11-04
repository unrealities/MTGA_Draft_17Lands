import pytest
import quality


def counts():
    # [in hand, won, in hand in every game, not drawn, won]
    return {
        "All Decks": {
            "Bomb": [1000, 650, 1200, 1000, 550],  # 65%, IWD 10
            "Filler": [1000, 550, 1200, 1000, 540],  # 55%
            "Chaff": [1000, 450, 1200, 1000, 460],  # 45%
            "Rare": [100, 90, 110, 10, 5],  # too few games
        },
        "WU": {
            "Filler": [400, 240, 500, 400, 200],  # 60% in WU, 500 games
            "Chaff": [5, 5, 6, 5, 5],  # too few for a pair rating
        },
    }


def test_values_follow_the_engine():
    r = quality.Ratings(counts())
    assert r.mean == pytest.approx(55.0)
    sd = r.std
    assert r.overall("Rare") is None and r.value("Rare", "WU", "engine") is None
    # Filler in WU: shrunk by 500 / 1000 toward 55, then blended.
    w = quality.ENGINE_WEIGHT
    trusted = 0.5 * 60 + 0.5 * 55
    blended = 55 * (1 - w) + trusted * w
    assert r.value("Filler", "WU", "engine") == pytest.approx(50 + (blended - 55) / sd * 15)
    unshrunk = 55 * (1 - w) + 60 * w
    assert r.value("Filler", "WU", "no-shrinkage") == pytest.approx(
        50 + (unshrunk - 55) / sd * 15)
    assert r.value("Filler", "WU", "no-archetype") == pytest.approx(50.0)
    assert r.value("Filler", "UB", "engine") == pytest.approx(50.0)
    assert r.value("Chaff", "WU", "engine") == pytest.approx(50 - 10 / sd * 15)
    assert r.value("Filler", "WU", quality.DECK_SCORE) == pytest.approx(
        50 + (0.7 * 60 + 0.3 * 55 - 55) / sd * 15)
    # Bomb: z = 10 / sd > 1 and IWD 10 > 4.5, so its bonus is 1.15x.
    z = 10 / sd
    assert r.value("Bomb", "WU", "engine") == pytest.approx(50 + z * 15 + z * 10 * 1.15)
    assert r.value("Bomb", "WU", "no-iwd") == pytest.approx(50 + z * 15 + z * 10)
    assert r.value("Bomb", "WU", "no-power-bonus") == pytest.approx(50 + z * 15)


class FakeApp:
    def deck(self, cards):
        if "Missing" in cards:
            return None
        return [dict(types=["Land"] if n == "Plains" else ["Creature"], count=c)
                for n, c in cards.items()]


def test_deck_quality_averages_rated_spells():
    r = quality.Ratings(counts())
    decks = [
        {"id": "a", "main_colors": "WU",
         "cards": {"Plains": 17, "Filler": 2, "Chaff": 1, "Rare": 1}},
        {"id": "b", "main_colors": "WU", "cards": {"Missing": 1}},
        {"id": "c", "main_colors": "WU", "cards": {"Plains": 17, "Rare": 1}},
    ]
    out = quality.deck_quality(FakeApp(), r, decks)
    assert set(out) == {"a"}
    expected = (2 * r.value("Filler", "WU", "engine") + r.value("Chaff", "WU", "engine")) / 3
    assert out["a"]["engine"] == pytest.approx(expected)
    assert set(out["a"]) == set(quality.VERSIONS) | {quality.DECK_SCORE}


def test_training_leaves_out_the_deck_s_fold():
    # [in hand, won, not drawn, won] for each fold.
    folds = [{"All Decks": {"Bolt": [10, 6, 4, 2]}}, {"All Decks": {"Bolt": [20, 10, 5, 1]}},
             {"All Decks": {"Bolt": [30, 12, 6, 3]}}]
    assert quality.training(folds, 1) == {"All Decks": {"Bolt": [40, 18, 60, 10, 5]}}


def test_each_deck_is_rated_by_its_fold():
    from games import fold_of
    good = quality.Ratings({"All Decks": {"Card": [1000, 600, 1000, 0, 0],
                                          "Other": [1000, 500, 1000, 0, 0]}})
    bad = quality.Ratings({"All Decks": {"Card": [1000, 500, 1000, 0, 0],
                                         "Other": [1000, 600, 1000, 0, 0]}})
    decks = [{"id": f"d{i}:0", "main_colors": "WU", "cards": {"Plains": 17, "Card": 23}}
             for i in range(20)]
    by_fold = [good if f % 2 else bad for f in range(quality.FOLDS)]
    out = quality.deck_quality(FakeApp(), by_fold, decks)
    for d in decks:
        high = out[d["id"]]["no-power-bonus"] > 50
        assert high == bool(fold_of(d["id"]) % 2)

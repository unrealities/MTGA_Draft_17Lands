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


# Fold counts: [in hand, won, not drawn, won]. Every card has enough games in
# any three folds to be rated.
def folds(won=500):
    return [{"All Decks": {"Filler": [500, won, 500, 250], "Chaff": [500, 200, 500, 250]},
             "WU": {"Filler": [100, 60, 100, 50]}}
            for _ in range(quality.FOLDS)]


def in_fold(fold):
    from games import fold_of
    return next(f"d{i}:0" for i in range(1000) if fold_of(f"d{i}:0") == fold)


def test_each_splits_quality_leaves_out_its_test_folds_results():
    decks = [{"id": in_fold(f), "main_colors": "WU", "cards": {"Filler": 2, "Chaff": 1}}
             for f in range(quality.FOLDS)]
    base = quality.deck_quality(FakeApp(), quality.Splits(folds()), decks)
    held_out = 2
    changed = folds()
    changed[held_out]["All Decks"]["Filler"][1] = 100
    changed[held_out]["WU"]["Filler"][1] = 10
    other = quality.deck_quality(FakeApp(), quality.Splits(changed), decks)
    for d in decks:
        rows, new = base[d["id"]], other[d["id"]]
        assert rows[held_out] == new[held_out]
        # The same results do count in the other splits, except for the deck
        # whose own fold they are.
        moved = [t for t in range(quality.FOLDS) if rows[t] != new[t]]
        assert moved == ([] if d["id"] == decks[held_out]["id"]
                         else [t for t in range(quality.FOLDS) if t != held_out])


def test_a_deck_is_rated_without_its_own_results():
    # Changing a fold's results moves none of that fold's decks' qualities.
    decks = [{"id": in_fold(1), "main_colors": "WU", "cards": {"Filler": 2}}]
    changed = folds()
    changed[1]["All Decks"]["Filler"][1] = 100
    assert (quality.deck_quality(FakeApp(), quality.Splits(folds()), decks)
            == quality.deck_quality(FakeApp(), quality.Splits(changed), decks))


def test_only_rated_two_color_decks_are_kept():
    cards = {"Plains": 17, "Filler": 2}
    decks = [
        {"id": "a:0", "main_colors": "WU", "cards": cards},
        {"id": "b:0", "main_colors": "W", "cards": cards},
        {"id": "c:0", "main_colors": "WUB", "cards": cards},
        {"id": "d:0", "main_colors": "WU", "cards": {"Missing": 1}},
        {"id": "e:0", "main_colors": "WU", "cards": {"Plains": 17, "Rare": 1}},
    ]
    out = quality.deck_quality(FakeApp(), quality.Splits(folds()), decks)
    assert set(out) == {"a:0"}
    assert len(out["a:0"]) == quality.FOLDS
    assert len(out["a:0"][0]) == len(quality.NAMES)


def test_too_few_games_in_a_split_rates_nothing_instead_of_failing():
    few = [{"All Decks": {"Filler": [60, 30, 60, 30]}} for _ in range(quality.FOLDS)]
    decks = [{"id": "a:0", "main_colors": "WU", "cards": {"Filler": 2}}]
    assert quality.deck_quality(FakeApp(), quality.Splits(few), decks) == {}


def test_training_reads_results_only_outside_the_left_out_folds():
    # [in hand, won, not drawn, won] for each fold.
    three = [{"All Decks": {"Bolt": [10, 6, 4, 2]}}, {"All Decks": {"Bolt": [20, 10, 5, 1]}},
             {"All Decks": {"Bolt": [30, 12, 6, 3]}}]
    assert quality.training(three, {1}) == {"All Decks": {"Bolt": [40, 18, 60, 10, 5]}}
    assert quality.training(three, {0, 1}) == {"All Decks": {"Bolt": [30, 12, 60, 6, 3]}}


class Metrics:
    def __init__(self, mean, std):
        self.mean, self.std = mean, std

    def get_metrics(self, *_):
        return self.mean, self.std


def card(name, colors, overall, pair=None):
    stats = {"All Decks": {"gihwr": overall, "iwd": 0.0}}
    if pair:
        stats["WU"] = {"gihwr": pair[0], "samples": pair[1]}
    return {"name": name, "colors": colors, "types": ["Creature"], "cmc": 2, "tags": [],
            "mana_cost": "{1}{" + colors[0] + "}", "deck_colors": stats}


def test_a_two_color_deck_gets_the_score_the_advisor_gives_it():
    from src.advisor.engine import DraftAdvisor

    r = quality.Ratings(counts())
    pair = counts()["WU"]["Filler"]
    filler = card("Filler", ["W"], 55.0, (100.0 * pair[1] / pair[0], pair[2]))
    pool = [card(f"W{i}", ["W"], 70.0) for i in range(6)]
    pool += [card(f"U{i}", ["U"], 70.0) for i in range(6)]
    advisor = DraftAdvisor(Metrics(r.mean, r.std), pool)
    assert advisor.main_archetype == "WU"
    # The engine's weight at pick 7.5 is the average weight the test uses.
    # Since #259 it matches the historical no-shrinkage variant. Filler has
    # z=0, so the power bonus does not affect this base-score comparison.
    assert advisor._calculate_weighted_score(filler, 7.5) == pytest.approx(
        r.value("Filler", "WU", "no-shrinkage"))
    assert r.value("Filler", "WU", "engine") != pytest.approx(
        r.value("Filler", "WU", "no-shrinkage"))


@pytest.mark.parametrize("colors", (["W"], ["W", "U", "B"]))
def test_the_decks_left_out_are_those_the_advisor_rates_by_another_archetype(colors):
    """Mono-color: All Decks. Three colors: the pool's top two. So a deck's final
    colors don't name the advisor's archetype, and quality.py doesn't rate them."""
    from src.advisor.engine import DraftAdvisor

    pool = [card(f"{c}{i}", [c], 70.0) for c in colors for i in range(6)]
    advisor = DraftAdvisor(Metrics(55.0, 4.0), pool)
    assert advisor.main_archetype != "".join(colors)
    decks = [{"id": "a:0", "main_colors": "".join(colors), "cards": {"Filler": 2}}]
    assert quality.deck_quality(FakeApp(), quality.Splits(folds()), decks) == {}

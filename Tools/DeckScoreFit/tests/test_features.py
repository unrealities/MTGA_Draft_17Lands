import gzip
import json
import os

import features
import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DATASET = os.path.join(ROOT, "tests", "data", "MKM_PremierDraft_Data_2024_5_3.json")


@pytest.fixture(scope="module")
def app():
    return features.App(DATASET)


@pytest.fixture(scope="module")
def white_blue(app):
    """23 white or blue spells and 17 basics, as the dump lists a deck."""
    cards = app.dataset.get_card_ratings().values()
    spells = sorted(
        {
            c["name"]
            for c in cards
            if c.get("colors") in (["W"], ["U"]) and "Land" not in c.get("types", [])
        }
    )[:23]
    return dict({name: 1 for name in spells}, Plains=9, Island=8)


def deck(cards, draft="d"):
    return {
        "id": f"{draft}:0",
        "main_colors": "WU",
        "splash_colors": "",
        "skill": "0.56",
        "experience": "50",
        "cards": cards,
        "games": 3,
        "wins": 2,
    }


def test_features_are_the_apps(app, white_blue):
    rows, skipped = features.deck_rows(app, [deck(white_blue)])
    assert not skipped
    [row] = rows
    built = app.deck(white_blue)
    assert sum(c["count"] for c in built) == 40
    expected = app.scorer.deck_features(
        built, ["W", "U"], features.POOL_SIZE, app.metrics
    )
    assert row["features"] == expected
    assert row["features"]["two_colors"] == 1 and not row["features"]["missing_spells"]
    assert (row["wins"], row["games"], row["skill"]) == (2, 3, "0.56")
    assert row["extra"]["lands"] == 17 and row["extra"]["spells"] == 23


def test_finds_split_cards_by_their_front_face(app):
    assert app.deck({"Cease": 1})[0]["name"] == "Cease // Desist"


def test_skips_decks_with_cards_missing_from_the_dataset(app, white_blue):
    rows, skipped = features.deck_rows(
        app, [deck(dict(white_blue, **{"Not A Card": 1}))]
    )
    assert rows == [] and skipped == {"card not in dataset": 1}
    assert app.unmatched["Not A Card"] == 1


def test_command_line(tmp_path, white_blue, app):
    decks = tmp_path / "decks.json.gz"
    with gzip.open(decks, "wt") as f:
        json.dump([deck(white_blue)], f)
    out = tmp_path / "results" / "MKM.json"  # as in the workflow
    features.main(
        [
            "--src",
            ROOT,
            "--decks",
            str(decks),
            "--dataset",
            DATASET,
            "--set",
            "MKM",
            "--out",
            str(out),
        ]
    )
    result = json.loads(out.read_text())
    assert result["set"] == "MKM" and len(result["rows"]) == 1
    assert result["weights"] == app.scorer.WEIGHTS
    assert result["base_score"] == app.scorer.BASE_SCORE


def card(name, cost, colors, types=("Creature",), tags=(), cmc=None, wr=None):
    pips = sum(cost.split("//")[0].count(c) for c in "WUBRG")
    digits = "".join(ch if ch.isdigit() else " " for ch in cost.split("//")[0])
    out = {
        "name": name,
        "mana_cost": cost,
        "cmc": cmc if cmc is not None else pips + sum(int(n) for n in digits.split()),
        "colors": list(colors),
        "types": list(types),
        "tags": list(tags),
        "count": 1,
    }
    if wr is not None:
        out["deck_colors"] = {"All Decks": {"gihwr": wr}}
    return out


def test_rule_counts(app):
    good, bad = app.playable + 1, app.playable - 1  # rated above or below the bar
    deck = [
        card("Bolt", "{R}", "R", ("Instant",), ("removal",), wr=good),
        dict(card("Murder", "{1}{B}{B}", "B", ("Instant",), ("removal",)), count=2),
        card("Dragon", "{4}{R}{R}", "R", wr=good),
        card("Rock", "{2}", "", ("Artifact",), ("fixing_ramp",), wr=good),
        card("Dual", "", "BR", ("Land",), wr=good),
        card("Forest", "", "G", ("Land", "Basic")),
        # Off-color playables for a BR deck: the lane can't pay for them and
        # they are rated above the bar...
        card("Giant", "{4}{G}", "G", wr=good),
        card("Hybrid", "{G/U}", "GU", wr=good),
        # ...the engine reads the front face only, so an omen with a castable
        # back is off-color...
        card("Omen", "{4}{G} // {1}{R}", "G", wr=good),
        # ...and so is a land of other colors, which has no cost to read.
        card("Offdual", "", "GU", ("Land",), wr=good),
        # Off-color but not playable: rated below the bar.
        card("Splash", "{1}{G}", "G", wr=bad),
        # On-color: its colors include G, but its cost needs only B.
        card("Identity", "{1}{B}", "BG", wr=good),
        # Hybrid payable by a lane color.
        card("Either", "{B/G}", "BG", wr=good),
    ]
    counts = app.rule_counts(deck, "BR", "G")
    assert counts == {
        "removal": 3,
        "heavy": 3,  # Giant, Dragon and the omen's front
        "fixing": 3,  # the rock and the two multicolor lands
        "off_color": 4,  # Giant, Hybrid, Omen, Offdual
        "splash": 1,
    }


def test_rule_counts_follow_the_engines_castability(app):
    """Both go through is_castable(): a card is on-color by its cost, not its colors."""
    from src.advisor.mana_base import is_castable

    good = app.playable + 1
    for cost, colors in (("{1}{B}", "BG"), ("{G/U}", "GU"), ("{4}{G} // {1}{R}", "G")):
        c = card("X", cost, colors, wr=good)
        assert (app.rule_counts([c], "BR", "")["off_color"] == 1) == (
            not is_castable(c, ["B", "R"])
        )


def test_rule_counts_take_up_to_three_main_colors(app):
    good = app.playable + 1
    deck = [
        card("W1", "{W}{W}", "W", wr=good),
        card("W2", "{1}{W}", "W", wr=good),
        card("U1", "{U}", "U", wr=good),
        card("U2", "{1}{U}", "U", wr=good),
        card("B1", "{B}{B}", "B", wr=good),
        card("R1", "{R}", "R", wr=good),
    ]
    # Three main colors are all the lane, as in the engine.
    assert app.rule_counts(deck, "WUB", "")["off_color"] == 1  # R1
    # With four, the three with the most pips: W (3), U (2), B (2).
    assert app.rule_counts(deck, "WUBR", "")["off_color"] == 1  # R1


def test_playable_bar_is_the_engines(app):
    mean, std = app.metrics.get_metrics("All Decks", "gihwr")
    assert mean > 0 and std > 0
    assert app.playable == mean - std

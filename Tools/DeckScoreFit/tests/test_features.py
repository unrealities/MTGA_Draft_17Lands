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

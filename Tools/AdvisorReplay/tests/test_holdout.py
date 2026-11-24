import csv
import gzip
import io
import json

import holdout

HEADER = ["draft_id", "build_index", "main_colors", "on_play", "num_mulligans", "won",
          "deck_Bolt", "opening_hand_Bolt", "drawn_Bolt", "tutored_Bolt"]


def lines(rows):
    out = io.StringIO()
    csv.writer(out, lineterminator="\n").writerow(HEADER)
    for row in rows:
        out.write(",".join(row) + "\n")
    return out.getvalue().splitlines(keepends=True)


def game(draft, won, in_hand=True, colors="UR", deck=1, drawn=0, tutored=0):
    return [draft, "0", colors, "True", "0", str(won), str(deck),
            "1" if in_hand else "0", str(drawn), str(tutored)]


def dataset(name="Bolt"):
    stats = {"gihwr": 99.0, "gnswr": 99.0, "iwd": 9.0, "samples": 1, "alsa": 3.5}
    return {
        "card_ratings": {
            "1": {
                "name": name,
                "deck_colors": {"All Decks": dict(stats), "UR": dict(stats), "WU": dict(stats)},
            }
        }
    }


def test_read_counts_splits_games_by_draft():
    held, rest = holdout.read_counts(
        lines([game("a", True), game("b", False), game("b", True, in_hand=False)]), {"a"}
    )
    assert held["All Decks"]["Bolt"] == [1, 1, 0, 0]
    assert rest["UR"]["Bolt"] == [1, 0, 1, 1]


def test_read_counts_counts_copies_as_17lands_does():
    # Two copies in hand in a win and one in a loss: 2 of 3, not 1 of 2.
    _, rest = holdout.read_counts(
        lines([game("b", True, deck=3, drawn=1), game("b", False, deck=3)]), set()
    )
    assert rest["All Decks"]["Bolt"] == [3, 2, 3, 1]


def test_read_counts_leaves_tutored_copies_out_of_both_counts():
    _, rest = holdout.read_counts(
        lines([game("b", True, in_hand=False, deck=2, tutored=1)]), set()
    )
    assert rest["All Decks"]["Bolt"] == [0, 0, 1, 1]


def test_merged_adds_counts():
    assert holdout.merged({"UR": {"Bolt": [1, 1, 0, 0]}}, {"UR": {"Bolt": [2, 0, 1, 1]}}) == {
        "UR": {"Bolt": [3, 1, 1, 1]}
    }


def test_rates_come_from_the_counts_and_samples_from_the_whole_dump():
    whole = {"All Decks": {"Bolt": [1000, 600, 500, 250]}, "UR": {"Bolt": [600, 390, 400, 200]}}
    counts = {"All Decks": {"Bolt": [800, 400, 400, 200]}, "UR": {"Bolt": [400, 240, 300, 150]}}
    card = holdout.rebuilt(dataset(), counts, whole)["card_ratings"]["1"]["deck_colors"]
    assert card["All Decks"] == {
        "gihwr": 50.0, "gnswr": 50.0, "iwd": 0.0, "samples": 1000, "alsa": 3.5
    }
    assert card["UR"]["gihwr"] == 60.0
    assert card["UR"]["iwd"] == 10.0
    assert card["UR"]["samples"] == 600


def test_thin_cards_have_no_rate_in_either_dataset():
    whole = {"All Decks": {"Bolt": [499, 300, 10, 5]}}
    card = holdout.rebuilt(dataset(), whole, whole)["card_ratings"]["1"]["deck_colors"]
    assert card["All Decks"]["gihwr"] == 0.0
    assert card["All Decks"]["samples"] == 499
    assert card["WU"] == {"gihwr": 0.0, "gnswr": 0.0, "iwd": 0.0, "samples": 0, "alsa": 3.5}


def test_cards_the_app_has_no_data_for_stay_unrated():
    data = dataset("Forest")
    data["card_ratings"]["1"]["deck_colors"]["All Decks"].update(gihwr=0.0, samples=0)
    whole = {"All Decks": {"Forest": [1000, 600, 0, 0]}}
    card = holdout.rebuilt(data, whole, whole)["card_ratings"]["1"]["deck_colors"]
    assert card["All Decks"]["gihwr"] == 0.0


def test_double_faced_cards_match_by_front_face():
    whole = {"All Decks": {"Bolt": [1000, 600, 0, 0]}}
    card = holdout.rebuilt(dataset("Bolt // Back"), whole, whole)["card_ratings"]["1"]
    assert card["deck_colors"]["All Decks"]["gihwr"] == 60.0


def test_the_original_dataset_is_untouched():
    data = dataset()
    holdout.rebuilt(data, {}, {})
    assert data["card_ratings"]["1"]["deck_colors"]["UR"]["gihwr"] == 99.0


def write_gz(path, text):
    with gzip.open(path, "wt", encoding="utf-8") as f:
        f.write(text)


def run(tmp_path, rows, drafts, also=None):
    write_gz(tmp_path / "games.csv.gz", "".join(lines(rows)))
    write_gz(tmp_path / "drafts.json.gz", json.dumps([{"id": d} for d in drafts]))
    write_gz(tmp_path / "dataset.json.gz", json.dumps(dataset()))
    extra = []
    if also is not None:
        write_gz(tmp_path / "also.json.gz", json.dumps([{"id": d} for d in also]))
        extra = ["--also", str(tmp_path / "also.json.gz")]
    holdout.main([
        "--games", str(tmp_path / "games.csv.gz"),
        "--drafts", str(tmp_path / "drafts.json.gz"),
        "--dataset", str(tmp_path / "dataset.json.gz"),
        "--rebuilt", str(tmp_path / "rebuilt.json.gz"),
        "--heldout", str(tmp_path / "heldout.json.gz"),
    ] + extra)


def gihwr(tmp_path, name):
    with gzip.open(tmp_path / name, "rt", encoding="utf-8") as f:
        return json.load(f)["card_ratings"]["1"]["deck_colors"]["All Decks"]["gihwr"]


def test_command_line_leaves_the_sampled_drafts_out(tmp_path):
    rows = [game("a", True) for _ in range(100)]
    rows += [game("b", True) for _ in range(200)] + [game("b", False) for _ in range(200)]
    run(tmp_path, rows, ["a"])

    def gihwr(name):
        with gzip.open(tmp_path / name, "rt", encoding="utf-8") as f:
            return json.load(f)["card_ratings"]["1"]["deck_colors"]["All Decks"]["gihwr"]

    assert gihwr("rebuilt.json.gz") == 60.0
    assert gihwr("heldout.json.gz") == 50.0


def test_also_leaves_more_drafts_out_of_the_heldout_ratings_only(tmp_path):
    rows = [game("a", True) for _ in range(100)] + [game("c", False) for _ in range(100)]
    rows += [game("b", True) for _ in range(200)] + [game("b", False) for _ in range(200)]
    run(tmp_path, rows, ["a"], also=["c"])
    assert gihwr(tmp_path, "rebuilt.json.gz") == 50.0
    assert gihwr(tmp_path, "heldout.json.gz") == 50.0
    run(tmp_path, rows, ["a"])
    assert gihwr(tmp_path, "heldout.json.gz") == 40.0


def test_command_line_refuses_drafts_missing_from_the_game_data(tmp_path):
    try:
        run(tmp_path, [game("b", True)], ["a"])
    except SystemExit as e:
        assert "None of the sampled drafts" in str(e)
    else:
        raise AssertionError("should have stopped")

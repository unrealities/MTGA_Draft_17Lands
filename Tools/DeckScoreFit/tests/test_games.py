import csv
import gzip
import io
import json

import games

HEADER = ["draft_id", "build_index", "main_colors", "on_play", "num_mulligans", "won",
          "deck_Bolt", "opening_hand_Bolt", "drawn_Bolt",
          "deck_Bear", "opening_hand_Bear", "drawn_Bear"]


def dump(rows):
    out = io.StringIO()
    csv.writer(out, lineterminator="\n").writerow(HEADER)
    for row in rows:
        out.write(",".join(row) + "\n")
    return out.getvalue().splitlines(keepends=True)


def game(draft, won, bolt=("1", "0", "0"), bear=("2", "0", "0"), colors="WR",
         play="True", mulls="0"):
    return [draft, "0", colors, play, mulls, str(won), *bolt, *bear]


def test_hands_and_ratings():
    lines = dump([
        game("s", True, bolt=("1", "1", "0"), bear=("2", "0", "1")),
        game("s", False, play="False", mulls="1", bear=("2", "2.0", "0")),
        game("o", True, bolt=("1", "0", "1")),  # Bolt drawn, Bear not
        game("o", False, bolt=("1", "1", "0"), colors="UR"),
        game("p", True, bear=("0", "0", "0")),  # Bolt not drawn, no Bear
    ])
    hands, ratings = games.read_games(lines, {"s:0"})
    assert hands == [
        ["s:0", True, 0, True, {"Bolt": 1}],
        ["s:0", False, 1, False, {"Bear": 2}],
    ]
    # [in hand, won, in hand in every game, not drawn, won], from o and p only,
    # except the third.
    assert ratings["All Decks"]["Bolt"] == [2, 1, 3, 1, 1]
    assert ratings["All Decks"]["Bear"] == [0, 0, 2, 2, 1]
    assert ratings["WR"]["Bolt"] == [1, 1, 2, 1, 1]
    assert ratings["UR"]["Bolt"] == [1, 0, 1, 0, 0]


def test_command_line(tmp_path):
    dump_path = tmp_path / "games.csv.gz"
    with gzip.open(dump_path, "wt") as f:
        f.writelines(dump([game("s", True), game("o", False)]))
    decks = tmp_path / "decks.json.gz"
    with gzip.open(decks, "wt") as f:
        json.dump([{"id": "s:0"}], f)
    out = tmp_path / "out.json.gz"
    games.main(["--games", str(dump_path), "--decks", str(decks), "--out", str(out)])
    with gzip.open(out, "rt") as f:
        saved = json.load(f)
    assert len(saved["hands"]) == 1 and saved["ratings"]["All Decks"]["Bolt"][3] == 1

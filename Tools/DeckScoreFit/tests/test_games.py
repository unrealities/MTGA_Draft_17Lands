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
    hands, folds = games.read_games(lines, {"s:0"})
    assert hands == [
        ["s:0", True, 0, True, {"Bolt": 1}],
        ["s:0", False, 1, False, {"Bear": 2}],
    ]
    assert len(folds) == games.FOLDS

    def counts(colors, card):
        # [in hand, won, not drawn, won], summed over every deck's fold.
        out = [0, 0, 0, 0]
        for f in folds:
            for i, n in enumerate(f.get(colors, {}).get(card, [0] * 4)):
                out[i] += n
        return out

    assert counts("All Decks", "Bolt") == [3, 2, 2, 1]
    assert counts("All Decks", "Bear") == [2, 1, 2, 1]
    assert counts("WR", "Bolt") == [2, 2, 2, 1]
    assert counts("UR", "Bolt") == [1, 0, 0, 0]
    # Each deck's games are in its own fold only.
    f = games.fold_of("o:0")
    assert folds[f]["UR"]["Bolt"] == [1, 0, 0, 0]
    assert all("UR" not in r for i, r in enumerate(folds) if i != f)


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
    assert len(saved["hands"]) == 1
    assert sum(r.get("All Decks", {}).get("Bolt", [0, 0, 0, 0])[2] for r in saved["folds"]) == 2

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
         play="True", mulls="0", build="0"):
    return [draft, build, colors, play, mulls, str(won), *bolt, *bear]


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


def test_builds_of_a_draft_share_a_fold():
    # Enough drafts that two builds hashed apart would almost surely differ.
    drafts = [f"d{i}" for i in range(50)]
    assert all(games.fold_of(f"{d}:0") == games.fold_of(f"{d}:1") for d in drafts)
    assert len({games.fold_of(f"{d}:0") for d in drafts}) == games.FOLDS
    lines = dump([
        game("d7", True, colors="UR"),
        game("d7", False, colors="UB", build="1"),
    ])
    _, folds = games.read_games(lines, set())
    f = games.fold_of("d7:0")
    assert folds[f]["UR"]["Bolt"] == [0, 0, 1, 1]
    assert folds[f]["UB"]["Bolt"] == [0, 0, 1, 0]
    assert all(not r for i, r in enumerate(folds) if i != f)


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

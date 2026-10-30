import csv
import gzip
import io
import json

import decks

HEADER = [
    "draft_id",
    "build_index",
    "main_colors",
    "splash_colors",
    "user_game_win_rate_bucket",
    "user_n_games_bucket",
    "won",
    "deck_Plains",
    "deck_Bonder, the Brave",
    "sideboard_Bonder, the Brave",
]


def dump(rows):
    out = io.StringIO()
    csv.writer(out, lineterminator="\n").writerow(HEADER)
    for row in rows:
        out.write(",".join(row) + "\n")
    return out.getvalue().splitlines(keepends=True)


def game(draft, build="0", won=True, plains="9", bonder="2"):
    return [draft, build, "WU", "", "0.56", "50", str(won), plains, bonder, "0"]


def test_groups_games_by_deck():
    lines = dump(
        [
            game("a", won=True),
            game("a", won=False),
            game("a", build="1", plains="8", bonder="0"),
            game("b", won=False),
        ]
    )
    by_id = {d["id"]: d for d in decks.read_decks(lines, 10)}
    assert set(by_id) == {"a:0", "a:1", "b:0"}
    assert by_id["a:0"] == {
        "id": "a:0",
        "main_colors": "WU",
        "splash_colors": "",
        "skill": "0.56",
        "experience": "50",
        "cards": {"Plains": 9, "Bonder, the Brave": 2},
        "games": 2,
        "wins": 1,
    }
    # Cards with no copies in the deck are left out.
    assert by_id["a:1"]["cards"] == {"Plains": 8}
    assert (by_id["b:0"]["games"], by_id["b:0"]["wins"]) == (1, 0)


def test_keeps_the_decks_that_hash_lowest():
    rows = [game(f"d{i}", won=i % 2 == 0) for i in range(50) for _ in range(2)]
    lines = dump(rows)
    every = decks.read_decks(lines, 1000, salt="s")
    some = decks.read_decks(lines, 7, salt="s")
    lowest = sorted(every, key=lambda d: decks.deck_hash(d["id"], "s"))[:7]
    assert some == sorted(lowest, key=lambda d: d["id"])
    assert all(d["games"] == 2 for d in some)
    assert decks.read_decks(lines, 7, salt="t") != some


def test_parses_quoted_fields():
    lines = dump([game("a")])
    lines[1] = lines[1].replace("WU", '"WU"')
    assert decks.read_decks(lines, 1)[0]["main_colors"] == "WU"


def test_command_line(tmp_path):
    games = tmp_path / "games.csv.gz"
    with gzip.open(games, "wt") as f:
        f.writelines(dump([game("a"), game("b")]))
    out = tmp_path / "decks.json.gz"
    decks.main(["--games", str(games), "--decks", "1", "--out", str(out)])
    with gzip.open(out, "rt") as f:
        assert len(json.load(f)) == 1

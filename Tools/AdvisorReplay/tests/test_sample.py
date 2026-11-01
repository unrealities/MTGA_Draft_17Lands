import csv
import io

from sample import sample_drafts

HEADER = [
    "draft_id",
    "event_match_wins",
    "event_match_losses",
    "pack_number",
    "pick_number",
    "pick",
    "user_n_games_bucket",
    "user_game_win_rate_bucket",
    "pack_card_Alpha",
    "pack_card_Beta",
    "pool_Alpha",
    "pool_Beta",
]


def dump(drafts):
    """CSV text for drafts named in drafts, two picks each."""
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(HEADER)
    for draft_id in drafts:
        writer.writerow([draft_id, 7, 1, 0, 0, "Alpha", 100, 0.62, 2, 1, 0, 0])
        writer.writerow([draft_id, 7, 1, 0, 1, "Beta", 100, 0.62, 0, 1, 1, 0])
    out.seek(0)
    return out


def test_reads_each_pick():
    (draft,) = sample_drafts(dump(["d1"]), 5)
    assert draft["id"] == "d1"
    assert (draft["wins"], draft["losses"], draft["skill"], draft["games"]) == (
        7,
        1,
        0.62,
        100,
    )
    assert draft["picks"] == [
        [1, 1, "Alpha", ["Alpha", "Alpha", "Beta"], []],
        [1, 2, "Beta", ["Beta"], ["Alpha"]],
    ]


def test_sample_is_repeatable_and_salt_changes_it():
    ids = [f"d{i}" for i in range(40)]

    def sample(salt):
        return [d["id"] for d in sample_drafts(dump(ids), 10, salt)]

    assert len(sample("")) == 10
    assert sample("") == sample("")
    assert sample("") != sample("other")


def test_kept_drafts_keep_all_their_picks():
    for draft in sample_drafts(dump([f"d{i}" for i in range(40)]), 10):
        assert [p[:2] for p in draft["picks"]] == [[1, 1], [1, 2]]

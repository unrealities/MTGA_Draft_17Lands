import lanes
import lanes_report
from test_replay import app, draft, names  # noqa: F401  (fixtures)

GAMES = """draft_id,build_index,main_colors,won
d1,0,WU,True
d1,1,BU,True
d1,1,BU,False
d2,0,R,True
d2,1,RG,False
other,0,WB,True
"""


def test_app_arm_matches_the_advisor_at_every_pick(app, names):
    # lanes_of_draft stops the run if lane() and DraftAdvisor disagree.
    rows = lanes.lanes_of_draft(app, draft(names, 40), lanes.Counter())
    assert [size for _, _, size, _ in rows] == list(range(1, 40))
    assert all(len(found) == len(lanes.ARMS) for *_, found in rows)
    assert any(found[0] for *_, found in rows)


def test_pool_out_of_step_with_the_picks_is_skipped(app, names):
    d = draft(names, 3)
    d["picks"][2][4] = [names[0], names[5]]
    skipped = lanes.Counter()
    assert len(lanes.lanes_of_draft(app, d, skipped)) == 1
    assert skipped == {"pool doesn't match the earlier picks": 1}


def test_played_colors_come_from_the_build_with_most_games():
    played = lanes.played_colors(GAMES.splitlines(keepends=True), {"d1", "d2"})
    # d1's second build has more games; d2's builds tie, so the later one.
    assert played == {"d1": "UB", "d2": "RG"}


def test_verdict():
    assert lanes_report.verdict("W", "WU") == "open"
    assert lanes_report.verdict("UWB", "WU") == "right"
    assert lanes_report.verdict("WU", "WUB") == "right"
    assert lanes_report.verdict("WU", "W") == "right"
    assert lanes_report.verdict("WB", "WU") == "wrong"


def test_report(app, names):
    run = {
        "set": "MKM",
        "arms": list(lanes.ARMS),
        "skipped": {},
        "drafts": [
            {
                "id": f"d{i}",
                "skill": 0.6,
                "played": played,
                "picks": lanes.lanes_of_draft(app, draft(names[i:], 30), lanes.Counter()),
            }
            for i, played in enumerate(["WU", "BR", "G"])
        ],
    }
    text = lanes_report.report([run])
    assert "3 drafts, 87 picks" in text
    assert "| no-recency |" in text and "| MKM | 3 |" in text

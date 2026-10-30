# Advisor replay

Measures a change to the draft advisor on real drafts. It replays picks from
17Lands' public Premier Draft data through two copies of the app (a pull
request and its base) and compares them on the same drafts.

It is separate from the app: nothing in `src/` imports it, and the app's tests
don't run it. CI runs the harness's own tests on every pull request, so a change
to the app that breaks the harness fails there.

## What it reports

- **Picks:** how often the card the drafter took was the advisor's first
  choice (top-1) or among its first three (top-3), for all drafters and for
  strong ones (60%+ game win rate over 50+ games). Picking by highest GIH WR is
  shown as a yardstick.
- **Event wins:** in finished events, how event wins relate to
  - *regret*: how far the drafter's picks fell below the advisor's top choice,
    in standard deviations of the pack's scores. If an advisor knows better
    picks, drafters who stray from it should win less, so more negative is
    better;
  - *deck score*: the app's score for the best quick build of the final pool.
    More positive is better. Pool GIH WR is shown as a yardstick.

  Both are per +1 SD and control for set and the drafter's skill and games
  buckets.
- **Head minus base** for each, with a paired bootstrap standard error. Treat a
  difference smaller than about two SEs as no difference.

Card ratings come from the whole format, including the replayed drafts, so the
numbers compare advisors with each other; they aren't out-of-sample accuracy.

## On GitHub

The **Advisor replay** workflow runs on pull requests that change
`src/advisor/` or this folder, comparing the pull request with its base. It
takes about 15 minutes, and the report is on the run's summary page.

To run it by hand: Actions → Advisor replay → Run workflow. Pick the branch to
test, and set:

- `base`: the branch, tag or commit to compare with (default `main`);
- `sets`: a JSON list of set codes, for example `["FRA", "TDM"]`; empty means
  all ten;
- `drafts`: drafts per set (default 3000);
- `salt`: any text, to sample different drafts. Use a new salt to confirm a
  result on drafts it wasn't tuned on.

## Locally

```sh
SET=FRA
curl -fsSLo dump.csv.gz "https://17lands-public.s3.amazonaws.com/analysis_data/draft_data/draft_data_public.$SET.PremierDraft.csv.gz"
curl -fsSLo dataset.json.gz "https://unrealities.github.io/MTGA_Draft_17Lands/${SET}_PremierDraft_All_Data.json.gz"
git worktree add ../base main

poetry run python Tools/AdvisorReplay/sample.py --dump dump.csv.gz --drafts 300 --out drafts.json.gz
poetry run python Tools/AdvisorReplay/replay.py --src ../base --drafts drafts.json.gz --dataset dataset.json.gz --set $SET --label base --out results/$SET.base.json
poetry run python Tools/AdvisorReplay/replay.py --src . --drafts drafts.json.gz --dataset dataset.json.gz --set $SET --label head --out results/$SET.head.json
poetry run python Tools/AdvisorReplay/report.py results/*.json
```

Sampling reads the whole dump (about a minute); replaying 300 drafts through
one copy of the advisor takes about 20 seconds.

## Files

| file | does |
|---|---|
| `sample.py` | Picks drafts from a dump by a hash of their ID, so a sample is repeatable. Standard library only. |
| `replay.py` | Runs one copy of the app (`--src`) over the sampled drafts: the advisor at every pick, the deck score on the final pool. |
| `report.py` | Pairs the base and head results by draft and writes the Markdown report. Needs only NumPy. |
| `tests/` | Tests for the three scripts: `poetry run pytest Tools/AdvisorReplay/tests`. |

`replay.py` uses only the app's public entry points: `DraftAdvisor`,
`SetMetrics`, `Dataset` and the quick deck builders in `src.card_logic`. If one
of those changes, `replay.py` needs to change with it.

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A desktop overlay app (Python/Tkinter via `ttkbootstrap`) for Magic: The Gathering Arena drafting. It tails the local `Player.log` file to infer draft state in real time and recommends picks using 17Lands win-rate statistics, augmented by a local MTGA SQLite database and Scryfall. A separate standalone ETL pipeline (`server/`) runs daily in GitHub Actions to pre-aggregate 17Lands/Scryfall data and publish it to GitHub Pages for the desktop client to download.

These two halves (`src/` desktop app, `server/` ETL pipeline) share only `src/dataset_manifest.py` and are otherwise independent — don't assume changes in one require changes in the other.

## Commands

Dependency management is via **Poetry** (the project uses `pyproject.toml` + `poetry.lock`; ignore `pyproject.toml.backup` and `uv.lock`, which are untracked local experiments, not the active toolchain).

```bash
poetry install                               # install dependencies
poetry run python main.py                    # run the desktop app
poetry run pytest tests/                      # run full test suite
poetry run pytest tests/test_card_logic.py    # run a single test file
poetry run pytest tests/test_card_logic.py::test_name -v   # run a single test
poetry run pytest tests/ --cov=src            # with coverage (see .coveragerc)
poetry run python bump_version.py            # bump patch version (updates src/constants.py + pyproject.toml)
poetry run python bump_version.py major       # bump major version
poetry run python bump_version.py --set 4.50  # set version explicitly
poetry run pyinstaller main.spec --clean      # build a local binary (macOS/Linux/Windows)
```

Run the ETL pipeline locally (separate from the desktop app, needs `server/` deps):

```bash
.venv/Scripts/python.exe -m server.main       # requires an existing build/ warehouse,
                                               # or ETL_ALLOW_INITIALIZE=1 for a fresh one
```

Releases are fully automated: merging to `main`/`master` reads the version from `src/constants.py`/`pyproject.toml`, tags, builds all three platform executables, and publishes via GitHub Actions. Bump the version with `bump_version.py` on a feature branch before merging if the change should ship as a new release; otherwise merges just rebuild the existing release (fine for hotfixes).

## Architecture

Full specs live in `docs/` — read these before making non-trivial changes, they are kept current and are more detailed than this file:
- `docs/00-system-overview.md` — module map, operational lifecycle, threading/timing constraints
- `docs/01-domain-models.md` — canonical `Card`, `DraftState`, `Recommendation` shapes
- `docs/02-log-parsing-rules.md` — `Player.log` event catalog and the state machine
- `docs/03-business-logic.md` — the "Compositional Brain" scoring engine in detail
- `docs/04-external-integrations.md` — 17Lands/Scryfall/SQLite/GitHub API contracts, caching, validation
- `docs/05-server-etl-pipeline.md` — the ETL pipeline spec

### Desktop app data flow

`Player.log` (tailed every 500ms by `src/log_scanner.py`'s `ArenaScanner`) → event detected → `src/advisor/engine.py` scores the pack using cached dataset stats (`src/dataset.py`) → UI (`src/ui/`, drained every 100ms) renders recommendations. The UI thread must never block: parsing, dataset downloads, and Monte Carlo simulation all run on background threads/`ThreadPoolExecutor`s and communicate back via queues/`after()`.

Key modules:
- `src/log_scanner.py` — tails the log, owns the draft/sealed state machine (Idle → Drafting/Sealed → Game)
- `src/dataset.py` / `src/dataset_updater.py` / `src/dataset_selection.py` — cached 17Lands dataset loading, sync, and event-to-dataset matching
- `src/advisor/engine.py` — the scoring engine ("Compositional Brain"): Z-scores, lane/archetype gravity, sliding commitment curve, VOR, bomb detection (see `docs/03-business-logic.md`)
- `src/advisor/deck_builder.py`, `src/advisor/mana_base.py`, `src/advisor/simulator.py` — deck construction, Frank Karsten mana-base math, Monte Carlo deck simulation/optimizer
- `src/advisor/schema.py` — the `Recommendation` output contract consumed by the UI
- `src/file_extractor.py` — locates the MTGA install, queries the local `Raw_CardDatabase_*.sqlite` for zero-day card resolution
- `src/scryfall_tagger.py` / `src/seventeenlands.py` — external API clients with caching/throttling
- `src/ui/app.py`, `app_controller.py`, `orchestrator.py` — Tkinter app shell, wiring, and background-to-UI update plumbing
- `src/ui/windows/` — standalone dialogs/workspaces (Sealed Studio, Deck Builder windows, Compare, Settings, etc.)

Card metadata resolution is asynchronous: `Dataset.get_data_by_id()` never does network/DB IO itself — unresolved IDs are queued, and a single `card-resolver` worker resolves them (SQLite first, Scryfall fallback) against a private dataset snapshot, discarding stale results if the dataset changes mid-resolution. Failures retry with exponential backoff (5s → 5min cap) and are never persisted as resolved.

### Critical invariants (see `docs/00-system-overview.md` §5)

- **Color strings are always sorted WUBRG** (`GW` → `WG`) at ingestion time — raw 17Lands JSON keys vary and dictionary lookups assume normalized order.
- **17Lands/Scryfall requests are cached aggressively** (12–24h) — see `docs/04-external-integrations.md` for exact cache keys/TTLs per integration. Don't add a network call without a cache path.
- **Dataset writes are atomic**: write to a temp file in `Sets/`, validate, then `os.replace()`. A failed export must leave the previous file and active selection untouched.
- **UI thread never blocks** — no synchronous network/DB/file IO on the Tkinter main thread.

### ETL pipeline (`server/`)

Runs daily via GitHub Actions, scheduled by MTGpile's Arena event feed (`server/events.py`), not a manually maintained calendar. `server/extract.py` pulls Scryfall + 17Lands data, `server/transform.py` merges and enforces the "all 26 archetypes always present" contract so the desktop client never hits a `KeyError` on an unraked color pair, `server/load.py` writes `.json.gz` + manifest atomically to `build/`. The desktop client only auto-syncs datasets whose set code appears in the manifest's `active_sets`; historical sets stay download-only. See `docs/05-server-etl-pipeline.md` for the full validation/security contract on both ends (filename/path checks, SHA-256, size caps on the client; manifest/warehouse integrity on the server).

## Testing notes

- `tests/conftest.py` has autouse fixtures that reset `Theme` state between tests and patch a `ttkbootstrap` crash when widgets are destroyed mid-test — expect Tkinter-heavy tests to need a real (if headless) Tk root.
- Coverage (`.coveragerc`) measures `src` and `server` only; `src/constants.py` and `__init__.py` files are excluded.
- Regression coverage for dataset/export validation specifically lives in `tests/test_seventeenlands.py`, `tests/test_file_extractor_extra.py`, and `tests/test_download_panel.py`.

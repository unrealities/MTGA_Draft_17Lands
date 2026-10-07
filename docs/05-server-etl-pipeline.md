# Server ETL Pipeline Specification

## 1. Introduction

The Server ETL (Extract, Transform, Load) Pipeline is a standalone, automated system designed to aggregate Magic: The Gathering card metadata and telemetry. It securely fetches data from Scryfall and 17Lands, standardizes the payloads, and compresses them into `.json.gz` files. 

These compiled datasets are then deployed to a static file host (e.g., GitHub Pages), allowing the MTGA Draft Tool desktop client to download complete, pre-calculated statistical packages instantly without hammering third-party APIs.

## 2. Architecture & Execution Flow

The pipeline executes daily via GitHub Actions. MTGpile's Arena event feed determines which announced Limited sets and formats are currently active.

```mermaid
graph TD
    A[MTGpile Arena Event Feed] --> J(server/events.py)
    J -->|Determines Active Sets| B(server/main.py)
    J --> K[Generated build/calendar.json]
    B -->|1. Extract Metadata| C[Scryfall API]
    B -->|2. Extract Telemetry| D[17Lands API]
    C --> E{Transform & Merge}
    D --> E
    E -->|Inject Format Texture & Baseline Stats| F[In-Memory Payload]
    F -->|3. Load (Compress)| G[Output /build/*.json.gz]
    G --> H[manifest.json]
    G --> I[report.json]
```

## 3. Module Breakdown

| Module | Function |
| :--- | :--- |
| `config.py` | Centralizes all configuration: API delays, retry logic, WAF cooldowns, and definition of the 26 tracked color archetypes. |
| `utils.py` | Houses the `APIClient`. Wraps `requests` with robust exponential backoff, automated HTTP 429/403 (Cloudflare WAF) cooldowns, random anti-bot jitter, and a local `.api_cache` system. |
| `events.py` | Fetches MTGpile's schedule, resolves set names through Scryfall and supported 17Lands codes, and selects active event windows. |
| `extract.py` | Handles all network requests. Responsible for downloading base card definitions, Scryfall community tags (`otags`), and 17Lands archetype-specific win rates. |
| `transform.py` | The "Data Sanitizer." Merges Scryfall IDs with 17Lands `arena_id`s, guarantees all 26 archetypes are pre-initialized (even if data is missing), and formats the payload exactly to the desktop client's expectations. |
| `load.py` | Writes the final `.json.gz` files using **Atomic Writes** (writing to a `.tmp` file, then utilizing OS-level replacement) to prevent dataset corruption. |
| `report.py` | Generates a highly detailed, professional execution summary detailing pipeline intent, data sizes, network errors, and warehouse state. |

## 4. Caching & Etiquette (Critical)

The pipeline is designed to be highly respectful of community APIs:
- **Scryfall Base Cards:** Cached locally for **7 Days**. (Base set data rarely changes).
- **Scryfall Tags:** Cached locally for **7 Days**.
- **17Lands/Scryfall/MTGpile GET Requests:** Cached transparently by `APIClient` for **12 Hours** using MD5 hashing of the full URL. If the pipeline crashes, rerunning it will instantly bypass previously successful network requests.
- **Throttling:** 17Lands is rate-limited to 1 request per ~5 seconds. Scryfall is rate-limited to 1 request per 200ms. MTGpile requests are separated by at least 1 second.

## 5. Event Management (MTGpile)

The scheduling source is [MTGpile's Arena JSON feed](https://mtgpile.com/api/v1/events/arena/all.json), compiled from Wizards of the Coast's published event schedules. There is no manually maintained calendar input.

`server/events.py` translates event titles to 17Lands format identifiers and resolves set names using Scryfall's set catalog. Only codes present in 17Lands' `/data/filters` catalog are scheduled. Alchemy codes are matched against that catalog rather than inferred from a year. Unknown titles, ambiguous multi-stage events, missing source links, and incomplete or reversed date windows are logged and skipped.

Events run between their announced start and end dates, inclusive, using UTC. A missing, future-dated, or more than seven days old `as_of` stamp fails the run, as do unavailable catalogs or a feed with no resolvable Limited events. Fetch failures use the shared client's retry behavior and then fail the run; there is no fallback to a manual calendar.

The normalized schedule is written atomically to `build/calendar.json`, including source attribution and the feed's `as_of` stamp, for the website's existing calendar view. It is refreshed even when there are no active events. New supported sets require no calendar edit; new event titles may require a mapping in `FORMAT_TITLES` once their 17Lands format is known.

## 6. Transform Constraints (The "All Decks" Fallback)

Because 17Lands does not immediately have data for every color pair on Day 1 of a new format, the `transform.py` module strictly enforces a data contract for the Desktop UI:

1. Every card must have an `"All Decks"` archetype.
2. Every card must possess keys for all 26 possible archetypes (e.g., `UB`, `WUBRG`). 
3. If 17Lands did not return data for an archetype, `transform.py` injects a placeholder object with `0.0` values. This prevents the Desktop App from throwing fatal `KeyError` exceptions when a user changes their deck filter in the UI. 
4. The pipeline combines mtga_id (from 17Lands) and arena_ids (from Scryfall) into a single array to ensure Showcase, Retro, and Alternate Art card styles are successfully matched by the local MTG Arena log scanner.

## 7. Local Development

### Warehouse preservation and deployment

Each daily run restores the existing `gh-pages` branch before updating active datasets. A network or checkout failure stops the workflow. The ETL also rejects missing or malformed manifests, unsafe dataset filenames or checksums, and manifests referencing absent historical files. A failure saving the new manifest exits the process with an error, preventing deployment. ETL runs share a concurrency group so simultaneous runs cannot overwrite each other's warehouse snapshots.

For a repository's first deployment, manually dispatch **Daily Dataset ETL Pipeline** with **initialize_warehouse** enabled. This only permits initialization after Git confirms that `gh-pages` does not exist; an existing branch must still restore successfully. Normal scheduled runs cannot initialize a replacement warehouse.

### Client download checks

The desktop client permits only manifest filenames of the form `{dataset_key}_Data.json.gz`, with letters, digits, spaces, underscores and hyphens in the key. Destinations must resolve inside Sets, including existing symbolic links. It streams at most 32 MiB of compressed content, verifies SHA-256 over those compressed bytes, and decompresses at most 256 MiB. JSON metadata, date ranges and every card's archetype structure are validated before the cached dataset is atomically replaced. The local manifest is also written atomically. Rejected updates leave the prior dataset and its manifest entry intact and do not block independent valid datasets.

The manifest and payload are trusted through HTTPS and GitHub Pages. SHA-256 checks detect payload/manifest mismatches; they do not authenticate a compromised publisher.

To run the ETL pipeline locally for testing:

1. Ensure the project virtual environment has the server dependencies installed.
2. Restore an existing warehouse into `build/`, or explicitly set `ETL_ALLOW_INITIALIZE=1` for a new local warehouse. On PowerShell: `$env:ETL_ALLOW_INITIALIZE = "1"`; on bash: `export ETL_ALLOW_INITIALIZE=1`. This opt-in never bypasses validation of an existing manifest.
3. Run the pipeline module: `.venv/Scripts/python.exe -m server.main`.
4. The compressed datasets and manifest will be output to the local `build/` directory.

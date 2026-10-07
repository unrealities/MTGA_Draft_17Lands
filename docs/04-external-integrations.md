# External Integrations & APIs

**Status:** Implementation Spec | **Dependencies:** Managed via `pyproject.toml` (Poetry)

## 1. 17Lands.com API (Statistical Data)

The application relies entirely on 17Lands for win-rate data.

### A. Card Ratings Endpoint

- **URL:** `https://www.17lands.com/api/card_data`
- **Method:** GET
- **Parameters:**
  - `expansion`: Case-sensitive expansion identifier (e.g., `OTJ`, `Cube - Powered`).
  - `event_type`: Event Type (e.g., `PremierDraft`).
  - `time_period`: Preset such as `ALL_TIME` or `LATEST_EVENT`.
  - `colors`: Optional filter (e.g., `UB`).
  - `user_group`: Optional player group; omitted for All users.

`Seventeenlands._unwrap_card_payload()` accepts either a bare card list or a
`data` list inside a response object. Before caching or applying ratings, every
row must have a nonblank string name, string-or-null image fields (`url`,
`url_back`), and finite values for the statistics consumed by the client.
Booleans are rejected as statistics; game counts must be nonnegative integers
compatible with integer conversion. Missing/null statistics remain valid and
become zero during processing; compatible numeric strings and negative
improvement values remain supported. A malformed row rejects the entire response
before existing ratings or raw cache files are changed.

### B. Rate Limiting Strategy (CRITICAL)

- **Cache Directory:** Store responses in `Temp/RawCache/`.
- **Naming Convention:** `{set}_{format}_{time_period}_{color}_{user}_v2.json`, lowercased. The version marker avoids caches from the retired card-ratings route.
- **Staleness Check:** Valid, nonempty caches younger than 12 hours bypass the network. Invalid, unreadable, empty, or stale caches trigger a fetch.
- **Cache Writes:** Nonempty validated responses replace raw caches atomically. Cache IO failures are logged without discarding a successful download. Empty responses are valid but are not cached.
- **Throttling:** Sleeps **1.5 seconds** after each archetype fetched from the network; cache hits do not sleep.

### C. Manual Dataset Persistence

`FileExtractor.export_card_data()` serializes the assembled dataset to a unique
temporary file inside Sets, rejecting non-finite JSON numbers. It runs the
existing `check_file_integrity()` check on that file before installing it with
`os.replace()`. Serialization, write, validation, and replacement failures leave
the previous destination intact and return an empty filename; temporary files
are cleaned up, with cleanup failures logged. Successful installation invalidates
the local dataset listing cache.

The download window updates `latest_dataset`, writes configuration, and reports
success only when export returns a filename. An empty filename produces a save
error while retaining the active selection.

The manual integrity check remains a basic structural check, including a minimum
of ten cards; it is not the stricter cloud payload validator. It currently
examines only the first card's structure. Raw-response validation covers all rows
but does not replace complete validation of assembled local metadata.

Regression coverage is in `tests/test_seventeenlands.py`,
`tests/test_file_extractor_extra.py`, and `tests/test_download_panel.py`, covering
malformed responses/caches, sparse valid statistics, failed export preservation,
temporary-file cleanup, and activation only after a successful save.

---

## 2. Scryfall API (Metadata Backup & Tag Harvesting)

### A. Community Tags (`otags`)

The app uses the `ScryfallTagger` to harvest community-sourced roles to feed the Compositional Brain.

- **Endpoint:** `https://api.scryfall.com/cards/search?q=set:{SET} ({QUERY})`
- **Queries:** Complex regex combinations (e.g., `otag:removal OR otag:board-wipe`).
- **Cache:** Stored in `Temp/RawCache/{set}_scryfall_tags.json` for 12 hours.
- **Rate Limit:** Strictly enforces a 0.5s backoff to avoid HTTP 429 penalties.

### B. Bulk Resolution

If the local Arena Database fails to resolve an ID, the app sends a bulk query using the `/cards/collection` endpoint in chunks of 75.

`Dataset.get_data_by_id()` and name getters perform no database or network IO.
They enqueue unresolved IDs; the watchdog starts one resolver worker at a time.
`resolve_data_by_id()` is the blocking worker operation. Transient errors,
non-200 responses, and missing cards remain retryable, with delays starting at
5 seconds and doubling to a 300-second cap. Only successfully resolved metadata
is written to `custom_cards.json`; legacy numeric placeholders are ignored.

---

## 3. Local MTGA SQLite Database (Zero-Day Fallback)

To ensure the app works seamlessly on Day 1 of a new set release without waiting for 3rd party APIs, it queries local game files.

- **Path:** `MTGA_Data/Downloads/Raw/Raw_CardDatabase_*.sqlite`
- **Logic:** Joins `Cards` with `Localizations_enUS` and `Enums` to instantly resolve numeric `GrpId`s into English card names, CMCs, and Base Types.
- **Custom Installs:** Users can manually map custom installation paths via the UI (`File -> Locate MTGA Data Folder`).

---

## 4. GitHub Releases (Self-Update)

- **Endpoint:** `https://api.github.com/repos/unrealities/MTGA_Draft_17Lands/releases/latest`
- **Logic:**
  1. Fetch `tag_name` (e.g., `v4.15`).
  2. Compare with internal constant `APPLICATION_VERSION`.
  3. If `Remote > Local`: Prompt user to open the release URL.

The prompt runs on the UI thread, appears at most once per version per session,
and opens the fixed official release page only when accepted.

The public releases page treats release names, tags, asset names, and Markdown
as untrusted content. It escapes text, allows only a small set of formatting
elements, removes event attributes, and restricts links to HTTP(S). Raw release
HTML is displayed as text. Links opening a new tab use `noopener noreferrer`.

### Dataset preferences

`Auto-Sync Cloud Datasets` controls automatic dataset downloads at startup and
through the notification worker. `Check for Dataset Updates` enables the latter
only when auto-sync is also enabled. Disabling auto-sync stops that background
download path; explicit downloads remain available in Datasets. The existing
one-time version migration in `main.load_data()` still forces a dataset refresh.

---

## 5. Security & Compliance Checklist

1. [x] **User Agent:** All HTTP requests include a descriptive User-Agent header (e.g., `MTGADraftTool/5.0 (Contact: repo_url)`).
2. [x] **Read-Only:** The app never attempts to write to MTGA memory or inject inputs. It interacts strictly via `Player.log` and Local SQLite mapping.
3. [x] **Data Minimization:** Logs or deck lists are never uploaded to any server unless the user explicitly exports them.

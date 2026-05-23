# External Integrations & APIs

**Status:** Implementation Spec | **Dependencies:** Managed via `pyproject.toml` (Poetry)

## 1. 17Lands.com API (Statistical Data)

The application relies entirely on 17Lands for win-rate data.

### A. Card Ratings Endpoint

- **URL:** `https://www.17lands.com/card_ratings/data`
- **Method:** GET
- **Parameters:**
  - `expansion`: Set Code (e.g., `OTJ`, `MH3`).
  - `format`: Event Type (e.g., `PremierDraft`).
  - `start_date`: YYYY-MM-DD
  - `end_date`: YYYY-MM-DD
  - `colors`: Optional filter (e.g., `UB`).

### B. Rate Limiting Strategy (CRITICAL)

- **Cache Directory:** Store responses in `Temp/RawCache/`.
- **Naming Convention:** `{set}_{format}_{start}_{end}_{color}_{user}.json`.
- **Staleness Check:** Network fetches are completely bypassed if the file is < 12 Hours old.
- **Throttling:** Sleeps **1.5 seconds** between archetype requests.

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

---

## 5. Security & Compliance Checklist

1. [x] **User Agent:** All HTTP requests include a descriptive User-Agent header (e.g., `MTGADraftTool/5.0 (Contact: repo_url)`).
2. [x] **Read-Only:** The app never attempts to write to MTGA memory or inject inputs. It interacts strictly via `Player.log` and Local SQLite mapping.
3. [x] **Data Minimization:** Logs or deck lists are never uploaded to any server unless the user explicitly exports them.

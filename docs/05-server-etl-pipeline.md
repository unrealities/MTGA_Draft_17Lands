# Server ETL Pipeline Specification

## 1. Introduction

The Server ETL (Extract, Transform, Load) Pipeline is a standalone, automated system designed to aggregate Magic: The Gathering card metadata and telemetry. It securely fetches data from Scryfall and 17Lands, standardizes the payloads, and compresses them into `.json.gz` files. 

These compiled datasets are then deployed to a static file host (e.g., GitHub Pages), allowing the MTGA Draft Tool desktop client to download complete, pre-calculated statistical packages instantly without hammering third-party APIs.

## 2. Architecture & Execution Flow

The pipeline executes daily via GitHub Actions. It is strictly calendar-driven, meaning it only spends compute resources updating sets that are currently active on MTG Arena.

```mermaid
graph TD
    A[calendar.json] -->|Determines Active Sets| B(server/main.py)
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
| `extract.py` | Handles all network requests. Responsible for downloading base card definitions, Scryfall community tags (`otags`), and 17Lands archetype-specific win rates. |
| `transform.py` | The "Data Sanitizer." Merges Scryfall IDs with 17Lands `arena_id`s, guarantees all 26 archetypes are pre-initialized (even if data is missing), and formats the payload exactly to the desktop client's expectations. |
| `load.py` | Writes the final `.json.gz` files using **Atomic Writes** (writing to a `.tmp` file, then utilizing OS-level replacement) to prevent dataset corruption. |
| `report.py` | Generates a highly detailed, professional execution summary detailing pipeline intent, data sizes, network errors, and warehouse state. |

## 4. Caching & Etiquette (Critical)

The pipeline is designed to be highly respectful of community APIs:
- **Scryfall Base Cards:** Cached locally for **7 Days**. (Base set data rarely changes).
- **Scryfall Tags:** Cached locally for **7 Days**.
- **17Lands/Scryfall GET Requests:** Cached transparently by `APIClient` for **12 Hours** using MD5 hashing of the full URL. If the pipeline crashes, rerunning it will instantly bypass previously successful network requests.
- **Throttling:** 17Lands is rate-limited to 1 request per ~5 seconds. Scryfall is rate-limited to 1 request per 200ms.

## 5. Event Management (`calendar.json`)

The pipeline does not guess what to download. It reads `server/calendar.json` to determine exactly which sets and formats to update.

**To add a new set to the pipeline:**
Add an object to the `events` array. The pipeline will automatically fetch data for it every day between the `start_date` and `end_date`.

```json
{
    "set_code": "MH3",
    "formats": [
        "PremierDraft",
        "TradDraft"
    ],
    "start_date": "2024-06-11",
    "end_date": "2025-01-01"
}
```

## 6. Transform Constraints (The "All Decks" Fallback)

Because 17Lands does not immediately have data for every color pair on Day 1 of a new format, the `transform.py` module strictly enforces a data contract for the Desktop UI:

1. Every card must have an `"All Decks"` archetype.
2. Every card must possess keys for all 26 possible archetypes (e.g., `UB`, `WUBRG`). 
3. If 17Lands did not return data for an archetype, `transform.py` injects a placeholder object with `0.0` values. This prevents the Desktop App from throwing fatal `KeyError` exceptions when a user changes their deck filter in the UI. 
4. The pipeline combines `mtga_id` (from 17Lands) and `arena_ids` (from Scryfall) into a single array to ensure Showcase, Retro, and Alternate Art card styles are successfully matched by the local MTG Arena log scanner.
```

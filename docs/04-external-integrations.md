# External Integrations & APIs

**Status:** Implementation Spec | **Dependencies:** `requests`, `PIL`

## 1. 17Lands.com API (Statistical Data)

The application relies entirely on 17Lands for win-rate data. Note that 17Lands does **not** have an official public API documentation; this usage is based on "gentlemen's agreements" regarding rate limiting.

### A. Card Ratings Endpoint

* **URL:** `https://www.17lands.com/card_ratings/data`
* **Method:** GET
* **Parameters:**
  * `expansion`: Set Code (e.g., `OTJ`, `MH3`).
  * `format`: Event Type (e.g., `PremierDraft`).
  * `start_date`: YYYY-MM-DD (Usually set start).
  * `end_date`: YYYY-MM-DD (Today).
  * `colors`: Optional filter (e.g., `UB`). If omitted, returns all.

### B. Rate Limiting Strategy (CRITICAL)

To avoid IP bans, the new application **MUST** implement the following caching logic (found in `src/seventeenlands.py`):

1. **Cache Directory:** Store responses in `Temp/RawCache/`.
2. **Naming Convention:** `{set}_{format}_{color}.json` (e.g., `otj_premierdraft_ub.json`).
3. **Staleness Check:**
    * On Request: Check file modification time (`mtime`).
    * If `TimeSinceModified < 24 Hours`: **RETURN CACHE**. Do not hit network.
    * If `TimeSinceModified > 24 Hours`: Fetch fresh data and overwrite cache.
4. **Throttling:** When fetching multiple archetypes (e.g., "All", "WU", "UB"), sleep **1.5 seconds** between requests.

### C. Data Normalization

The API returns colors in varying orders (e.g., "GW").

* **Requirement:** The app must normalize ALL keys to **WUBRG** order (e.g., `GW` -> `WG`) before storage/lookup.

---

## 2. Google Cloud Functions (OCR Service)

This is a stateless microservice used to solve the "P1P1 Gap" (where logs don't show cards until after a pick).

* **Trigger:** User clicks "P1P1" button (manual action).
* **URL:** `https://us-central1-mtgalimited.cloudfunctions.net/pack_parser`
* **Method:** POST
* **Payload (JSON):**

    ```json
    {
      "image": "base64_encoded_string...", // Screenshot of main monitor
      "card_names": ["Card A", "Card B", ...] // Full list of ALL cards in the set
    }
    ```

* **Response:** `["Card A", "Card B", ...]` (List of detected strings).

### Usage Constraints

1. **Privacy:** Do not send screenshots automatically. Only on explicit user action.
2. **Performance:** Compressing the image (JPEG/PNG) before Base64 encoding is recommended to reduce payload size.
3. **Fallback:** If this service fails (500/404), the app should fail silently and wait for log data.

---

## 3. Scryfall API (Metadata Backup)

Used to build the local ID-to-Name database if Arena's local files are unreadable.

* **Endpoint:** `https://api.scryfall.com/sets`
* **Usage:**
    1. Fetch list of all sets.
    2. Match `arena_code` to the current log's Set ID.
    3. Download card definitions to map `arena_id` -> `name`.
* **Etiquette:** Scryfall requires a 50-100ms delay between requests.

---

## 4. GitHub Releases (Self-Update)

* **Endpoint:** `https://api.github.com/repos/unrealities/MTGA_Draft_17Lands/releases/latest`
* **Logic:**
    1. Fetch `tag_name` (e.g., `v3.38`).
    2. Compare with internal constant `APPLICATION_VERSION`.
    3. If `Remote > Local`: Prompt user to open the release URL.

---

## 5. Security & Compliance Checklist

When migrating, ensure these standards are met:

1. [ ] **User Agent:** All HTTP requests must include a descriptive User-Agent header (e.g., `MTGADraftTool/4.0 (Contact: repo_url)`).
2. [ ] **Read-Only:** The app must never attempt to write to MTGA memory or inject inputs. It interacts strictly via `Player.log` and Screenshots.
3. [ ] **Data Minimization:** Do not upload logs or deck lists to any server unless the user explicitly exports them.

# System Overview & Architecture

**Status:** Active | **Current Version:** 4.16 | **Target:** Architecture Specification

## 1. Introduction

The MTGA Draft Tool is a reactive desktop overlay for Magic: The Gathering Arena (MTGA). It functions as a sidecar process that monitors local game logs to infer draft state and provides real-time statistical advice based on data from 17Lands.com, augmented by deep local MTGA SQLite database queries.

## 2. Core Architecture

The system follows a uni-directional data flow, heavily utilizing background threading to ensure the UI remains responsive (Zero-Idle Fast Path).

```mermaid
graph TD
    %% Cloud ETL Pipeline
    Z[Cloud ETL Server] -->|Aggregates Daily| Y[GitHub Pages]
    Y -->|Downloads manifest.json| X(App Auto-Updater)

    %% Local App Flow
    A[MTGA Client] -->|Writes to| B(Player.log)
    A -->|Local SQLite DB| DB[(Raw_CardDatabase)]
    B -->|Tails File| C{Log Scanner}

    C -->|Event: Start Draft| D[Data Manager]
    X -->|Caches Active Sets| F[Local Storage]

    %% The Fallback
    D -.->|Manual Historical Fetch| E[17Lands API]
    E -.-> F

    C -->|Event: Pack Data| G[Advisor Engine]
    F -->|Card Stats & Tags| G
    DB -->|Resolves Unknown IDs (Zero-Day)| G

    H[Taken Cards Pool] -->|Current Deck State| G

    G -->|Calculate Score| I[Tabbed UI / Dashboard / Sealed Studio]
    I -->|Render| J((User Display))
```

## 3. Key Modules

| Module             | Function                                                                                                                                                                   | Dependencies     | Criticality                     |
| :----------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :--------------- | :------------------------------ |
| **Log Scanner**    | Tails `Player.log` on a background thread, executes normalized matching, manages state machine (Idle -> Drafting -> Sealed -> Game).                                       | OS File System   | **High** (App fails without it) |
| **Data Manager**   | Downloads/Caches cloud datasets. Handles 17Lands/Scryfall fallback (if data is missing/incomplete).                                                                        | 17Lands API      | **High**                        |
| **Advisor Engine** | The "Compositional Brain" (v5.5). Normalizes win-rates, calculates Z-Scores, applies Lane Commitment, tracks VOR (Value Over Replacement), and measures pip-density.       | None (Pure Math) | **High**                        |
| **Deck Builder**   | Interactive drag-and-drop deck construction environment. Generates base archetypes, applies 1-click "Auto-Lands" math, and features an on-demand AI Monte Carlo optimizer. | Card Logic       | Medium                          |
| **Sealed Studio**  | A dedicated workspace for 90+ card pools featuring AI Shell Generation and a 1-to-1 MTGA-style visual CMC-stacked interface.                                               | Card Logic       | Medium                          |

## 4. Operational Lifecycle

### Phase B: The Draft Loop (Active)

The application polls for file changes via a background thread every **100ms** to ensure zero UI freezing.

1. **State: Waiting for Event**
   - Listens for: `[UnityCrossThreadLogger]==> Event_Join` or `"CardPool":[`
   - Action: Identify Set Code (e.g., "OTJ"). Download/Load JSON stats from 17Lands. Map local SQLite database for zero-day card names.

2. **State: Pack Review**
   - Listens for: `Draft.Notify` containing `PackCards` array.
   - Action:
     1. Retrieve stats for `CardsInPack`.
     2. Retrieve stats for `TakenCards` (User's pool).
     3. Pass data to **Advisor Engine**.
     4. Render UI Tables sorted by contextual "Score".

3. **State: Pick Confirmation**
   - Listens for: `Event_PlayerDraftMakePick`.
   - Action: Move selected `GrpId`(s) from "Pack" array to "TakenCards" array. Update "Signals" logic.

### Phase C: Shutdown

- Save window coordinates, sash locations, and column preferences to `config.json` via thread-safe atomic writes.

## 5. Constraints & Invariants

1. **Rate Limiting:** 17Lands and Scryfall API requests must be cached aggressively. Network requests use an exponential backoff to handle HTTP 429/403 responses gracefully.
2. **Color Normalization:** All color strings must be sorted WUBRG (`GW` -> `WG`). The keys in 17Lands JSONs vary; the app normalizes them upon dataset ingestion to ensure dictionary lookups never fail.

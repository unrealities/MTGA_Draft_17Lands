# System Overview & Architecture

**Status:** Draft | **Legacy Version:** Python 3.38 | **Target:** Migration Specification

## 1. Introduction

The MTGA Draft Tool is a reactive desktop overlay for Magic: The Gathering Arena (MTGA). It functions as a sidecar process that monitors local game logs to infer draft state and provides real-time statistical advice based on data from 17Lands.com.

## 2. Core Architecture

The system follows a uni-directional data flow.

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
    F -->|Card Stats| G
    DB -->|Resolves Unknown IDs| G

    H[Taken Cards Pool] -->|Current Deck State| G

    G -->|Calculate Score| I[Tabbed UI / Dashboard]
    I -->|Render| J((User Display))
```

## 3. Key Modules

| Module             | Function                                                                                                                                                                   | Dependencies     | Criticality                     |
| :----------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :--------------- | :------------------------------ |
| **Log Scanner**    | Tails `Player.log`, executes Regex matching, manages state machine (Idle -> Drafting -> Game).                                                                             | OS File System   | **High** (App fails without it) |
| **Data Manager**   | Downloads/Caches set data. Handles fallback (if Premier data missing, use Quick data).                                                                                     | 17Lands API      | **High**                        |
| **Advisor Engine** | The "Brain." Normalizes win-rates, calculates Z-Scores, applies "Lane Commitment" logic.                                                                                   | None (Pure Math) | **High**                        |
| **Deck Builder**   | Interactive drag-and-drop deck construction environment. Generates base archetypes, applies 1-click "Auto-Lands" math, and features an on-demand AI Monte Carlo optimizer. | Card Logic       | Medium                          |

## 4. Operational Lifecycle

### Phase B: The Draft Loop (Active)

The application polls for file changes every **1000ms**.

1. **State: Waiting for Event**
   - Listens for: `[UnityCrossThreadLogger]==> Event_Join`
   - Action: Identify Set Code (e.g., "OTJ"). Download/Load JSON stats from 17Lands.

2. **State: Pack Review**
   - Listens for: `Draft.Notify` containing `PackCards` array.
   - Action:
     1. Retrieve stats for `CardsInPack`.
     2. Retrieve stats for `TakenCards` (User's pool).
     3. Pass data to **Advisor Engine**.
     4. Render Overlay Table sorted by "Score".

3. **State: Pick Confirmation**
   - Listens for: `Event_PlayerDraftMakePick`.
   - Action: Move selected `GrpId` from "Pack" array to "TakenCards" array. Update "Signals" logic.

### Phase C: Shutdown

- Save window coordinates and column preferences to `config.json`.

## 5. Constraints & Invariants

1. **Rate Limiting:** 17Lands API requests must be cached for 24 hours. Do not fetch on every launch.
2. **Color Normalization:** All color strings must be sorted WUBRG (`GW` -> `WG`). The keys in 17Lands JSONs vary; the app must normalize them before lookup or data will appear missing.

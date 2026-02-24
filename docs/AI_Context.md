# AI Context: MTGA Draft Tool (Migration Specification)

**Role:** You are an expert Systems Architect migrating a Python/Tkinter application to a modern stack (Rust/Tauri or TS/Electron).
**Goal:** Replicate the "Advisor" business logic exactly while improving performance and maintainability.

## 1. System Architecture

The application is a **Reactive Overlay** for Magic: The Gathering Arena (MTGA).

* **Input:** Tails `Player.log` (UTF-8) in real-time.
* **State:** Tracks Draft Pack (Current Options) and Pool (Taken Cards).
* **Output:** Renders a floating UI table ranking cards by a contextual "Score" (0-100).

## 2. Critical Constraints

1. **The P1P1 Gap:** MTGA logs do NOT reveal Pack 1 Pick 1 cards immediately. You must implement a **Screen Capture + OCR** fallback for this specific state.
2. **Rate Limiting:** 17Lands API requests must be cached locally for **24 hours**. Never fetch on every startup.
3. **Color Normalization:** All color keys must be sorted **WUBRG** (e.g., store "GW" as "WG"). Failure to do this breaks dictionary lookups.
4. **Read-Only:** Never write to MTGA memory or inject input. Only read logs/screen.

## 3. Data Schema (Types)

```typescript
// The fundamental unit of data
type Card = {
  id: number;           // Arena GrpId
  name: string;
  colors: string[];     // ["W", "U"] (Sorted!)
  stats: {
    gihwr: number;      // Games in Hand Win Rate (0-100)
    alsa: number;       // Average Last Seen At (1-15)
  }
};

// The State Machine
type DraftState = {
  set_code: string;     // "OTJ"
  pack_num: 1 | 2 | 3;
  pick_num: 1...15;
  pool: Card[];         // Cards user has picked
  current_pack: Card[]; // Cards currently on screen
};
```

## 4. Log Parsing Logic (Regex)

**Input Normalization:** `Upper() -> Remove("_") -> Remove(" ")`

| Event | Trigger (Normalized) | Payload Key | Action |
| :--- | :--- | :--- | :--- |
| **Start Draft** | `EVENTJOIN` | `EventName` | Parse Set Code (e.g., `PremierDraft_OTJ`). Load JSON stats. |
| **New Pack** | `DRAFT.NOTIFY` | `PackCards` | Update `current_pack`. Trigger Advisor Calc. |
| **Make Pick** | `EVENTPLAYERDRAFTMAKEPICK` | `GrpId` | Move card from `pack` -> `pool`. Update Signals. |
| **Bot Draft** | `BOTDRAFTDRAFTSTATUS` | `DraftPack` | *Edge Case:* Convert 0-indexed pack/pick to 1-indexed. |

## 5. The "Advisor" Scoring Algorithm

This determines the "Value" column in the UI.

$$ Score = (Base + ZScore) \times ColorMult \times HungerMult $$

1. **Base:** `(GIHWR - 45.0) * 5.0` (Clamped 0-100).
2. **Z-Score:** If `(GIHWR - PackMean) / PackStdDev > 1.0`, add `Z * 15`.
3. **Color Mult (Lane Commitment):**
    * **P1P1-P1P7:** 1.0 (Stay Open).
    * **Pack 2:** 0.3 if off-color (Soft Lock).
    * **Pack 3:** 0.05 if off-color (Hard Lock).
    * *Override:* If `Z-Score > 2.0` (Bomb), reduce penalty to allow pivoting.
4. **Hunger Mult (Deck Needs):**
    * `Creatures < Expected`: 1.2x boost to Creatures.
    * `Removal < 2` (Late Game): 1.3x boost to Removal.

## 6. Signal Detection Logic

* **Goal:** Detect "Open Lanes" (Colors being passed).
* **Logic:**
  * Iterate cards in `current_pack`.
  * `Lateness = CurrentPick - Card.ALSA`.
  * If `Lateness > 0` AND `Card.GIHWR > SetAverage`:
  * `SignalScore += Lateness * (Card.GIHWR - SetAverage)`.
* **Display:** Sum scores by color. High score = Open Lane.

## 7. External Integrations

1. **17Lands:** `GET /card_ratings/data?expansion={SET}&format={FMT}`.
2. **Google OCR:** `POST /pack_parser` (Payload: `{image: "base64", candidates: ["list", "of", "names"]}`).

# Domain Models & Data Structures

**Purpose:** Defines the core data structures used throughout the application logic.
**Target:** AI Context & Type Definition for Migration.

## 1. The Card Object (Canonical)

Every card flowing through the system eventually matches this shape.

```json
{
  "arena_id": 12345,          // Integer: The 'GrpId' from logs
  "name": "Lightning Bolt",   // String: English name
  "colors": ["R"],            // Array: Normalized WUBRG
  "cmc": 1,                   // Integer: Converted Mana Cost
  "types": ["Instant"],       // Array: Super types
  "meta": {
    "is_bomb": false,         // Derived: Z-Score > 2.0
    "tier": "A"               // Derived: Tier list grade
  }
}
```

## 2. The Statistical Record (17Lands)

Data fetched from 17Lands `card_ratings`.

```json
{
  "gihwr": 58.5,  // Games in Hand Win Rate (0.0 - 100.0)
  "ohwr": 56.2,   // Opening Hand Win Rate
  "alsa": 2.1,    // Average Last Seen At (1.0 - 15.0)
  "iwd": 5.4,     // Improvement When Drawn
  "sample_size": 15000
}
```

## 3. The Draft State (In-Memory)

The mutable state maintained during a draft session.

```typescript
interface DraftState {
  eventId: string;          // e.g., "PremierDraft_OTJ_2024..."
  set: string;              // "OTJ"
  heroColor: string[];      // Top 2 colors (e.g., ["R", "W"])
  
  packNumber: number;       // 1, 2, or 3
  pickNumber: number;       // 1 to 15
  
  currentPack: number[];    // Array of Arena IDs
  takenCards: number[];     // Array of Arena IDs (Pool)
  
  signals: {
    W: number; // Signal score (0-100)
    U: number;
    B: number;
    R: number;
    G: number;
  }
}
```

## 4. The Advisor Recommendation

The output of the logic engine sent to the UI.

```typescript
interface Recommendation {
  cardName: string;
  score: number;            // 0.0 - 100.0 (The primary sort key)
  
  factors: {
    baseWinRate: number;    // Raw GIHWR
    zScore: number;         // Statistical advantage vs pack average
    colorPenalty: number;   // 1.0 (None) to 0.05 (Hard Lock)
    hungerBonus: number;    // Multiplier for deck needs (Creatures/Removal)
  }
  
  notes: string[];          // e.g. ["Critical Removal Need", "Splashable"]
}

# Domain Models & Data Structures

**Purpose:** Defines the core data structures used throughout the application logic.
**Target:** AI Context & Type Definition for Migration/Development.

## 1. The Card Object (Canonical)

Every card flowing through the system eventually matches this shape after data merging.

```typescript
type Card = {
  arena_ids: number[] // Array of MTGA GrpIds (handles alt-arts & printings)
  name: string // Sanitized English name
  cmc: number // Base Converted Mana Cost
  mana_cost: string // Raw string (e.g., "{1}{W}{U}")
  types: string[] // Supertypes: ["Creature", "Artifact"]
  colors: string[] // ["W", "U"] (Sorted WUBRG!)
  tags: string[] // Scryfall semantic roles: ["removal", "fixing_ramp"]
  deck_colors: {
    [archetype: string]: {
      gihwr: number // Games in Hand Win Rate (0.0 - 100.0)
      alsa: number // Average Last Seen At (1.0 - 15.0)
      iwd: number // Improvement When Drawn
      samples: number // Sample size for statistical confidence
    }
  }
}
```

## 2. The Statistical Record (17Lands Raw)

Data fetched directly from the 17Lands `card_ratings` API before transformation.

```json
{
  "gihwr": 58.5, // Games in Hand Win Rate
  "ohwr": 56.2, // Opening Hand Win Rate
  "alsa": 2.1, // Average Last Seen At
  "iwd": 5.4, // Improvement When Drawn
  "sample_size": 15000
}
```

## 3. The Draft State (In-Memory)

The mutable state maintained during a draft session by `ArenaScanner`.

```typescript
interface DraftState {
  current_draft_id: string // e.g., UUID from Arena
  event_string: string // "PremierDraft_OTJ_2024..."
  draft_type: number // Enumerator (e.g., 2 for PremierDraft_V2)
  draft_sets: string[] // ["OTJ"]

  current_pack: number // 1, 2, or 3
  current_pick: number // 1 to 15 (or 14)

  pack_cards: string[][] // Matrix of cards currently in packs (for 8 players)
  taken_cards: string[] // Array of Arena IDs (The active Pool)
  picked_cards: string[][] // Matrix tracking exactly what was picked from where

  draft_history: {
    // Used for exporting to CSV/JSON
    Pack: number
    Pick: number
    Cards: string[]
  }[]
}
```

## 4. The Advisor Recommendation

The output of the logic engine sent to the UI, defined by `src/advisor/schema.py`.

```typescript
interface Recommendation {
  card_name: string
  contextual_score: number // Primary sort key (0-100)
  z_score: number // Statistical advantage vs pack average
  wheel_chance: number // 0.0 to 100.0 (Polynomial probability)
  reasoning: string[] // Array of human-readable factors (e.g. ["Critical: Needs Removal"])
  is_elite: boolean // True if card is a game-warping Bomb
  tags: string[] // Scryfall semantic tags
}
```

"""Let the advisor draft a whole 17Lands draft itself, and score the deck it ends with.

replay.py --simulate calls simulate_draft for each draft. The advisor takes its
own first choice at every pick, from the packs the drafter saw, and the app's
Suggest Deck builds its pool. The first suggested deck's score, as an expected
game win rate, is the draft's simulated deck win rate. A head and its base
draft the same packs, so the paired difference measures how much better a deck
the head's advice drafts, by the deck score's own lights.

The packs. In an eight-player pod, the pack at pick p of a round was last seen
at pick p - 8: picks 1 to 8 see packs the drafter's own picks never touched,
and from pick 9 a pack comes back without the card the drafter took from it.
When the advisor took A where the drafter took H, the returning pack would hold
H and not A. So from the second lap on, if A is in the pack, A is swapped for H
and the swap carries on to the next lap. If A is not in the pack, another
drafter took it in the real draft; what they'd have taken instead is unknown,
so the pack is left as it was and the swap is dropped. Drafters downstream are
assumed to pick as they did, whatever the advisor took.

Picks the dump has no row for (TLA and TMT have no first pick) are forced: the
advisor gets the drafter's card, read from the pools, and no swap follows.
"""

import math
from collections import Counter

PLAYERS = 8


def card_names(draft):
    """{(pack, pick): (taken, pack names, pool names)} from sample.py's picks."""
    return {(p[0], p[1]): (p[2], p[3], p[4]) for p in draft["picks"]}


def forced_picks(draft):
    """{(pack, pick): card} for picks the dump has no row for, read from the pools.

    None if the pools don't account for them (the draft can't be simulated)."""
    rows = card_names(draft)
    if not rows:
        return None
    packs = sorted({k[0] for k in rows})
    picks_per_round = max(k[1] for k in rows)
    slots = [(r, p) for r in range(1, max(packs) + 1) for p in range(1, picks_per_round + 1)]
    out, gap, before = {}, [], Counter()
    for slot in slots:
        if slot not in rows:
            gap.append(slot)
            continue
        taken, _, pool = rows[slot]
        if gap:
            missing = Counter(pool) - before
            if sum(missing.values()) != len(gap):
                return None
            for s, card in zip(gap, sorted(missing.elements())):
                out[s] = card
            gap = []
        before = Counter(pool) + Counter([taken])
    if gap:  # missing picks at the very end: nothing after them to read
        return None
    return out


def returning_pack(pack, swaps, counts):
    """The pack as the advisor's draft would see it, and the swaps still pending.

    swaps: [(advisor's card, drafter's card)] from earlier laps of this pack."""
    pack, kept = list(pack), []
    for mine, theirs in swaps:
        if mine in pack:
            pack[pack.index(mine)] = theirs
            kept.append((mine, theirs))
            counts["wheel swap applied"] += 1
        else:
            counts["wheel swap dropped (taken by another drafter)"] += 1
    return pack, kept


def win_rate(score, scorer):
    """A deck score as an expected game win rate, in percent."""
    log_odds = scorer.WIN_LOG_ODDS_AT_BASE + (score - scorer.BASE_SCORE) * scorer.WIN_LOG_ODDS_PER_POINT
    return 100.0 / (1.0 + math.exp(-log_odds))


def simulate_draft(app, draft, counts):
    """The advisor's own draft from these packs and its deck, or None.

    app is replay.App; counts a Counter of what the simulation did."""
    forced = forced_picks(draft)
    if forced is None:
        counts["drafts: pools don't account for missing picks"] += 1
        return None
    rows = card_names(draft)
    name = lambda n: app.full_names.get(n, n)  # dump names to dataset names
    picks_per_round = max(k[1] for k in rows)
    rounds = max(k[0] for k in rows)
    pool, agree, decided, swaps_fired = [], 0, 0, 0
    for r in range(1, rounds + 1):
        pending = {}  # pack slot (pick - 1) % PLAYERS -> swaps
        for p in range(1, picks_per_round + 1):
            if (r, p) in forced:
                pool.append(name(forced[(r, p)]))
                counts["picks forced (no row in the dump)"] += 1
                continue
            taken, pack_names, _ = rows[(r, p)]
            theirs = name(taken)
            slot = (p - 1) % PLAYERS
            before = counts["wheel swap applied"]
            pack_names, pending[slot] = returning_pack(
                [name(n) for n in pack_names], pending.get(slot, []), counts
            )
            swaps_fired += counts["wheel swap applied"] > before
            if p > PLAYERS:
                counts["wheel picks"] += 1
            pack = app.cards(pack_names)
            distinct = {c["name"] for c in pack}
            if len(distinct) >= 2:
                scores = app.advise(pack, app.cards(pool), r, p)
                mine = sorted(scores, key=lambda n: -scores[n])[0] if scores else theirs
                decided += 1
                agree += mine == theirs
            elif distinct:
                mine = next(iter(distinct))
            else:
                mine = theirs
                counts["picks with no known card: took the drafter's"] += 1
            pool.append(mine)
            if mine != theirs:
                pending[slot].append((mine, theirs))
            counts["picks"] += 1
    score, how = deck_rating(app, app.cards(pool))
    counts[f"decks: {how}"] += 1
    return {
        "score": round(score, 4),
        "win": round(win_rate(score, app.scorer), 4),
        "agree": agree,
        "decided": decided,
        "wheel_swaps": swaps_fired,
        "deck": how,
    }


def deck_rating(app, pool):
    """(score, how) of the first deck the app's Suggest Deck offers for this pool.

    Suggest Deck needs 15 spells; a pool short of them falls back to the best
    quick build, whose score charges for the missing spells."""
    decks = app.suggest(pool)
    if decks:
        return next(iter(decks.values()))["rating"], "suggest deck"
    return app.deck_score(pool), "quick build (no suggested deck)"

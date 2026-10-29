"""
tests/test_deck_builder.py
High-impact test targeting the V4 Deck Suggester and Holistic Scoring engine.
"""

import pytest
from unittest.mock import MagicMock
from src.card_logic import suggest_deck, calculate_dynamic_mana_base, count_fixing
from src.configuration import Configuration


@pytest.fixture
def mock_metrics():
    metrics = MagicMock()
    # Mocking the global average to 55.0% and Standard Deviation to 3.0
    metrics.get_metrics.return_value = (55.0, 3.0)
    return metrics


@pytest.fixture
def sample_pool():
    pool = []
    # 1. Add 15 solid On-Color (Green/Red) Spells
    for i in range(15):
        pool.append(
            {
                "name": f"Gruul Beater {i}",
                "types": ["Creature"],
                "colors": ["R", "G"],
                "cmc": 4,
                "mana_cost": "{2}{R}{G}",
                "deck_colors": {"All Decks": {"gihwr": 59.0}},
            }
        )
    # 2. Add 1 Off-Color Elite Bomb (Blue) for the Splash builder to find
    pool.append(
        {
            "name": "Dream Trawler",
            "types": ["Creature"],
            "colors": ["U"],
            "cmc": 6,
            "mana_cost": "{4}{U}{U}",
            "deck_colors": {"All Decks": {"gihwr": 65.0}},  # Very high win rate
        }
    )
    # 3. Add 15 low-CMC Aggro cards for the Tempo builder
    for i in range(15):
        pool.append(
            {
                "name": f"Goblin {i}",
                "types": ["Creature"],
                "colors": ["R"],
                "cmc": 1,
                "mana_cost": "{R}",
                "deck_colors": {"All Decks": {"gihwr": 56.0}},
            }
        )
    # 4. Add Fixing to satisfy the Alien Gold/Splash protection
    for i in range(3):
        pool.append(
            {
                "name": f"Evolving Wilds {i}",
                "types": ["Land"],
                "colors": [],
                "text": "search your library for a basic land",
                "deck_colors": {"All Decks": {"gihwr": 55.0}},
            }
        )
    return pool


def test_full_deck_suggestion_pipeline(sample_pool, mock_metrics):
    """
    Passes a simulated draft pool into the engine to trigger the creation of
    Consistency, Greedy, and Tempo deck variants.
    """
    config = Configuration()

    # Run the massive function
    results = suggest_deck(sample_pool, mock_metrics, config, event_type="PremierDraft")

    # Assertions
    assert len(results) > 0, "Deck builder failed to generate any archetypes."

    labels = list(results.keys())

    # Ensure it generated different variants
    assert any("Safe Core" in label for label in labels) or any(
        "Consistent" in label for label in labels
    ), "Failed to build Safe Core/Consistency variant"

    assert any("Safe Tempo" in label for label in labels) or any(
        "Tempo" in label for label in labels
    ), "Failed to build Safe Tempo/Tempo variant"

    assert any("Splash" in label for label in labels), "Failed to build Splash variant"


def test_dynamic_mana_base_math():
    """Verify the proportional land allocation guarantees minimums."""
    # Simulate a deck heavily skewed to Red, with a light Green splash
    spells = [{"mana_cost": "{R}"} for _ in range(15)] + [
        {"mana_cost": "{G}"} for _ in range(2)
    ]

    lands = calculate_dynamic_mana_base(spells, [], ["R", "G"], forced_count=17)

    # Count the generated basic lands
    forests = sum(1 for c in lands if c["name"] == "Forest")
    mountains = sum(1 for c in lands if c["name"] == "Mountain")

    assert len(lands) == 17
    assert forests >= 3, "Light splash should have a hard floor of 3 sources"
    assert mountains >= 6, "Primary color should have a hard floor of 6 sources"


def test_hybrid_mana_does_not_force_unneeded_lands():
    spells = [{"mana_cost": "{U}"} for _ in range(15)] + [
        {"mana_cost": "{W/U}"} for _ in range(2)
    ]
    lands = calculate_dynamic_mana_base(spells, [], ["U", "W"], forced_count=17)

    plains = sum(1 for c in lands if c["name"] == "Plains")
    islands = sum(1 for c in lands if c["name"] == "Island")

    assert plains == 0
    assert islands == 17


def test_proportional_mana_base_fixes_starvation():
    """Verify that a 3-color pool distributes lands using Frank Karsten targets and caps splash basics."""
    spells = (
        [{"mana_cost": "{U}"} for _ in range(8)]
        + [{"mana_cost": "{B}"} for _ in range(3)]
        + [{"mana_cost": "{G}"} for _ in range(7)]
    )

    lands = calculate_dynamic_mana_base(spells, [], ["U", "B", "G"], forced_count=17)

    islands = sum(1 for c in lands if c["name"] == "Island")
    swamps = sum(1 for c in lands if c["name"] == "Swamp")
    forests = sum(1 for c in lands if c["name"] == "Forest")

    assert islands == 8
    assert swamps == 2
    assert forests == 7


def test_mana_source_analyzer():
    """Verify the fixing counter correctly identifies fetch lands and duals."""
    pool = [
        {"name": "Forest", "types": ["Land", "Basic"]},  # Should be ignored
        {"name": "Jungle Hollow", "types": ["Land"], "colors": ["B", "G"]},  # Dual
        {
            "name": "Unknown Shores",
            "types": ["Land"],
            "text": "add one mana of any color",
        },  # Any
    ]

    fixing = count_fixing(pool)

    assert fixing["G"] == 2
    assert fixing["B"] == 2
    assert fixing["R"] == 1


def _variant(label, rating, colors, breakdown="", identity_colors=None):
    return (
        label,
        {
            "rating": rating,
            "colors": colors,
            "identity_colors": (
                identity_colors if identity_colors is not None else colors
            ),
            "breakdown": breakdown,
            "deck_cards": [],
        },
    )


def test_safe_deck_prefers_best_two_color():
    from src.advisor.deck_builder import select_safe_deck_index

    final_list = [
        _variant("BG Good Stuff", 83.0, ["G", "B", "U", "W", "R"]),
        _variant("UG Consistent", 65.0, ["G", "U"], breakdown="Solid"),
    ]
    assert select_safe_deck_index(final_list) == 1


def test_safe_deck_uses_identity_colors_ignoring_incidental_splash():
    """A deck labeled 3-color only because one gold card adds a single off-color
    pip (identity_colors == 2) still counts as the safe 2-color option."""
    from src.advisor.deck_builder import select_safe_deck_index

    final_list = [
        _variant(
            "BG Good Stuff",
            83.0,
            ["G", "B", "U", "W", "R"],
            identity_colors=["G", "B", "U"],
        ),
        _variant(
            "BG Splash W",
            79.0,
            ["G", "B", "W"],
            breakdown="Solid",
            identity_colors=["G", "B"],
        ),
    ]
    assert select_safe_deck_index(final_list) == 1


def test_safe_deck_prefers_complete_over_incomplete():
    """A complete 2-color deck beats a higher-rated but incomplete one."""
    from src.advisor.deck_builder import select_safe_deck_index

    final_list = [
        _variant("Soup", 83.0, ["G", "B", "U"]),
        _variant(
            "GU Incomplete", 50.0, ["G", "U"], breakdown="Incomplete Deck (-20.0)"
        ),
        _variant("GB Complete", 45.0, ["G", "B"], breakdown="Solid"),
    ]
    assert select_safe_deck_index(final_list) == 2


def test_safe_deck_surfaces_incomplete_two_color_when_only_option():
    """User always wants at least one <=2-color deck: an incomplete, weak, or
    far-behind 2-color deck is still surfaced when it's the only non-soupy option."""
    from src.advisor.deck_builder import select_safe_deck_index

    final_list = [
        _variant("BG Good Stuff", 83.0, ["G", "B", "U", "W", "R"]),
        _variant("UG Splash W", 82.0, ["G", "U", "W"]),
        _variant(
            "G Splash W",
            14.0,
            ["G", "W"],
            breakdown="Incomplete Deck (-20.0) | Flood Risk (-50.7)",
            identity_colors=["G"],
        ),
    ]
    assert select_safe_deck_index(final_list) == 2


def test_safe_deck_tiebreak_prefers_tighter_mana():
    """Two near-equal 2-color-identity decks: prefer the one with fewer actual
    colors (fewer incidental splashes) so 'Safe' has the tightest mana."""
    from src.advisor.deck_builder import select_safe_deck_index

    final_list = [
        _variant(
            "BG Splash WU",
            82.0,
            ["G", "B", "W", "U"],
            breakdown="Solid",
            identity_colors=["G", "B"],
        ),
        _variant(
            "UG Splash W",
            82.0,
            ["G", "U", "W"],
            breakdown="Solid",
            identity_colors=["G", "U"],
        ),
    ]
    # Same rounded rating; UG has fewer displayed colors -> tighter -> chosen.
    assert select_safe_deck_index(final_list) == 1


def test_safe_deck_none_when_all_soupy():
    """Only returns -1 when the pool genuinely can't form any <=2-color deck."""
    from src.advisor.deck_builder import select_safe_deck_index

    final_list = [
        _variant("Soup A", 83.0, ["G", "B", "U"]),
        _variant("Soup B", 80.0, ["W", "U", "R"]),
    ]
    assert select_safe_deck_index(final_list) == -1


def _greedy_pool(main_g, main_b, splash_u):
    """Pool with castable GB main spells, strong mono-U splash candidates, and
    one GU dual so the splash is mechanically enabled."""
    pool = [
        {
            "name": f"G Bear {i}",
            "types": ["Creature"],
            "colors": ["G"],
            "cmc": 2,
            "mana_cost": "{1}{G}",
            "deck_colors": {"All Decks": {"gihwr": 56.0}},
        }
        for i in range(main_g)
    ]
    pool += [
        {
            "name": f"B Bruiser {i}",
            "types": ["Creature"],
            "colors": ["B"],
            "cmc": 3,
            "mana_cost": "{2}{B}",
            "deck_colors": {"All Decks": {"gihwr": 56.0}},
        }
        for i in range(main_b)
    ]
    pool += [
        {
            "name": f"U Bomb {i}",
            "types": ["Creature"],
            "colors": ["U"],
            "cmc": 3,
            "mana_cost": "{2}{U}",
            "deck_colors": {"All Decks": {"gihwr": 62.0}},
        }
        for i in range(splash_u)
    ]
    pool.append(
        {
            "name": "GU Dual",
            "types": ["Land"],
            "colors": ["G", "U"],
            "deck_colors": {"All Decks": {"gihwr": 54.0}},
        }
    )
    return pool


def test_greedy_splash_is_capped(mock_metrics):
    """Regression: with thin main colors the greedy builder filled the deck
    with every splash candidate (6 'splash' cards on 2 sources)."""
    from src.card_logic import build_variant_greedy

    pool = _greedy_pool(main_g=9, main_b=9, splash_u=6)
    deck, splash_col = build_variant_greedy(pool, ["B", "G"], mock_metrics)

    assert deck is not None
    assert splash_col == "U"
    u_spells = sum(
        c.get("count", 1)
        for c in deck
        if c.get("colors") == ["U"] and "Land" not in c.get("types", [])
    )
    assert u_spells <= 2, f"Splash not capped: {u_spells} blue spells"


def test_greedy_skips_unsupported_pair_instead_of_over_splashing(mock_metrics):
    """If the main colors can't reach ~20 spells even with a capped splash,
    the pair isn't a real deck — skip it rather than over-splash."""
    from src.card_logic import build_variant_greedy

    pool = _greedy_pool(main_g=7, main_b=7, splash_u=6)
    deck, splash_col = build_variant_greedy(pool, ["B", "G"], mock_metrics)

    assert deck is None


# --- B3a/B3b: greedy fixing count and 23rd-slot splash swap ---


def _wb_spells(n):
    cards = []
    for i in range(n):
        cards.append(
            {
                "name": f"WB Spell {i}",
                "colors": ["W", "B"],
                "types": ["Creature"],
                "cmc": 3,
                "mana_cost": "{1}{W}{B}",
                "deck_colors": {"All Decks": {"gihwr": 58.0}, "WB": {"gihwr": 59.0}},
            }
        )
    return cards


def _duals(a, b, n):
    return [
        {
            "name": f"Dual {a}{b} {i}",
            "colors": [a, b],
            "types": ["Land"],
            "deck_colors": {"All Decks": {"gihwr": 55.0}},
        }
        for i in range(n)
    ]


def _off_color_double_pip(global_wr=65.0):
    return {
        "name": "GG Bomb",
        "colors": ["G"],
        "types": ["Creature"],
        "cmc": 6,
        "mana_cost": "{4}{G}{G}",
        "deck_colors": {"All Decks": {"gihwr": global_wr}},
    }


def test_double_pip_splash_gate_counts_fixing_once(mock_metrics):
    """Two real G-fixing sources must not pass a >= 3 gate: the old code
    recomputed count_fixing per card and added it to itself, doubling it."""
    from src.card_logic import build_variant_greedy

    pool = _wb_spells(20) + _duals("W", "G", 2) + [_off_color_double_pip()]
    deck, splash = build_variant_greedy(pool, ["W", "B"], mock_metrics)

    assert splash == ""
    assert deck is None or not any(c["name"] == "GG Bomb" for c in deck)


def test_splash_must_beat_the_cut_spell_on_the_shared_scale(mock_metrics):
    """Scale reversal: the splash rates higher on the All-Decks-only scale the
    candidate pass uses (62 global vs the 23rd spell's 55 global), but the
    23rd spell is pair-proven (WB blend 65.0) — the unconditional swap used to
    cut it anyway."""
    from src.card_logic import build_variant_greedy

    pool = [
        {
            "name": f"WB Filler {i}",
            "colors": ["W", "B"],
            "types": ["Creature"],
            "cmc": 3,
            "mana_cost": "{1}{W}{B}",
            "deck_colors": {"All Decks": {"gihwr": 64.0}},
        }
        for i in range(22)
    ]
    # Lowest-rated on the deck's own scale (blend 62.3 under the 64.0 fillers)
    # but far from a free cut for a 61.5 global splash.
    pool.append(
        {
            "name": "WB Diluted Pair",
            "colors": ["W", "B"],
            "types": ["Creature"],
            "cmc": 3,
            "mana_cost": "{1}{W}{B}",
            "deck_colors": {"All Decks": {"gihwr": 62.0}, "WB": {"gihwr": 63.0}},
        }
    )
    pool += _duals("W", "G", 3) + [_off_color_double_pip(global_wr=61.5)]

    deck, splash = build_variant_greedy(pool, ["W", "B"], mock_metrics)

    assert splash == ""
    assert any(c["name"] == "WB Diluted Pair" for c in deck)
    assert not any(c["name"] == "GG Bomb" for c in deck)


def test_deserving_splash_still_swaps_in(mock_metrics):
    """Preservation: a splash that beats the 23rd spell even on the deck's own
    scale still enters the deck."""
    from src.card_logic import build_variant_greedy

    pool = _wb_spells(23) + _duals("W", "G", 3) + [_off_color_double_pip(global_wr=70.0)]

    deck, splash = build_variant_greedy(pool, ["W", "B"], mock_metrics)

    assert splash == "G"
    assert any(c["name"] == "GG Bomb" for c in deck)


# --- B4: decks are scored under their color identity, everywhere ---


def _gb_pool_with_stray_w_pip():
    pool = []
    for i in range(21):
        pool.append(
            {
                "name": f"GB Spell {i}",
                "colors": ["G", "B"],
                "types": ["Creature"],
                "cmc": 3,
                "mana_cost": "{1}{G}{B}",
                "deck_colors": {"All Decks": {"gihwr": 58.0}, "GB": {"gihwr": 60.0}},
            }
        )
    pool.append(
        {
            "name": "Gold Stray W Pip",
            "colors": ["G", "B", "W"],
            "types": ["Creature"],
            "cmc": 3,
            "mana_cost": "{1}{G}{B}{W}",
            "deck_colors": {"All Decks": {"gihwr": 59.0}},
        }
    )
    pool += [
        {
            "name": f"Dual GW {i}",
            "colors": ["G", "W"],
            "types": ["Land"],
            "deck_colors": {"All Decks": {"gihwr": 55.0}},
        }
        for i in range(2)
    ]
    return pool


def test_suggester_scores_stray_pip_deck_under_identity(mock_metrics):
    """A Golgari deck with one gold card carrying a single white pip is still
    2-color: no Greedy Mana Strain penalty, identity == GB (parent passed the
    raw 3-color active list to the holistic scorer)."""
    from src.card_logic import suggest_deck
    from src.configuration import Configuration

    pool = _gb_pool_with_stray_w_pip()
    variants = suggest_deck(pool, mock_metrics, Configuration(), event_type="PremierDraft")
    stray = [
        (label, vd)
        for label, vd in (variants or {}).items()
        if any(c.get("name") == "Gold Stray W Pip" for c in vd.get("deck_cards", []))
    ]
    assert stray, "the gold card must land in some variant"
    for label, vd in stray:
        assert "Greedy Mana Strain" not in str(vd.get("breakdown", ""))
        assert set(vd.get("identity_colors", [])) == {"G", "B"}


def test_lookahead_scores_stray_pip_deck_under_identity(mock_metrics):
    """The engine's greedy lookahead branch must score the same deck under the
    same identity the suggester uses — captured at the calculate_holistic_score
    call site."""
    from unittest.mock import patch
    from src.card_logic import calculate_holistic_score
    from src.advisor.engine import DraftAdvisor

    pool = _gb_pool_with_stray_w_pip()

    captured = []
    real = calculate_holistic_score

    def spy(deck, colors, pool_size, metrics):
        captured.append((tuple(sorted(colors)), any(c.get("name") == "Gold Stray W Pip" for c in deck)))
        return real(deck, colors, pool_size, metrics)

    advisor = DraftAdvisor(mock_metrics, pool)
    # No color options: only the soup branch runs, and soup is the variant that
    # carries the multi-color gold card.
    with patch("src.card_logic.calculate_holistic_score", side_effect=spy):
        advisor._get_fast_best_deck_score(pool, [], pool_size=len(pool))

    stray_calls = [colors for colors, has_stray in captured if has_stray]
    assert stray_calls, "the soup deck must contain and score the gold card"
    assert all(set(colors) == {"G", "B"} for colors in stray_calls)


# --- B11: variant diversity is measured over spells, not the 40-card deck ---


def _div_variant(label, rating, spells, lands):
    return (
        label,
        {
            "rating": rating,
            "deck_cards": spells + lands,
            "label_prefix": label,
        },
    )


def test_same_spells_different_basics_is_one_deck():
    """Two variants with identical 23 spells and a different basic split are
    duplicates: the second must be dropped (the parent compared all 40 cards,
    so a 3+-basic difference kept the same deck twice)."""
    from src.advisor.deck_builder import _diversity_filter

    spells = [
        {"name": f"Spell {i}", "types": ["Creature"], "count": 1, "colors": ["W"]}
        for i in range(23)
    ]
    lands_a = [{"name": "Plains", "types": ["Land"], "count": 9, "colors": []},
               {"name": "Island", "types": ["Land"], "count": 8, "colors": []}]
    lands_b = [{"name": "Plains", "types": ["Land"], "count": 12, "colors": []},
               {"name": "Island", "types": ["Land"], "count": 5, "colors": []}]

    final_list = [
        _div_variant("WB Alpha", 90.0, spells, lands_a),
        _div_variant("WB Beta", 88.0, spells, lands_b),   # same 23 spells, split differs
        _div_variant("WB Gamma", 85.0, spells[:14] + [
            {"name": f"Other {i}", "types": ["Creature"], "count": 1, "colors": ["W"]}
            for i in range(9)
        ], lands_a),
    ]
    kept = _diversity_filter(final_list)
    kept_labels = [label for label, _ in kept]
    assert "WB Alpha" in kept_labels
    assert "WB Beta" not in kept_labels
    assert "WB Gamma" in kept_labels  # 9 different spells: a genuinely different deck


# --- B15: internal builder failures surface as errors, not empty results ---


def test_internal_builder_error_raises_instead_of_empty_dict(
    mock_metrics, sample_pool
):
    """A crash inside the builders must reach the UI worker's error branch —
    the old blanket except converted it into the 'not enough playables'
    empty result."""
    from unittest.mock import patch

    import pytest as _pytest

    from src.card_logic import suggest_deck
    from src.configuration import Configuration

    boom = RuntimeError("boom: injected builder failure")
    with (
        patch("src.advisor.deck_builder.build_variant_consistency", side_effect=boom),
        patch("src.advisor.deck_builder.build_variant_curve", side_effect=boom),
        patch("src.advisor.deck_builder.build_variant_greedy", side_effect=boom),
        patch("src.card_logic.build_variant_consistency", side_effect=boom),
        patch("src.card_logic.build_variant_curve", side_effect=boom),
        patch("src.card_logic.build_variant_greedy", side_effect=boom),
    ):
        with _pytest.raises(RuntimeError):
            suggest_deck(
                sample_pool, mock_metrics, Configuration(), event_type="PremierDraft"
            )


# --- Cycle 2 item 2b: one rescaled MC objective, deterministic seeds ---


def test_hinge_cliffs_replaced_by_continuous_mana_term(mock_metrics, sample_pool):
    """A deck with color_screw_t3 = 11 used to eat a cliff penalty; the mana
    term now prices it continuously (breakdown carries 'Mana (+x)', never
    'Color Screw')."""
    from unittest.mock import patch

    from src.card_logic import suggest_deck
    from src.configuration import Configuration
    from src.advisor import deck_builder

    fake_stats = {
        "mulligans": 5.0, "screw_t3": 10.0, "screw_t4": 10.0, "flood_t5": 10.0,
        "cast_t2": 80.0, "cast_t3": 70.0, "cast_t4": 60.0, "curve_out": 50.0,
        "removal_t4": 0.0, "color_screw_t3": 11.0, "avg_hand_size": 6.8,
    }
    with patch.object(deck_builder, "simulate_deck", return_value=fake_stats):
        variants = suggest_deck(
            sample_pool, mock_metrics, Configuration(), event_type="PremierDraft"
        )
    assert variants
    joined = " | ".join(str(vd.get("breakdown", "")) for vd in variants.values())
    assert "Color Screw" not in joined
    assert "Mana (+" in joined


def test_suggest_deck_is_deterministic_run_to_run(mock_metrics, sample_pool):
    """Per-deck CRC32 seeds make the suggester's MC term reproducible across
    runs (cache cleared between the two invocations)."""
    from src.card_logic import suggest_deck
    from src.configuration import Configuration
    from src.advisor import deck_builder

    deck_builder.GLOBAL_DECK_CACHE.clear()
    first = suggest_deck(
        sample_pool, mock_metrics, Configuration(), event_type="PremierDraft"
    )
    deck_builder.GLOBAL_DECK_CACHE.clear()
    second = suggest_deck(
        sample_pool, mock_metrics, Configuration(), event_type="PremierDraft"
    )
    ratings_a = {k: round(v["rating"], 6) for k, v in first.items()}
    ratings_b = {k: round(v["rating"], 6) for k, v in second.items()}
    assert ratings_a == ratings_b


def test_mc_anchor_card_quality_dominates(mock_metrics):
    """The rescaled mana term cannot outweigh a >=1-sigma difference in
    average card quality: two otherwise identical pools whose spells differ
    by +4.0 WR (~1 sigma) must rank ~12 holistic points apart, far beyond the
    mana term's realistic swing (<= ~6)."""
    from src.card_logic import suggest_deck
    from src.configuration import Configuration

    def pool(gihwr):
        cards = []
        for i in range(24):
            cards.append(
                {
                    "name": f"WB Anchor {i}",
                    "colors": ["W", "B"],
                    "types": ["Creature"],
                    "cmc": 3,
                    "mana_cost": "{1}{W}{B}",
                    "deck_colors": {"All Decks": {"gihwr": gihwr}},
                }
            )
        cards += [
            {"name": f"Dual WB {i}", "colors": ["W", "B"], "types": ["Land"],
             "deck_colors": {"All Decks": {"gihwr": 55.0}}}
            for i in range(4)
        ]
        return cards

    from src.advisor import deck_builder

    hi = suggest_deck(pool(58.0), mock_metrics, Configuration(), event_type="PremierDraft")
    deck_builder.GLOBAL_DECK_CACHE.clear()  # pool_sig is name-based: bypass it
    lo = suggest_deck(pool(54.0), mock_metrics, Configuration(), event_type="PremierDraft")
    best_hi = max(v["rating"] for v in hi.values())
    best_lo = max(v["rating"] for v in lo.values())
    assert best_hi > best_lo + 6.0


# --- Cycle 2 item 2c: cache identity ---


def test_same_names_different_stats_never_share_cache(mock_metrics):
    """Two pools with identical name:count signatures but different win rates
    must not share variants: the cache key is stats-sensitive."""
    from src.card_logic import suggest_deck
    from src.configuration import Configuration
    from src.advisor import deck_builder

    def pool(gihwr):
        cards = []
        for i in range(24):
            cards.append(
                {
                    "name": f"WB Cache {i}",
                    "colors": ["W", "B"],
                    "types": ["Creature"],
                    "cmc": 3,
                    "mana_cost": "{1}{W}{B}",
                    "deck_colors": {"All Decks": {"gihwr": gihwr}},
                }
            )
        cards += [
            {"name": f"Dual WBC {i}", "colors": ["W", "B"], "types": ["Land"],
             "deck_colors": {"All Decks": {"gihwr": 55.0}}}
            for i in range(4)
        ]
        return cards

    hi = suggest_deck(pool(58.0), mock_metrics, Configuration(), event_type="PremierDraft")
    lo = suggest_deck(pool(50.0), mock_metrics, Configuration(), event_type="PremierDraft")
    assert max(v["rating"] for v in hi.values()) > max(v["rating"] for v in lo.values())


# --- Cycle 2 item 4: finalist mana base, exact-40 gated ---


def test_finalist_wrapper_rejects_invalid_decks(mock_metrics, sample_pool):
    """The wrapper fails loudly where mana_base.brute_force_mana_base silently
    returns its first permutation ([] for empty input)."""
    from src.advisor.deck_builder import _finalist_mana_base

    forty_one = [{"name": f"S{i}", "types": ["Creature"], "count": 1,
                  "colors": ["U"], "deck_colors": {"All Decks": {"gihwr": 55.0}}}
                 for i in range(41)]
    with pytest.raises(ValueError, match="40"):
        _finalist_mana_base(forty_one, sample_pool, ["U"], mock_metrics)

    cheater = [
        {"name": "Only Copy", "types": ["Creature"], "count": 1, "colors": ["U"],
         "deck_colors": {"All Decks": {"gihwr": 55.0}}}
    ] * 40
    cheater = [dict(c, name=f"Only Copy {i}") for i, c in enumerate(cheater)]
    pool_one = [{"name": "Only Copy 0", "count": 1, "types": ["Creature"]}]
    four = [dict(cheater[0], count=4)] + cheater[1:37]
    with pytest.raises(ValueError, match="copies"):
        _finalist_mana_base(four, pool_one, ["U"], mock_metrics)


def test_brute_force_characterization_keeps_deck_legal():
    """Non-mocked characterization of the live optimizer Auto-Lands uses: on a
    U-heavy 24-spell deck with a deliberately bad 16-Swamp split, the returned
    basics sum to the forced count, the deck stays exactly 40, and the split
    shifts toward Islands."""
    from src.advisor.mana_base import brute_force_mana_base

    spells = []
    for i in range(24):
        spells.append(
            {"name": f"U Spell {i}", "types": ["Creature"], "count": 1,
             "colors": ["U"], "mana_cost": "{1}{U}", "cmc": 2,
             "deck_colors": {"All Decks": {"gihwr": 55.0}}}
        )
    basics = brute_force_mana_base(spells, [], ["U", "B"], forced_count=16)
    assert basics, "optimizer must return a basic configuration"
    total = sum(c.get("count", 1) for c in basics)
    assert total == 16
    islands = sum(c.get("count", 1) for c in basics if c.get("name") == "Island")
    swamps = sum(c.get("count", 1) for c in basics if c.get("name") == "Swamp")
    assert islands + swamps == 16
    assert islands > swamps  # a 24-single-U-pip deck wants Islands first


def test_suggest_deck_finalists_stay_legal_after_rebasing(mock_metrics, sample_pool):
    """End-to-end: after the finalist mana pass every emitted deck is exactly
    40 cards with 22-24 spells, and pool legality holds for spells and
    nonbasics."""
    from src.card_logic import suggest_deck
    from src.configuration import Configuration

    variants = suggest_deck(
        sample_pool, mock_metrics, Configuration(), event_type="PremierDraft"
    )
    assert variants
    owned = {}
    for c in sample_pool:
        owned[c["name"]] = owned.get(c["name"], 0) + c.get("count", 1)
    for label, vd in variants.items():
        deck = vd["deck_cards"]
        assert sum(c.get("count", 1) for c in deck) == 40, label
        spells = [c for c in deck if "Land" not in c.get("types", [])]
        assert 22 <= sum(c.get("count", 1) for c in spells) <= 24, label
        for c in spells:
            if c.get("name") in owned:  # synthetic names not in pool are fixture-only
                assert c.get("count", 1) <= owned[c["name"]], label

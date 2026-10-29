"""
src/advisor/deck_scorer.py
Evaluates pool strength, calculates holistic power scores, and identifies top lanes.
"""

from src import constants
from src.card_utils import get_functional_cmc
from src.advisor.mana_base import ManaSourceAnalyzer
from src.utils import normalize_color_string
from src.sealed_logic import HeuristicEvaluator

# Named projection concepts (distinct from the advisor engine's pick-index
# TOTAL_PICKS=45 and card-total TOTAL_CARDS_DRAFTED=45 on purpose): this scorer
# projects a partial pool toward a full draft's spell target. Pool sizes 43-45
# are behaviorally identical under this projection, so 42 vs 45 is a documented
# consistency choice, not a bug to unify.
SPELL_TARGET_PROJECTION_BASE = 42
TARGET_SPELL_COUNT = 23

# Bayesian shrinkage toward the set mean (global) / global + pair-offset
# (archetype), in game counts (ever_drawn_game_count). Value fitted by
# empirical Bayes (Beta-binomial method of moments on between-card variance,
# net of binomial noise) across FRA/DFT/VOW/Cube Premier tables:
# per-set k_hat 287..504, pooled median ~350 (evidence/nextgen/
# ADR-architecture.md + tools-data/k_fit_results.json). Per-set and
# per-statistic refinement belongs to the tier-1 calibration pass.
SHRINKAGE_K = 350

# --- Rules-level card prior (what the card DOES -> expected z of GIH WR) ---
# Trained offline on 34 sets of 17Lands data with Scryfall rules features;
# replaces the set-mean constant as the shrinkage prior. Falls back to the
# set mean on ANY load/gate failure (atomic, logged once).
import json as _json
import os as _os

_PRIOR_MODELS = {}  # lazy: {"full": (predict_fn, manifest), "nr": (predict_fn, manifest)}
_PRIOR_LOAD_TRIED = False

# v2: per-card prior z precomputed offline by the evaluated v5 level-1 model
# (spearman 0.665 FRA / 0.615 DFT on sets frozen out of training). The app
# only looks names up — no model code runs here, so predictions are exactly
# the evaluated ones. Cards outside the table keep the v1 path below, and
# everything falls back to the set mean.
_PRIOR_Z_TABLE = {}
_PRIOR_Z_TABLE_TRIED = False
_PRIOR_Z_CLAMPS = (-2.0, 2.0)  # widened at load from the manifest (floors reach z 5.0)


def _norm_card_name(s):
    import re as _re

    t = (s or "").lower().replace("’", "'")
    # split/aftermath separators arrive in several spellings (" // ", "//",
    # " /// "): normalize to one canonical spaced form so lookups match
    t = t.replace(" /// ", " // ").replace("///", " // ")
    t = _re.sub(r"\s*//\s*", " // ", t)
    return _re.sub(r"\s+", " ", t).strip()


def _load_prior_z_table():
    global _PRIOR_Z_TABLE_TRIED
    if _PRIOR_Z_TABLE_TRIED:
        return
    _PRIOR_Z_TABLE_TRIED = True
    try:
        import numpy as _np

        base = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.dirname(
            _os.path.abspath(__file__)))), "assets", "models")
        # manifest FIRST: a missing/malformed manifest must abort the whole
        # table load (otherwise floors would be silently clamped to +-2)
        mf = _json.load(open(_os.path.join(base,
            "card_prior_z_table_manifest.json")))
        cl = mf.get("z_clamps")
        if not (isinstance(cl, list) and len(cl) == 2
                and float(cl[0]) < 0 < float(cl[1])):
            raise ValueError("bad z_clamps in manifest")
        data = _np.load(_os.path.join(base, "card_prior_z_table.npz"),
                        allow_pickle=False)
        n_rows = len(data["names"])
        if len(data["z"]) != n_rows or n_rows != int(mf.get("n_cards", -1)):
            raise ValueError("prior table rows disagree with the manifest")
        table = {_norm_card_name(str(nm)): float(zv)
                 for nm, zv in zip(data["names"], data["z"])}
        # face -> full-name index for split/DFC cards ("ice" -> "fire // ice");
        # exact names always win (a card genuinely named "Fire" keeps its z).
        # Repeated-name rows ("A // A" MDFC doubles in the export) are
        # skipped: their degenerate alias shadows the card's real canonical
        # row and poisons front-face lookups.
        for nm in list(table):
            if " // " in nm:
                parts = [p for p in nm.split(" // ") if p]
                if len(parts) > 1 and len(set(parts)) == 1:
                    continue
                for part in parts:
                    table.setdefault(part, table[nm])
        global _PRIOR_Z_CLAMPS
        _PRIOR_Z_CLAMPS = (float(cl[0]), float(cl[1]))
        _PRIOR_Z_TABLE.update(table)   # published only after everything parsed
    except Exception:
        pass  # atomic fallback: v1 path, then the set mean


def _table_prior_z(card):
    """Table z for a card dict, or None. Exact (normalized) name first; the
    loader's face index resolves single-face names of split cards."""
    if not _PRIOR_Z_TABLE:
        return None
    name = card.get("name") if isinstance(card, dict) else None
    if not name:
        return None
    return _PRIOR_Z_TABLE.get(_norm_card_name(str(name)))


def _load_card_prior():
    global _PRIOR_LOAD_TRIED
    if _PRIOR_LOAD_TRIED:
        return
    _PRIOR_LOAD_TRIED = True
    base = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.dirname(
        _os.path.abspath(__file__)))), "assets", "models")
    for kind, fname in (("full", "card_prior.npz"), ("nr", "card_prior_nr.npz")):
        try:
            import numpy as _np
            data = _np.load(_os.path.join(base, fname), allow_pickle=False)
            feat_names = list(data["feature_names"])
            dump = _json.loads(str(data["model_dump"][0])
                               if "model_dump" in data
                               else str(data["thresholds"][0]))
            manifest = _json.load(open(_os.path.join(base,
                fname.replace(".npz", "").replace("card_prior", "card_prior")
                + "_manifest.json")))
            _PRIOR_MODELS[kind] = (_make_predictor(dump, feat_names), manifest, feat_names)
        except Exception:
            pass  # atomic fallback: the set-mean prior stays


def _make_predictor(dump, feat_names):
    """Pure-Python tree-walk predictor for the LightGBM dump (v1: prior lookup
    per card is called rarely; numpy optimization deferred to the exporter v2)."""
    trees = dump["tree_info"]

    def predict_one(features):
        total = 0.0
        for tree in trees:
            node = tree["tree_structure"]
            while "leaf_value" not in node:
                f = node["split_feature"]
                val = features.get(feat_names[f], 0.0)
                try:
                    thr = float(node["threshold"])
                except (TypeError, ValueError):
                    thr = 0.0
                # default_left for missing; we have no missing values
                node = node["left_child"] if val <= thr else node["right_child"]
            total += node["leaf_value"]
        return total
    return predict_one


def _feature_prior_z(card, use_nr=False):
    """Predicted z of the card's GIH WR from rules features; 0.0 (set mean) on
    any failure. The v2 table (exact offline predictions by the evaluated v5
    model) wins when it has the card; otherwise the v1 live-extractor path
    runs below."""
    _load_prior_z_table()
    tz = _table_prior_z(card)
    if tz is not None:
        lo, hi = _PRIOR_Z_CLAMPS
        return max(lo, min(hi, tz))
    _load_card_prior()
    kind = "nr" if use_nr else "full"
    if kind not in _PRIOR_MODELS:
        return 0.0
    predict, manifest, feat_names = _PRIOR_MODELS[kind]
    try:
        # minimal feature extraction from the card dict the app already carries
        # (cost, type, body, oracle keywords); full extractor features are in
        # the offline pipeline — for v1 the prior uses the app's own fields
        feats = _extract_live_features(card)
        z = predict(feats)
        lo, hi = manifest.get("z_clamps", [-2.0, 2.0])
        return max(lo, min(hi, z))
    except Exception:
        return 0.0


def _extract_live_features(card):
    """Minimal feature extraction matching the training schema, from the card
    dict the app already has. Covers the highest-signal features only; the
    rest default to 0 (which is the training median for most binary flags)."""
    import re as _re
    types = card.get("types", []) or []
    tl = " ".join(str(t) for t in types).lower()
    cost = card.get("mana_cost", "") or ""
    cmc = card.get("cmc", 0) or 0
    colors = card.get("colors", []) or []
    text = str(card.get("oracle_text", card.get("text", "")) or "").lower()
    rarity = str(card.get("rarity", "common")).lower()

    pips = {"w": 0, "u": 0, "b": 0, "r": 0, "g": 0}
    for sym in _re.findall(r"\{(.*?)\}", cost):
        for part in sym.lower().split("/"):
            if part in pips:
                pips[part] += 1

    f = {"cmc": float(cmc), "n_colors": len(set(colors)), "colorless": 1 if not colors else 0}
    for c, n in pips.items():
        f[f"pip_{c}"] = n
    f["is_creature"] = "creature" in tl
    f["is_instant"] = "instant" in tl
    f["is_sorcery"] = "sorcery" in tl
    f["is_land"] = "land" in tl.split(" ")[0:1]
    f["is_artifact"] = "artifact" in tl
    f["is_enchantment"] = "enchantment" in tl
    f["rarity_common"] = rarity == "common"
    f["rarity_uncommon"] = rarity == "uncommon"
    f["rarity_rare"] = rarity == "rare"
    f["rarity_mythic"] = rarity == "mythic"

    # body (may be absent on non-creatures)
    f["power"] = 0; f["toughness"] = 0; f["pt_sum"] = 0; f["pt_per_mana"] = 0.0
    f["power_minus_cmc"] = -float(cmc); f["toughness_minus_cmc"] = -float(cmc)
    f["toughness_ge_2"] = 0; f["toughness_ge_3"] = 0; f["toughness_ge_4"] = 0
    f["power_ge_3"] = 0; f["statline_at_curve"] = 0

    # top effect flags (oracle text regex, matching the extractor's patterns)
    # the shipped models' feature schema calls this 'draw_count' (not
    # fx_draw_count — that mismatch made every live-extracted draw feature
    # invisible to the v1 predictor, defaulting to zero)
    f["draw_count"] = min(len(_re.findall(r"draw (?:one|two|three|four|\d+)", text)), 3)
    f["fx_counter_hard"] = 1 if _re.search(r"counter target (?:spell|noncreature)", text) else 0
    f["fx_destroy_creature"] = 1 if _re.search(r"destroy target (?:creature|creature or)", text) else 0
    f["fx_exile_creature"] = 1 if _re.search(r"exile target (?:creature|permanent)", text) else 0
    f["removal_ordinal"] = 0
    if f["fx_exile_creature"]: f["removal_ordinal"] = 5
    elif f["fx_destroy_creature"]: f["removal_ordinal"] = 4
    elif _re.search(r"deals? \d+ damage to (?:any target|target creature)", text):
        f["removal_ordinal"] = 2
    f["fx_add_mana"] = 1 if _re.search(r"add \{[wubrg]\}|add one mana", text) else 0
    f["fx_token"] = 1 if "token" in text else 0
    f["fx_lifegain"] = 1 if _re.search(r"gain \d+ life|lifelink", text) else 0
    f["kw_flying"] = 1 if "flying" in text else 0
    f["kw_haste"] = 1 if "haste" in text else 0
    f["kw_trample"] = 1 if "trample" in text else 0
    f["kw_lifelink"] = 1 if "lifelink" in text else 0
    f["kw_deathtouch"] = 1 if "deathtouch" in text else 0
    f["kw_menace"] = 1 if "menace" in text else 0
    f["kw_first_strike"] = 1 if "first strike" in text else 0
    f["kw_vigilance"] = 1 if "vigilance" in text else 0
    f["kw_reach"] = 1 if "reach" in text else 0
    f["ds_upkeep_damage"] = 1 if _re.search(r"upkeep[^.]*deals? \d+ damage to you", text) else 0
    f["ds_cumulative_upkeep"] = 1 if "cumulative upkeep" in text else 0
    f["ds_etb_tapped"] = 1 if "enters the battlefield tapped" in text else 0
    f["ds_cant_block"] = 1 if "can't block" in text else 0
    f["ds_defender"] = 1 if "defender" in text else 0
    f["text_length"] = min(len(text) // 100, 12)
    return f


def shrunk_wr(raw, prior, n, k=SHRINKAGE_K):
    """n/(n+k) shrinkage of raw toward prior. n <= 0 returns raw unchanged:
    with no reliability information the caller's no-data policy applies."""
    if n <= 0:
        return raw
    return prior + (raw - prior) * (n / (n + k))


def effective_pair_key(card, colors):
    """Which pair prices a card in a 3+ color context: the card's own
    best-WUBRG pair among the deck's colors, not a positional truncation.
    Falls back to the first two colors when the card carries no pair data."""
    if len(colors) <= 2:
        return normalize_color_string("".join(colors))
    stats = card.get("deck_colors", {})
    best, best_wr = None, -1.0
    from itertools import combinations

    for a, b in combinations(sorted(colors), 2):
        key = normalize_color_string(a + b)
        wr = float(stats.get(key, {}).get("gihwr") or 0.0)
        if wr > best_wr:
            best, best_wr = key, wr
    if best is None or best_wr <= 0.0:
        return normalize_color_string("".join(sorted(colors)[:2]))
    return best


def card_wr_posteriors(card, colors, metrics=None):
    """Posterior win-rate estimates for `card` under `colors`, WR scale only —
    callers apply their own transforms. Returns a dict with raw values, the
    game counts, and the shrunk estimates. The GLOBAL posterior shrinks with
    the global game count and the ARCH posterior with the pair's count; when
    the pair has no data the arch posterior falls back to the global
    evidence instead of returning an unshrunk raw rate. Shrinkage only
    applies for n > 0 (n from `samples` / ever_drawn_game_count; absent on
    shipped fixtures, where every card therefore keeps raw-value behavior)."""
    stats = card.get("deck_colors", {})
    global_stats = stats.get("All Decks", {})
    global_wr = float(global_stats.get("gihwr") or 0.0)
    n_global = int(global_stats.get("samples", 0) or 0)
    arch_key = effective_pair_key(card, colors)
    arch_stats = stats.get(arch_key, {}) if arch_key != "All Decks" else {}
    arch_wr = float(arch_stats.get("gihwr") or 0.0) if arch_stats else global_wr
    n = int(arch_stats.get("samples", 0) or 0) if arch_stats else 0

    set_global_mean = global_wr
    offset = 0.0
    if metrics:
        try:
            g_mean, _ = metrics.get_metrics("All Decks", "gihwr")
            if g_mean:
                set_global_mean = float(g_mean)
            if arch_stats and arch_key != "All Decks":
                pair_mean, _ = metrics.get_metrics(arch_key, "gihwr")
                if pair_mean:
                    offset = float(pair_mean) - float(g_mean)
        except Exception:
            offset = 0.0

    # Rules-feature prior: what the card DOES predicts its expected z; the
    # shrinkage target becomes set_mean + feature_prior_z * set_std (in WR
    # points) instead of the bare set mean. Fallback to the set mean on any
    # failure (the prior function returns 0.0 = set mean).
    prior_z = _feature_prior_z(card)
    feature_prior_wr = set_global_mean + prior_z * 4.0  # sigma approx; per-set
    # std would need metrics.get_metrics std — use it when available
    if metrics:
        try:
            _, g_std = metrics.get_metrics("All Decks", "gihwr")
            if g_std and g_std > 0:
                feature_prior_wr = set_global_mean + prior_z * float(g_std)
        except Exception:
            pass

    return {
        "global_wr": global_wr,
        "arch_wr": arch_wr,
        "n": n,
        "n_global": n_global,
        "arch_prior": global_wr + offset,
        "shrunk_global": shrunk_wr(global_wr, feature_prior_wr, n_global),
        # no pair data: the arch posterior IS the global posterior (global
        # evidence + prior), never an unshrunk 3-game raw rate
        "shrunk_arch": shrunk_wr(arch_wr, feature_prior_wr + offset,
                                 n if n > 0 else n_global),
        "pair_offset": offset,
        "prior_z": prior_z,
    }

TIER_TO_GIHWR = {
    "A+": 68.0,
    "A ": 66.0,
    "A-": 64.0,
    "B+": 62.0,
    "B ": 60.0,
    "B-": 58.0,
    "C+": 56.0,
    "C ": 54.0,
    "C-": 52.0,
    "D+": 50.0,
    "D ": 48.0,
    "D-": 46.0,
    "F ": 40.0,
    "SB": 40.0,
    "NA": 0.0,
}


def get_card_rating(card, colors, metrics=None, tier_data=None):
    global_mean = 54.0
    set_has_data = False
    if metrics:
        mean_val, _ = metrics.get_metrics("All Decks", "gihwr")
        if mean_val > 0:
            global_mean = mean_val
            set_has_data = True

    stats = card.get("deck_colors", {})
    global_wr = float(stats.get("All Decks", {}).get("gihwr") or 0.0)

    # Dataset deck_colors keys are WUBRG-ordered ("UB", not "BU"); in a 3+
    # color context the card is priced under its own best pair.
    arch_key = effective_pair_key(card, colors)
    arch_wr = float(stats.get(arch_key, {}).get("gihwr") or 0.0)

    post = card_wr_posteriors(card, colors, metrics)
    # Each estimate gates on ITS OWN evidence count: the arch posterior on
    # the pair's n, the global posterior on the global n. A card with three
    # global games and no pair games gets the prior-weighted global value,
    # not its raw 3-game rate (adversarial T1, consumer side).
    # any real evidence (pair OR global) makes the posterior estimates the
    # honest values; raw rates only when the card truly has no data
    arch_v = post["shrunk_arch"] if (post["n"] > 0 or post["n_global"] > 0) else arch_wr
    global_v = post["shrunk_global"] if post["n_global"] > 0 else global_wr
    has_evidence = post["n"] > 0 or post["n_global"] > 0
    # Evidence gates on COUNTS: a 0%-in-one-game record still has a real
    # posterior (the prior dominates it), and throwing it away made an
    # observed card fall through to the no-data path (rating 0). The raw
    # >30 value checks remain ONLY for legacy records without counts.
    if has_evidence:
        if post["n"] > 0 or arch_wr > 0.0:
            return (arch_v * 0.7) + (global_v * 0.3)
        return global_v
    if arch_wr > 30.0 and global_wr > 30.0:
        return (arch_wr * 0.7) + (global_wr * 0.3)
    if global_wr > 30.0:
        return global_v
    if arch_wr > 30.0:
        return arch_v

    if tier_data:
        name, tier_scores = card.get("name", ""), []
        for tier_obj in tier_data.values():
            if name in tier_obj.ratings:
                grade = tier_obj.ratings[name].rating
                score = TIER_TO_GIHWR.get(grade, 0.0)
                if score > 0.0:
                    tier_scores.append(score)
        if tier_scores:
            return sum(tier_scores) / len(tier_scores)

    # No observed data of its own. Before anything else, the shipped prior
    # speaks: what the card DOES predicts its expected z (a table hit IS the
    # rating evidence — this is the cold-start path the prior exists for).
    prior_z = _table_prior_z(card) or 0.0
    if prior_z and not set_has_data:
        g_std = 4.0
        try:
            if metrics:
                _m, _s = metrics.get_metrics("All Decks", "gihwr")
                if _s and _s > 0:
                    g_std = float(_s)
        except Exception:
            pass
        return global_mean + prior_z * g_std

    # In an established format (the set already has win-rate data), a card with
    # no data of its own is one nobody drafts or plays — effectively unplayable
    # (e.g. Worlds Within Worlds). Don't invent a generous score from a metadata
    # heuristic; that fallback is only for Day 1 before any data exists.
    if set_has_data:
        return 0.0

    return HeuristicEvaluator.evaluate(card)


def identify_top_pairs(pool, metrics, tier_data=None):
    global_mean, global_std = (
        metrics.get_metrics("All Decks", "gihwr") if metrics else (54.0, 4.0)
    )
    if global_mean == 0.0:
        global_mean = 54.0
    if global_std == 0.0:
        global_std = 4.0

    playable_baseline = global_mean - (global_std * 0.5)
    raw_scores = {c: 0.0 for c in constants.CARD_COLORS}
    eligible = {c: 0 for c in constants.CARD_COLORS}

    for card in pool:
        colors = card.get(constants.DATA_FIELD_COLORS, [])
        raw_wr = float(
            card.get("deck_colors", {}).get("All Decks", {}).get("gihwr") or 0.0
        )
        wr = get_card_rating(card, ["All Decks"], metrics, tier_data)
        # Raw-WR gate, shrunk weight: shrinkage pulls small-n cards toward the
        # mean, so gating on the shrunk value would let low-sample noise cross
        # the playable baseline and steer pair selection. On a COLD set
        # (no observed data), the prior-based rating IS the gate — every
        # raw WR is zero and the raw gate would return no lanes at all,
        # collapsing every suggestion to five-color soup.
        set_has_data_for_lanes = any(
            float(c.get("deck_colors", {}).get("All Decks", {}).get("gihwr") or 0.0)
            > 30.0
            for c in pool
        )
        gate_value = raw_wr if set_has_data_for_lanes else wr
        if gate_value > playable_baseline:
            points = (wr - playable_baseline) / global_std
            for c in colors:
                # Multicolor cards credit every color they can be played in,
                # but the per-color AVERAGE (not the sum) ranks the lane, so a
                # deep run of mediocre playables cannot drown a short lane of
                # bombs — which six pairs become variants depends on this.
                raw_scores[c] += points
                eligible[c] += 1

    scores = {
        c: (raw_scores[c] / eligible[c]) if eligible[c] else 0.0
        for c in constants.CARD_COLORS
    }

    # A lane needs bodies: an average over a handful of golds is noise, and
    # ranking by it let two-card lanes displace a 24-playable lane entirely.
    # Colors below the floor cannot enter the top-4; if fewer than two real
    # lanes exist yet, depth (raw sums) decides.
    min_lane_playables = 6
    qualifying = [
        c for c in constants.CARD_COLORS if eligible[c] >= min_lane_playables
    ]
    if len(qualifying) >= 2:
        ranked = sorted(
            ((c, scores[c]) for c in qualifying), key=lambda x: x[1], reverse=True
        )
        if ranked[0][1] <= 0.0:
            return []
        top_4_colors = [c for c, _ in ranked[:4]]
        # SEALED / five-color pools: when a fifth color qualifies AND is
        # substantially deeper than a qualifying top-4 color, swap it in —
        # average quality must not sideboard a 21-playable lane while a
        # shallower color builds a two-card variant. Depth is the number
        # of eligible playables; the swap is bounded (one color, only
        # when the depth gap is at least 5 cards).
        if len(qualifying) > 4:
            excluded = [c for c in qualifying if c not in top_4_colors]
            for exc in excluded:
                shallowest = min(top_4_colors, key=lambda c: eligible[c])
                if eligible[exc] >= eligible[shallowest] + 5:
                    top_4_colors.remove(shallowest)
                    top_4_colors.append(exc)
                    break
    else:
        sorted_c = sorted(raw_scores.items(), key=lambda x: x[1], reverse=True)
        if sorted_c[0][1] <= 0.0:
            return []
        top_4_colors = [c[0] for c in sorted_c[:4]]
    from itertools import combinations

    return [list(pair) for pair in combinations(top_4_colors, 2)]


def calculate_holistic_score(deck, colors, pool_size, metrics, tier_data=None):
    if not deck:
        return 0.0, ""

    global_mean, global_std = metrics.get_metrics("All Decks", "gihwr")
    if global_mean == 0.0:
        global_mean = 54.0
    if global_std == 0.0:
        global_std = 4.0

    spells = [c for c in deck if constants.CARD_TYPE_LAND not in c.get("types", [])]
    spell_count = sum(c.get("count", 1) for c in spells)
    if spell_count == 0:
        return 0.0, ""

    # Dataset deck_colors keys are WUBRG-ordered ("UB", not "BU"). The full
    # color context flows into get_card_rating: in 3+ color decks each card
    # is priced under its OWN best pair (effective_pair_key), not under a
    # positional truncation of the deck's colors.
    arch_key = normalize_color_string(
        "".join(colors) if len(colors) <= 2 else "".join(colors[:2])
    )
    # Unrated spells (no data of their own in an established set) are charged
    # at replacement level instead of vanishing from the average: every spell
    # the deck actually plays belongs in the denominator.
    replacement_level = global_mean - (global_std * 1.5)
    ratings = []
    for c in spells:
        for _ in range(c.get("count", 1)):
            rating = get_card_rating(c, colors, metrics, tier_data=tier_data)
            ratings.append(rating if rating > 0.0 else replacement_level)

    avg_gihwr = (
        sum(ratings) / len(ratings) if ratings else global_mean - global_std
    )
    z_score = (avg_gihwr - global_mean) / global_std
    power_level = 75.0 + (z_score * 12.0)
    breakdown_notes = []

    cmcs = [get_functional_cmc(c) for c in spells for _ in range(c.get("count", 1))]
    avg_cmc = sum(cmcs) / spell_count

    land_count = sum(c.get("count", 1) for c in deck if "Land" in c.get("types", []))
    ramp_count = min(
        3,
        sum(
            c.get("count", 1)
            for c in deck
            if (
                "fixing_ramp" in c.get("tags", [])
                or "treasure" in str(c.get("oracle_text", c.get("text", ""))).lower()
                or "add {" in str(c.get("oracle_text", c.get("text", ""))).lower()
                or "adds {" in str(c.get("oracle_text", c.get("text", ""))).lower()
            )
            and "Land" not in c.get("types", [])
        ),
    )

    mana_deficit = (avg_cmc * 5.5) - (land_count + ramp_count)
    if mana_deficit > 1.5:
        power_level -= mana_deficit * 3.0
        breakdown_notes.append(f"High Curve / Needs Lands (-{mana_deficit * 3.0:.1f})")
    elif mana_deficit < -1.0 and avg_cmc < 2.8:
        power_level += 5.0
        breakdown_notes.append("Excellent Aggro Curve (+5.0)")

    if len(colors) <= 2:
        power_level += 2.5
        breakdown_notes.append("Rock-Solid Mana (+2.5)")

    supertypes = {
        "Creature",
        "Instant",
        "Sorcery",
        "Enchantment",
        "Artifact",
        "Planeswalker",
        "Land",
        "Legendary",
        "Basic",
        "Snow",
        "World",
        "Tribal",
        "Kindred",
    }
    subtypes, changeling_count = {}, 0
    for c in spells:
        text, count = (
            str(c.get("oracle_text", c.get("text", ""))).lower(),
            c.get("count", 1),
        )
        if "changeling" in text:
            changeling_count += count
        for t in c.get("types", []):
            if t not in supertypes:
                subtypes[t] = subtypes.get(t, 0) + count

    if subtypes:
        top_tribe, tribe_count = max(subtypes.items(), key=lambda x: x[1])
        total_tribe_density = tribe_count + changeling_count
        payoff_count = sum(
            c.get("count", 1)
            for c in spells
            if "chosen type" in str(c.get("oracle_text", c.get("text", ""))).lower()
            or top_tribe.lower() in str(c.get("oracle_text", c.get("text", ""))).lower()
        )

        if total_tribe_density >= 6 and payoff_count >= 2:
            bonus = (total_tribe_density * 0.5) + (payoff_count * 1.5)
            power_level += bonus
            breakdown_notes.append(f"{top_tribe} Synergy (+{bonus:.1f})")

    if len(colors) >= 3:
        domain_payoffs = sum(
            c.get("count", 1)
            for c in spells
            if "colors among" in str(c.get("oracle_text", c.get("text", ""))).lower()
            or "basic land types"
            in str(c.get("oracle_text", c.get("text", ""))).lower()
        )
        fixing_count = ManaSourceAnalyzer(deck).total_fixing_cards

        if domain_payoffs >= 2 and fixing_count >= 4:
            power_level += 6.0
            breakdown_notes.append("Supported Domain/Soup (+6.0)")
        elif fixing_count < len(colors) - 1:
            penalty = (len(colors) - 1 - fixing_count) * 6.0
            power_level -= penalty
            breakdown_notes.append(f"Greedy Mana Strain (-{penalty:.1f})")

    evasion_count = sum(
        c.get("count", 1)
        for c in spells
        if "evasion" in c.get("tags", [])
        or any(
            kw in str(c.get("oracle_text", c.get("text", ""))).lower()
            for kw in [
                "flying",
                "trample",
                "menace",
                "can't be blocked",
                "unblockable",
                "deals damage to any target",
            ]
        )
    )
    if evasion_count < 3 and avg_cmc > 2.5:
        power_level -= 5.0
        breakdown_notes.append("Lacks Evasion/Reach (-5.0)")

    expected_spells = int(
        TARGET_SPELL_COUNT
        * (min(SPELL_TARGET_PROJECTION_BASE, pool_size) / SPELL_TARGET_PROJECTION_BASE)
    )
    if spell_count < expected_spells - 1:
        penalty = ((expected_spells - 1) - spell_count) * 10.0
        power_level -= penalty
        breakdown_notes.append(f"Incomplete Deck (-{penalty:.1f})")

    return max(0.0, power_level), ", ".join(breakdown_notes)


def estimate_record(power_level, is_bo3=False):
    if is_bo3:
        if power_level < 65:
            return "0-2 / 1-2"
        if power_level < 78:
            return "2-1"
        return "3-0"
    else:
        if power_level < 60:
            return "0-3 / 1-3"
        if power_level < 70:
            return "2-3 / 3-3"
        if power_level < 80:
            return "4-3 / 5-3"
        if power_level < 88:
            return "6-3"
        return "7-x"

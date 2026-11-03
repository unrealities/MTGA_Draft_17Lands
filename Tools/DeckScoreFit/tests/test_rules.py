import io
import json
import math

import numpy as np
import pytest
import rules

WEIGHTS = {"card_quality": 12.0, "two_colors": 3.5, "missing_fixing": -2.5,
           "missing_spells": -10.0}
# Log-odds per card in the simulated data: removal past the sixth costs wins,
# heavy drops are worth their rating, fixing is worth more while short.
QUALITY = 0.4
REMOVAL_PAST_6 = -0.06
FIXING_SHORT = -0.05


def files(n=24000, sets=("AAA", "BBB", "CCC", "DDD"), seed=0, tags=True):
    rng = np.random.default_rng(seed)
    out = []
    for s, set_effect in zip(sets, np.linspace(-0.1, 0.1, len(sets))):
        rows = []
        for i in range(n // len(sets)):
            removal = int(rng.integers(0, 12)) if tags else 0
            heavy = int(rng.integers(0, 9))
            off = int(rng.integers(0, 6)) * int(rng.random() < 0.5)
            fixing = int(rng.integers(0, 7))
            creatures = int(rng.integers(9, 19))
            early = int(rng.integers(2, 12))
            short = max(0, off + 1 - fixing) if off else 0
            f = {
                "card_quality": rng.normal(),
                "two_colors": float(off == 0),
                "missing_fixing": 0.0,
                "missing_spells": 0.0,
            }
            skill = rng.choice(["0.48", "0.54", "0.60"])
            eta = set_effect + (float(skill) - 0.54) * 4 + 0.2
            eta += QUALITY * f["card_quality"]
            eta += REMOVAL_PAST_6 * max(0, removal - 6) + FIXING_SHORT * short
            games = int(rng.integers(3, 10))
            rows.append({
                "id": f"{s}{i}",
                "wins": int(rng.binomial(games, 1 / (1 + math.exp(-eta)))),
                "games": games,
                "skill": skill,
                "experience": rng.choice(["5", "50"]),
                "features": f,
                "extra": {"lands": 17.0, "creatures": 15.0, "colors": 2.0 + (off > 0)},
                "rules": {"removal": removal, "heavy": heavy, "fixing": fixing,
                          "off_color": off, "splash": int(off > 0),
                          "creatures": creatures, "early": early},
            })
        out.append({"set": s, "base_score": 75.0, "weights": WEIGHTS, "rows": rows,
                    "tags": {"removal": 40 if tags else 0, "fixing_ramp": 10}})
    return out


@pytest.fixture(scope="module")
def rd():
    return rules.RuleData(files())


def by_name(name):
    return next(r for r in rules.RULES if r.name == name)


def per_pp(rd):
    return 100 * rd.win_rate * (1 - rd.win_rate)


def test_recovers_the_simulated_effects(rd):
    everything = np.ones(len(rd.base.set), dtype=bool)
    removal = rules.estimate(rd, by_name("removal_saturation"), everything)
    assert abs(removal["pp"] - per_pp(rd) * REMOVAL_PAST_6) < 3 * removal["se"]
    heavy = rules.estimate(rd, by_name("curve_heavy"), everything)
    assert abs(heavy["pp"]) < 3 * heavy["se"]
    fixing = rules.estimate(rd, by_name("fixing_hunger"), everything)
    assert abs(fixing["pp"] - per_pp(rd) * -FIXING_SHORT) < 3 * fixing["se"]
    # In rating SDs: the effect over card quality's, times the deck's spells.
    assert removal["sd"] == pytest.approx(
        rules.SPELLS * removal["logit"] / QUALITY, rel=0.2
    )
    assert removal["se_cluster"] is not None and removal["se"] >= removal["se_model"]


def test_verdicts():
    rule = by_name("removal_saturation")  # right if negative
    assert rules.verdict(rule, {"pp": -1.0, "se": 0.1}) == "supported"
    assert rules.verdict(rule, {"pp": 1.0, "se": 0.1}) == "contradicted"
    assert rules.verdict(rule, {"pp": -0.2, "se": 0.1}) == "not established"
    assert rules.verdict(by_name("fixing_hunger"), {"pp": 1.0, "se": 0.1}) == "supported"


def test_keep_or_drop():
    z = rules.Z
    # A penalty of -1: drop if the value is surely above -0.5, keep if below.
    assert rules.keep_or_drop(-1.0, 0.0, 0.1) == "drop"
    assert rules.keep_or_drop(-1.0, -1.0, 0.1) == "keep"
    assert rules.keep_or_drop(-1.0, -0.5, 0.1) == "can't tell"
    assert rules.keep_or_drop(-1.0, -0.5 + 1.01 * z * 0.1, 0.1) == "drop"
    # A boost of +1.
    assert rules.keep_or_drop(1.0, 0.1, 0.1) == "drop"
    assert rules.keep_or_drop(1.0, 1.2, 0.1) == "keep"


def test_early_plays_size_follows_the_shortfall(rd):
    rule = by_name("early_plays")
    everything = np.ones(len(rd.base.set), dtype=bool)
    short = 7 - rd.counts["early"][rd.counts["early"] < 7]
    expected = np.mean(np.minimum(0.5, 0.15 * short)) * 50 / 15
    assert rules.implied(rule, rd, everything) == pytest.approx(expected)
    assert rules.implied(by_name("creature_quota"), rd, everything) == pytest.approx(
        0.25 * 50 / 15
    )


def test_fixing_terms_follow_the_engine():
    r = {"off_color": np.array([0.0, 2, 2, 2]), "fixing": np.array([0.0, 1, 2, 3])}
    terms = rules.fixing_terms(r)
    # Hungry while fixing <= off-color: short by off + 1 - fixing.
    assert list(terms["fixing_short"]) == [0, 2, 1, 0]
    assert list(terms["fixing_in_off_color_deck"]) == [0, 1, 2, 3]


def test_sets_without_tags_are_left_out_of_that_rule():
    data = files(n=8000, sets=("AAA", "BBB")) + files(n=4000, sets=("CCC",), tags=False)
    rd = rules.RuleData(data)
    assert rules.usable_sets(rd, by_name("removal_saturation")) == ["AAA", "BBB"]
    assert rules.usable_sets(rd, by_name("curve_heavy")) == ["AAA", "BBB", "CCC"]
    # Every deck in CCC has fewer than 3 removal spells, but CCC has no tags.
    assert rules.usable_sets(rd, by_name("removal_need")) == ["AAA", "BBB"]


def test_dose_puts_the_reference_in_order(rd):
    everything = np.ones(len(rd.base.set), dtype=bool)
    var, rows = rules.dose(rd, by_name("removal_saturation"), everything)
    labels = [label for label, *_ in rows]
    assert var == "removal"
    assert labels == ["2 or fewer", "3", "4", "5", "6 (reference)", "7", "8", "9",
                      "10 or more"]
    assert sum(n for _, n, *_ in rows) == len(rd.base.set)
    # Removal past the sixth costs wins, so 10+ is below 6.
    assert rows[-1][2] < 0


def test_report(tmp_path, rd):
    out = io.StringIO()
    results = rules.report(rd, out)
    text = out.getvalue()
    for heading in ("## Primary results", "## By set", "## By count",
                    "## Uncertainty and sensitivity", "## Deck score terms"):
        assert heading in text
    assert results["removal_saturation"]["verdict"] in (
        "supported", "not established"
    )
    assert set(results["curve_heavy"]["per_set"]) == {"AAA", "BBB", "CCC", "DDD"}
    # Simulated removal past the sixth costs 23 * -0.06 / 0.4 = -3.45 rating
    # SDs, beyond the rule's -0.87.
    assert results["removal_saturation"]["keep_or_drop"] == "keep"
    # missing_fixing is never set in the simulated decks, so it drops out.
    assert set(results["deck_terms"]) == {"two_colors"}
    paths = []
    for f in files(n=4000, sets=("AAA", "BBB")):
        path = tmp_path / f"{f['set']}.json"
        path.write_text(json.dumps(f))
        paths.append(str(path))
    rules.main(paths + ["--json", str(tmp_path / "rules.json")])
    saved = json.loads((tmp_path / "rules.json").read_text())
    assert set(saved) == {r.name for r in rules.RULES} | {"deck_terms"}

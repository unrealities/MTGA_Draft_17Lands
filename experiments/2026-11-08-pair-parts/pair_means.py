"""Looked at after the result: per pair-by-set means of the deck parts.

    python -I pair_means.py RUN_ID WORK_DIR OUT.json

Downloads each features artifact into its own new directory, reduces it, deletes it.
"""
import glob
import json
import os
import shutil
import subprocess
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "Tools", "DeckScoreFit"))
from games import fold_of  # noqa: E402

REPO = "JamesYouL2/MTGA_Draft_17Lands"
run, work, out_path = sys.argv[1:4]
names = subprocess.run(
    ["gh", "api", f"repos/{REPO}/actions/runs/{run}/artifacts", "--paginate", "--jq",
     '.artifacts[].name'], capture_output=True, text=True, check=True).stdout.split()
out = {}
for name in sorted(n for n in names if n.startswith("features-")):
    d = os.path.join(work, name)
    os.makedirs(d)
    subprocess.run(["gh", "run", "download", run, "-R", REPO, "-n", name, "-D", d], check=True)
    q_path = glob.glob(os.path.join(d, "quality", "*.json"))[0]
    f_path = [p for p in glob.glob(os.path.join(d, "*.json"))][0]
    with open(q_path, encoding="utf-8") as f:
        q = json.load(f)
    idx = {k: q["part_names"].index(k) for k in ("overall", "level", "fit")}
    own = {}
    for key, rows in q["parts"].items():
        row = rows[fold_of(key)]
        own[key] = (row[idx["overall"]], row[idx["level"]], row[idx["fit"]], q["pairs"][key])
    del q
    with open(f_path, encoding="utf-8") as f:
        features = json.load(f)
    per = {}
    for r in features["rows"]:
        if r["id"] not in own:
            continue
        o, l, fit, pair = own[r["id"]]
        try:
            skill = float(r["skill"])
        except (TypeError, ValueError):
            skill = float("nan")
        per.setdefault(pair, []).append((r["wins"], r["games"], o, l, fit, skill))
    del features, own
    result = {}
    for pair, rows in per.items():
        a = np.array(rows, dtype=float)
        wins, games, o, l, fit, skill = a.T
        wr = wins.sum() / games.sum()
        ok = ~np.isnan(skill)
        # Games-weighted slope of a deck's win rate on its overall rating, within the pair.
        rate = wins / games
        mo = np.average(o, weights=games)
        sxx = float(np.sum(games * (o - mo) ** 2))
        sxy = float(np.sum(games * (o - mo) * (rate - wr)))
        result[pair] = {
            "decks": len(rows), "games": float(games.sum()), "wins": float(wins.sum()),
            "overall": float(mo), "level": float(np.average(l, weights=games)),
            "fit": float(np.average(fit, weights=games)),
            "skill": float(skill[ok].mean()) if ok.any() else None,
            "sxx": sxx, "sxy": sxy,
        }
    out[name.removeprefix("features-")] = result
    del per
    shutil.rmtree(d)
    print(name, len(result), flush=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f)
print("done", flush=True)

"""Integrity of the shipped card-prior assets and cross-process determinism.

Runs anywhere the suite runs (CI included): validates the npz/manifest pair
the loader consumes and pins the determinism contract (same inputs+seed ->
same priors regardless of PYTHONHASHSEED).
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets" / "models"


def test_table_manifest_pair():
    data = np.load(ASSETS / "card_prior_z_table.npz", allow_pickle=False)
    manifest = json.loads((ASSETS / "card_prior_z_table_manifest.json").read_text())
    cl = manifest["z_clamps"]
    assert isinstance(cl, list) and len(cl) == 2 and float(cl[0]) < 0 < float(cl[1])
    z = data["z"]
    assert z.dtype == np.float32
    assert np.isfinite(z).all(), "non-finite z values in the table"
    assert float(z.min()) >= float(cl[0]) - 1e-6
    assert float(z.max()) <= float(cl[1]) + 1e-6
    assert manifest["n_cards"] == len(data["names"])


def test_table_names_unique_and_covering():
    data = np.load(ASSETS / "card_prior_z_table.npz", allow_pickle=False)
    names = [str(n) for n in data["names"]]
    assert len(names) >= 30000, "table lost coverage"
    norm = [n.lower().replace("’", "'").strip() for n in names]
    assert len(set(norm)) == len(norm), "duplicate normalized names"


def test_face_index_consistency():
    from src.advisor import deck_scorer as _ds

    _ds._load_prior_z_table()
    # the ORIGINAL table rows (pre-alias): a face part that exists as its own
    # row keeps its own value (collision rule); otherwise it aliases the full
    # split name's row
    data = np.load(ASSETS / "card_prior_z_table.npz", allow_pickle=False)
    originals = {_ds._norm_card_name(str(n)) for n in data["names"]}
    full = {k: v for k, v in _ds._PRIOR_Z_TABLE.items() if " // " in k}
    assert len(full) > 100
    checked = 0
    for k, v in full.items():
        parts = [p for p in k.split(" // ") if p]
        if len(parts) > 1 and len(set(parts)) == 1:
            continue  # degenerate repeated-name row: no face alias (R2-3)
        for part in parts:
            if part in originals:
                continue  # standalone row wins by design
            got = _ds._PRIOR_Z_TABLE.get(part)
            assert got == v, f"face alias {part!r} != full row {k!r}"
            checked += 1
        if checked >= 50:
            break
    assert checked >= 10


def _prior_hash(seed_env_value):
    code = (
        "import hashlib, sys;"
        "sys.path.insert(0, '.');"
        "from src.advisor import deck_scorer as ds;"
        "vals = [ds._feature_prior_z({'name': n}) for n in "
        "['Sol Ring', 'Grizzly Bears', 'Fire // Ice', 'Ajani Unrelenting',"
        " 'Jeweled Lotus', 'Time Sieve', 'Mox Opal']];"
        "print(hashlib.sha256(repr(vals).encode()).hexdigest())"
    )
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = seed_env_value
    out = subprocess.run([sys.executable, "-c", code], cwd=str(ROOT),
                         env=env, capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr
    return out.stdout.strip()


@pytest.mark.slow
def test_priors_deterministic_across_hashseeds():
    a = _prior_hash("0")
    b = _prior_hash("12345")
    assert a == b, "prior values differ across PYTHONHASHSEED values"

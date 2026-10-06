"""
tests/test_import_cycles.py
Every advisor module must import cleanly in a fresh interpreter, without
relying on src.card_logic having been imported first (issue #203).

The in-process test session cannot catch this: conftest and other tests
import card_logic early, which hides the cycle. Each check therefore runs in
its own subprocess.
"""

import os
import subprocess
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MODULES = [
    "src.card_utils",
    "src.advisor.mana_base",
    "src.advisor.simulator",
    "src.advisor.deck_scorer",
    "src.advisor.deck_builder",
    "src.advisor.engine",
    "src.card_logic",
]


@pytest.mark.parametrize("module", MODULES)
def test_module_imports_in_fresh_process(module):
    result = subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr


def test_card_logic_still_reexports_advisor_api():
    """Callers import the advisor API through src.card_logic; keep it there."""
    code = (
        "from src.card_logic import (simulate_deck, get_card_rating, "
        "optimize_deck, suggest_deck, identify_top_pairs, "
        "calculate_holistic_score, get_functional_cmc, stack_cards, "
        "count_fixing, is_castable, get_strict_colors)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr

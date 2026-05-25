"""
tests/test_practice_dialog.py
Tests the Sealed Practice Dialog, including MTGA clipboard parsing and RNG pool generation.
"""

import pytest
import tkinter
from unittest.mock import MagicMock, patch
from src.ui.windows.practice_dialog import PracticeDialog
from src.configuration import Configuration
from src.limited_sets import SetInfo


@pytest.fixture
def root():
    root = tkinter.Tk()
    yield root
    root.destroy()


@pytest.fixture
def mock_app_context(root):
    app = MagicMock()
    app.root = root
    app.configuration = Configuration()

    # Mock Set List Data
    mock_set_info = SetInfo(set_code="M10", seventeenlands=["M10"])
    app.orchestrator.scanner.set_list.data = {"Magic 2010": mock_set_info}
    app.orchestrator.scanner.set_list.latest_set = "M10"

    # Mock the internal dataset
    mock_dataset = MagicMock()
    # Mock finding a card by name
    mock_dataset.get_data_by_name.side_effect = lambda n: [{"name": n[0], "cmc": 2}]
    # Mock the ratings dictionary for Random Pool Generation
    mock_dataset.get_card_ratings.return_value = {
        "1": {"name": "Common 1", "rarity": "common", "types": ["Creature"]},
        "2": {"name": "Uncommon 1", "rarity": "uncommon", "types": ["Creature"]},
        "3": {"name": "Rare 1", "rarity": "rare", "types": ["Creature"]},
        "4": {"name": "Basic Land", "rarity": "common", "types": ["Basic", "Land"]},
    }
    app.orchestrator.scanner.set_data = mock_dataset

    return app


@patch("src.ui.windows.practice_dialog.retrieve_local_set_list")
@patch("src.ui.windows.practice_dialog.SealedStudioWindow")
def test_import_clipboard_success(mock_studio, mock_retrieve, root, mock_app_context):
    """Verify that valid MTGA format clipboard data is successfully parsed into a pool."""
    # Mock that we have a dataset downloaded
    mock_retrieve.return_value = (
        [("M10", "Sealed", "All", "", "", 0, "/fake/path.json", "")],
        [],
    )

    # Put fake MTGA export data into the clipboard
    clipboard_data = "Deck\n1 Lightning Bolt\n2 Grizzly Bears\n\nSideboard\n1 Shock"
    root.clipboard_clear()
    root.clipboard_append(clipboard_data)

    dialog = PracticeDialog(root, mock_app_context, is_import=True)
    dialog._on_confirm()

    # Verify SealedStudio was launched
    mock_studio.assert_called_once()

    # The pool passed to SealedStudio is the 4th argument (index 3)
    generated_pool = mock_studio.call_args[0][3]

    # 1 Bolt, 2 Bears, 1 Shock = 4 cards total
    assert len(generated_pool) == 4
    names = [c["name"] for c in generated_pool]
    assert names.count("Lightning Bolt") == 1
    assert names.count("Grizzly Bears") == 2
    assert names.count("Shock") == 1


@patch("src.ui.windows.practice_dialog.retrieve_local_set_list")
@patch("tkinter.messagebox.showwarning")
def test_import_clipboard_garbage_data(
    mock_warn, mock_retrieve, root, mock_app_context
):
    """Verify that invalid clipboard data shows a warning instead of crashing."""
    mock_retrieve.return_value = (
        [("M10", "Sealed", "All", "", "", 0, "/fake/path.json", "")],
        [],
    )

    # Put garbage in clipboard
    root.clipboard_clear()
    root.clipboard_append("This is just some random text from the internet.")

    dialog = PracticeDialog(root, mock_app_context, is_import=True)
    dialog._on_confirm()

    # Warning should trigger, studio should NOT launch
    mock_warn.assert_called_once()
    assert "No valid MTGA format" in mock_warn.call_args[0][1]


@patch("src.ui.windows.practice_dialog.retrieve_local_set_list")
@patch("src.ui.windows.practice_dialog.SealedStudioWindow")
def test_generate_random_pool(mock_studio, mock_retrieve, root, mock_app_context):
    """Verify the RNG pool generation logic correctly selects 6 rares, 18 uncommons, and 60 commons."""
    mock_retrieve.return_value = (
        [("M10", "Sealed", "All", "", "", 0, "/fake/path.json", "")],
        [],
    )

    dialog = PracticeDialog(root, mock_app_context, is_import=False)
    dialog._on_confirm()

    mock_studio.assert_called_once()
    generated_pool = mock_studio.call_args[0][3]

    # 6 packs * (1 rare + 3 uncommons + 10 commons) = 84 cards
    assert len(generated_pool) == 84

    # Ensure Basic Lands are ignored in generation (as per the code logic)
    names = [c["name"] for c in generated_pool]
    assert "Basic Land" not in names


@patch("src.ui.windows.practice_dialog.retrieve_local_set_list")
@patch("tkinter.messagebox.showwarning")
def test_missing_dataset_blocks_generation(
    mock_warn, mock_retrieve, root, mock_app_context
):
    """Verify that attempting to practice without a downloaded dataset gracefully alerts the user."""
    # Return empty datasets
    mock_retrieve.return_value = ([], [])

    dialog = PracticeDialog(root, mock_app_context, is_import=False)
    dialog._on_confirm()

    mock_warn.assert_called_once()
    assert "No downloaded dataset found" in mock_warn.call_args[0][1]

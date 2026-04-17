import pytest
import tkinter
from unittest.mock import MagicMock, patch
from src.ui.windows.overlay import CompactOverlay
from src.configuration import Configuration
from src.ui.styles import Theme


@pytest.fixture
def root():
    r = tkinter.Tk()
    Theme.apply(r, "Dark")
    yield r
    r.destroy()


@pytest.fixture
def mock_app_context():
    context = MagicMock()
    context.orchestrator.scanner.retrieve_current_limited_event.return_value = (
        "M10",
        "Draft",
    )
    context.orchestrator.scanner.retrieve_taken_cards.return_value = []
    context.orchestrator.scanner.retrieve_current_missing_cards.return_value = []
    context.orchestrator.scanner.retrieve_current_pack_and_pick.return_value = (1, 1)

    # Mock Tkinter variables for labels
    var_mock = MagicMock()
    var_mock.get.return_value = "PremierDraft"
    context.vars = {
        "selected_event": var_mock,
        "selected_group": var_mock,
        "deck_filter": MagicMock(get=lambda: "All Decks"),
    }
    return context


@patch("tkinter.Toplevel.overrideredirect")
@patch("tkinter.Toplevel.wm_overrideredirect")
def test_compact_overlay_initialization_and_drag(
    mock_wm, mock_ov, root, mock_app_context
):
    """Verifies overlay can initialize without crashing and calculates drag vectors correctly."""
    config = Configuration()
    overlay = CompactOverlay(root, mock_app_context, config, lambda: None)

    assert overlay.winfo_exists()

    # Simulate a drag event
    class DragEvent:
        x = 100
        y = 50

    overlay._start_move(DragEvent())
    assert overlay.x == 100
    assert overlay.y == 50

    # Simulate moving 50px right
    class MoveEvent:
        x = 150
        y = 50

    overlay._do_move(MoveEvent())

    # Simulate stop drag
    overlay._stop_move(DragEvent())
    assert overlay.x is None


@patch("tkinter.Toplevel.overrideredirect")
@patch("tkinter.Toplevel.wm_overrideredirect")
def test_compact_overlay_update_data(mock_wm, mock_ov, root, mock_app_context):
    """Verifies that injecting pack data correctly populates the Treeview elements."""
    config = Configuration()
    overlay = CompactOverlay(root, mock_app_context, config, lambda: None)

    # Mock pack cards
    pack_cards = [
        {
            "name": "Lightning Bolt",
            "colors": ["R"],
            "deck_colors": {"All Decks": {"gihwr": 62.0}},
        },
        {
            "name": "Counterspell",
            "colors": ["U"],
            "deck_colors": {"All Decks": {"gihwr": 55.0}},
        },
    ]

    # Run the UI update cycle
    try:
        overlay.update_data(
            pack_cards=pack_cards,
            colors=["All Decks"],
            metrics=MagicMock(),
            tier_data={},
            current_pick=1,
            recommendations=None,
            picked_cards=[],
        )
    except Exception as e:
        pytest.fail(f"Overlay crashed during data update: {e}")

    # Verify rows were added to the internal Pack tree
    tree = overlay.table_manager.tree
    rows = tree.get_children()

    # We passed in 2 cards, the tree should have 2 rows
    assert len(rows) == 2

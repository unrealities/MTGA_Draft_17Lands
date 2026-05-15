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


@patch("tkinter.Toplevel.overrideredirect")
@patch("tkinter.Toplevel.wm_overrideredirect")
def test_compact_overlay_tab_switching_triggers_redraw(
    mock_wm, mock_ov, root, mock_app_context
):
    """Verify switching tabs manually forces the graph canvases to redraw their geometry."""
    config = Configuration()
    overlay = CompactOverlay(root, mock_app_context, config, lambda: None)

    # Spy on the redraw methods
    overlay.signal_meter.redraw = MagicMock()
    overlay.curve_plot.redraw = MagicMock()
    overlay.type_chart.redraw = MagicMock()

    # Simulate a Virtual Event from Tkinter Notebook
    overlay._on_tab_changed(None)

    # Due to update_idletasks() firing <Configure> events during testing,
    # redraw() may be called multiple times. We just ensure it executed.
    assert overlay.signal_meter.redraw.call_count >= 1
    assert overlay.curve_plot.redraw.call_count >= 1
    assert overlay.type_chart.redraw.call_count >= 1


@patch("tkinter.Toplevel.overrideredirect")
@patch("tkinter.Toplevel.wm_overrideredirect")
def test_compact_overlay_settings_menu_generation(
    mock_wm, mock_ov, root, mock_app_context
):
    """Verify the gear icon correctly generates cascading menus from the App Context variables."""
    config = Configuration()

    # Inject dummy event data
    mock_app_context.deck_filter_map = {"All Decks": "All", "Dimir": "UB"}
    mock_app_context.current_set_data_map = {
        "PremierDraft": {"All": "/path1", "Top": "/path2"},
        "TradDraft": {"All": "/path3"},
    }

    overlay = CompactOverlay(root, mock_app_context, config, lambda: None)

    with patch("tkinter.Menu.post") as mock_post:
        overlay._show_settings_menu()

        # Menu should have successfully generated and attempted to display
        mock_post.assert_called_once()


@patch("tkinter.Toplevel.overrideredirect")
@patch("tkinter.Toplevel.wm_overrideredirect")
def test_compact_overlay_missing_cards_grid_weights(
    mock_wm, mock_ov, root, mock_app_context
):
    """Verify that the UI vertically splits the window ONLY if there are wheel tracking cards to show."""
    config = Configuration()
    overlay = CompactOverlay(root, mock_app_context, config, lambda: None)

    # Scenario 1: No missing cards (Early Draft)
    overlay.update_data(
        pack_cards=[{"name": "Card A"}],
        colors=["All Decks"],
        metrics=MagicMock(),
        tier_data={},
        current_pick=1,
        picked_cards=[],
    )

    # The missing frame should be hidden
    assert not overlay.missing_frame.winfo_viewable()

    # Scenario 2: Missing cards exist (Late Draft - Wheel Tracker active)
    mock_app_context.orchestrator.scanner.retrieve_current_missing_cards.return_value = [
        {"name": "Wheeled Card"}
    ]

    overlay.update_data(
        pack_cards=[{"name": "Card A"}],
        colors=["All Decks"],
        metrics=MagicMock(),
        tier_data={},
        current_pick=9,
        picked_cards=[],
    )

    # The missing frame should be forced into the grid
    assert "grid" in overlay.missing_frame.winfo_manager()

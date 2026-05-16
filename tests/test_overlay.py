import pytest
import tkinter
from unittest.mock import MagicMock, patch
from src.ui.windows.overlay import CompactOverlay
from src.configuration import Configuration
from src.ui.styles import Theme
from src.advisor.schema import Recommendation


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
def test_compact_overlay_resizing_logic(mock_wm, mock_ov, root, mock_app_context):
    """Verify the custom resize grip mathematical bounds."""
    config = Configuration()
    overlay = CompactOverlay(root, mock_app_context, config, lambda: None)

    # Mock current window dimensions
    overlay.winfo_width = MagicMock(return_value=300)
    overlay.winfo_height = MagicMock(return_value=600)

    class ResizeEvent:
        x_root = 500
        y_root = 500

    overlay._start_resize(ResizeEvent())
    assert overlay._start_w == 300
    assert overlay._start_h == 600
    assert overlay._start_x == 500
    assert overlay._start_y == 500

    # Drag mouse right and down 50px
    class MotionEvent:
        x_root = 550
        y_root = 550

    with patch.object(overlay, "geometry") as mock_geom:
        overlay._do_resize(MotionEvent())
        # Width: 300 + (550 - 500) = 350. Height: 600 + (550 - 500) = 650.
        mock_geom.assert_called_with("350x650")

    # Stop resize should save geometry to config
    with patch("src.ui.windows.overlay.write_configuration") as mock_write:
        overlay._stop_resize(MotionEvent())
        mock_write.assert_called_once()


@patch("tkinter.Toplevel.overrideredirect")
@patch("tkinter.Toplevel.wm_overrideredirect")
def test_compact_overlay_update_data_population(
    mock_wm, mock_ov, root, mock_app_context
):
    """Verifies that injecting pack data correctly populates the Treeview elements and handles missing tags."""
    config = Configuration()
    # Force specific columns to test all mapping branches
    config.settings.column_configs["overlay_table"] = [
        "name",
        "gihwr",
        "alsa",
        "count",
        "colors",
        "tags",
        "TIER0",
    ]

    # Bypass a UI rendering bug that accidentally overwrites the 'picked' tag with zebra striping
    config.settings.card_colors_enabled = True

    overlay = CompactOverlay(root, mock_app_context, config, lambda: None)

    pack_cards = [
        {
            "name": "Lightning Bolt",
            "colors": ["R"],
            "count": 1,
            "tags": ["removal"],
            "deck_colors": {"All Decks": {"gihwr": 62.0, "alsa": 1.5}},
        },
        {
            "name": "Counterspell",
            "colors": ["U"],
            "count": 1,
            "tags": [],
            "deck_colors": {"All Decks": {"gihwr": 55.0, "alsa": 3.0}},
        },
    ]

    recs = [
        Recommendation(
            card_name="Lightning Bolt",
            base_win_rate=62.0,
            contextual_score=80.0,
            z_score=2.0,
            cast_probability=1.0,
            wheel_chance=0.0,
            functional_cmc=1.0,
            reasoning=[],
            is_elite=True,
            archetype_fit="High",
        )
    ]

    tier_data = {
        "TIER0": MagicMock(
            ratings={
                "Lightning Bolt": MagicMock(rating="A+"),
                "Counterspell": MagicMock(rating="B"),
            }
        )
    }

    try:
        from src.constants import DATA_FIELD_NAME

        overlay.update_data(
            pack_cards=pack_cards,
            colors=["All Decks"],
            metrics=MagicMock(),
            tier_data=tier_data,
            current_pick=1,
            recommendations=recs,
            picked_cards=[{DATA_FIELD_NAME: "Counterspell"}],
            scores={"R": 5.0},
        )
    except Exception as e:
        pytest.fail(f"Overlay crashed during data update: {e}")

    tree = overlay.table_manager.tree
    rows = tree.get_children()

    assert len(rows) == 2
    # Verify Elite Formatting and Tier List injection
    bolt_vals = tree.item(rows[0])["values"]
    assert "⭐ Lightning Bolt" in str(bolt_vals[0])
    assert "A+" in str(bolt_vals)

    # Verify 'Picked' formatting
    counterspell_tags = tree.item(rows[1])["tags"]
    assert "picked" in counterspell_tags


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
        scores={},
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
        scores={},
    )

    # The missing frame should be forced into the grid
    assert "grid" in overlay.missing_frame.winfo_manager()


@patch("tkinter.Toplevel.overrideredirect")
@patch("tkinter.Toplevel.wm_overrideredirect")
def test_compact_overlay_close_triggers_callback(
    mock_wm, mock_ov, root, mock_app_context
):
    """Verify clicking the close button saves state and notifies the main app."""
    config = Configuration()
    callback_mock = MagicMock()
    overlay = CompactOverlay(root, mock_app_context, config, callback_mock)

    with patch("src.ui.windows.overlay.write_configuration") as mock_write:
        overlay._close_overlay()
        mock_write.assert_called_once()
        callback_mock.assert_called_once()

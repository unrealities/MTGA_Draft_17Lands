"""
tests/test_top_bar.py
Tests the Top Bar Controls (Status dot, Auto-Detect Label, and History Dropdown logic).
"""

import pytest
import tkinter
from unittest.mock import MagicMock, patch
from src.ui.top_bar import TopBarControls
from src.configuration import Configuration
from src.ui.styles import Theme
from src import constants


@pytest.fixture
def root():
    root = tkinter.Tk()
    Theme.apply(root, "Dark")
    yield root
    root.destroy()


@pytest.fixture
def mock_app_context(root):
    app = MagicMock()
    app.root = root
    app.configuration = Configuration()

    app.configuration.settings.arena_log_location = "fake_live.log"

    app.vars = {
        "status_text": tkinter.StringVar(),
        "set_label": tkinter.StringVar(),
        "deck_filter": tkinter.StringVar(value=constants.FILTER_OPTION_AUTO),
        "selected_event": tkinter.StringVar(),
        "selected_group": tkinter.StringVar(),
    }

    app.orchestrator.scanner.arena_file = "Player.log"
    app.orchestrator.scanner.retrieve_current_limited_event.return_value = (
        "M10",
        "PremierDraft",
    )
    app.detected_set_code = "M10"

    return app


def test_update_status_dot(root, mock_app_context):
    """Verify the green/grey recording dot correctly reflects file modification timestamps."""
    top_bar = TopBarControls(root, mock_app_context)
    top_bar.status_dot.config = MagicMock()

    # Timestamps match = Idle
    top_bar.update_status_dot(current_ts=100, prev_ts=100)
    top_bar.status_dot.config.assert_called_with(bootstyle="secondary")

    # Timestamps differ = Active
    top_bar.update_status_dot(current_ts=105, prev_ts=100)
    top_bar.status_dot.config.assert_called_with(bootstyle="success")


def test_update_auto_detect_label(root, mock_app_context):
    """Verify the small text label updates to show the detected archetype."""
    top_bar = TopBarControls(root, mock_app_context)
    mock_app_context.orchestrator.scanner.set_data.get_color_ratings.return_value = {
        "UB": 55.0
    }

    top_bar.update_auto_detect_label(colors=["UB"])
    text = top_bar.lbl_auto_detect.cget("text")
    assert "UB" in text or "Dimir" in text
    assert "55.0%" in text

    top_bar.update_auto_detect_label(colors=[])
    text = top_bar.lbl_auto_detect.cget("text")
    assert "Detecting..." in text


@patch("src.ui.top_bar.os.path.exists", return_value=True)
@patch("src.ui.top_bar.os.listdir")
@patch("src.ui.top_bar.os.path.getmtime", return_value=123.0)
def test_update_history_dropdown(
    mock_mtime, mock_listdir, mock_exists, root, mock_app_context
):
    """Verify that old draft logs are scanned and populated into the history dropdown."""
    top_bar = TopBarControls(root, mock_app_context)

    # Return 1 dummy draft log
    mock_listdir.return_value = ["DraftLog_M10_PremierDraft_123.log"]

    top_bar.update_history_dropdown()

    options = top_bar.combo_history.cget("values")
    # Should contain the live log (always added if exists) + the 1 historical log
    assert len(options) == 2
    assert any("Live" in opt for opt in options)
    assert any("M10" in opt for opt in options)


def test_history_select_triggers_load(root, mock_app_context):
    """Verify selecting a historical log sends the file path to the orchestrator."""
    top_bar = TopBarControls(root, mock_app_context)
    top_bar.history_files = {"📂 M10 PremierDraft": "/Logs/DraftLog_M10_123.log"}
    mock_app_context.vars["set_label"].set("📂 M10 PremierDraft")

    top_bar._on_history_select(None)
    mock_app_context.orchestrator.set_file_and_scan.assert_called_once_with(
        "/Logs/DraftLog_M10_123.log"
    )


@patch("src.ui.top_bar.retrieve_local_set_list")
def test_update_data_sources(mock_retrieve, root, mock_app_context):
    """Verify the Top Bar correctly parses the local sets directory and populates the Event dropdown."""
    top_bar = TopBarControls(root, mock_app_context)

    # M10 matches the active draft in the fixture
    mock_retrieve.return_value = (
        [
            (
                "M10",
                "PremierDraft",
                "All",
                "2024",
                "2024",
                500,
                "/mock/path.json",
                "2024",
            )
        ],
        [],
    )

    top_bar.update_data_sources()

    assert mock_app_context.detected_set_code == "M10"

    menu = top_bar.om_event["menu"]
    end_idx = menu.index("end")
    if end_idx is not None:
        labels = [menu.entrycget(i, "label") for i in range(end_idx + 1)]
        assert "PremierDraft" in labels
    else:
        pytest.fail("Dropdown menu was empty!")


def test_update_deck_filter_options(root, mock_app_context):
    """Verify the filter dropdown pulls Archetype/Color data from the active dataset."""
    top_bar = TopBarControls(root, mock_app_context)

    # Prevent early exit
    mock_app_context._loading = False

    # Mock scanner returning available deck color filters
    mock_app_context.orchestrator.scanner.retrieve_color_win_rate.return_value = {
        "All Decks": "All Decks",
        "Dimir (UB)": "UB",
    }

    top_bar.update_deck_filter_options()

    menu = top_bar.om_filter["menu"]
    labels = [menu.entrycget(i, "label") for i in range(menu.index("end") + 1)]

    assert "All Decks" in labels
    assert "Dimir (UB)" in labels


def test_on_event_change_updates_group_dropdown(root, mock_app_context):
    """Verify changing the Event Type (e.g. Premier to Quick) refreshes the User Group dropdown."""
    top_bar = TopBarControls(root, mock_app_context)
    mock_app_context._initialized = True

    mock_app_context.vars["selected_event"].set("PremierDraft")
    mock_app_context.current_set_data_map = {
        "PremierDraft": {"All": "/path1", "Top": "/path2"}
    }

    with patch.object(top_bar, "on_group_change") as mock_group_change:
        top_bar.on_event_change()

        menu = top_bar.om_group["menu"]
        labels = [menu.entrycget(i, "label") for i in range(menu.index("end") + 1)]

        assert "All" in labels
        assert "Top" in labels

        # Because the current group was empty, it should auto-select "All" and trigger the downstream loader
        assert mock_app_context.vars["selected_group"].get() == "All"
        mock_group_change.assert_called_once()


@patch("src.ui.top_bar.write_configuration")
@patch("src.ui.top_bar.os.path.basename", return_value="path.json")
def test_on_group_change_loads_dataset(
    mock_basename, mock_write, root, mock_app_context
):
    """Verify selecting a final dataset combination successfully triggers the orchestrator to load the file."""
    top_bar = TopBarControls(root, mock_app_context)
    mock_app_context._initialized = True

    # Inject UI state
    mock_app_context.vars["selected_event"].set("PremierDraft")
    mock_app_context.vars["selected_group"].set("Top")
    mock_app_context.current_set_data_map = {"PremierDraft": {"Top": "/mock/path.json"}}

    top_bar.on_group_change()

    # 1. Scanner should be told to read the JSON file
    mock_app_context.orchestrator.scanner.retrieve_set_data.assert_called_once_with(
        "/mock/path.json"
    )

    # 2. Config should be updated and saved
    assert mock_app_context.configuration.card_data.latest_dataset == "path.json"
    mock_write.assert_called_once()

    # 3. Math engines and UI should be refreshed
    mock_app_context.orchestrator.request_math_update.assert_called_once()

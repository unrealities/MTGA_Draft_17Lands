"""
tests/test_menu_bar.py
Tests the OS Menu Bar integration, Custom Theme loading, and Log finding dialogs.
"""

import pytest
import tkinter
from unittest.mock import MagicMock, patch
from src.ui.menu_bar import AppMenuBar
from src.configuration import Configuration


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
    return app


@patch("src.ui.menu_bar.Theme.apply")
@patch("src.ui.menu_bar.write_configuration")
def test_update_theme(mock_write, mock_theme_apply, root, mock_app_context):
    """Verify clicking a theme from the menu updates config and triggers the UI theme engine."""
    menu_bar = AppMenuBar(root, mock_app_context)

    # Simulate clicking "Mana Flair: Island"
    menu_bar._update_theme(new_palette="Island")

    # Config should be updated
    assert mock_app_context.configuration.settings.theme == "Island"
    # Config should be written to disk
    mock_write.assert_called_once()
    # Theme engine should be triggered
    mock_theme_apply.assert_called_once()


@patch("src.ui.menu_bar.filedialog.askopenfilename")
@patch("src.ui.menu_bar.Theme.apply")
def test_browse_custom_tcl_theme(
    mock_theme_apply, mock_filedialog, root, mock_app_context
):
    """Verify custom TCL file loading routes correctly."""
    menu_bar = AppMenuBar(root, mock_app_context)

    # Mock user selecting a file
    mock_filedialog.return_value = "/path/to/custom_theme.tcl"

    menu_bar._browse_custom_tcl()

    # Verify the custom path was injected into config
    assert (
        mock_app_context.configuration.settings.theme_custom_path
        == "/path/to/custom_theme.tcl"
    )
    mock_theme_apply.assert_called_once()


@patch("src.ui.menu_bar.filedialog.askopenfilename")
def test_read_draft_log(mock_filedialog, root, mock_app_context):
    """Verify the "Read Draft Log..." menu item triggers the orchestrator scanner."""
    menu_bar = AppMenuBar(root, mock_app_context)

    # Mock user selecting a draft log
    mock_filedialog.return_value = "/Logs/DraftLog_M10.log"

    menu_bar._read_draft_log()

    # Verify the loading overlay was triggered
    mock_app_context.loading_overlay.show.assert_called_once_with("Loading Draft Log")

    # Verify orchestrator was told to scan the new file
    mock_app_context.orchestrator.set_file_and_scan.assert_called_once_with(
        "/Logs/DraftLog_M10.log"
    )


@patch("src.ui.menu_bar.filedialog.askopenfilename")
def test_read_draft_log_cancelled(mock_filedialog, root, mock_app_context):
    """Verify closing the file dialog without selecting a file does nothing."""
    menu_bar = AppMenuBar(root, mock_app_context)

    # Mock user hitting "Cancel" (returns empty string or None)
    mock_filedialog.return_value = ""

    menu_bar._read_draft_log()

    # Orchestrator should NOT be called
    mock_app_context.orchestrator.set_file_and_scan.assert_not_called()


@patch("src.ui.menu_bar.filedialog.askdirectory")
@patch("src.ui.menu_bar.os.path.exists")
@patch("src.ui.menu_bar.write_configuration")
@patch("src.ui.menu_bar.messagebox.showinfo")
def test_locate_mtga_data_success(
    mock_showinfo, mock_write, mock_exists, mock_askdir, root, mock_app_context
):
    """Verify selecting a custom MTGA_Data folder updates config and triggers a math update."""
    menu_bar = AppMenuBar(root, mock_app_context)

    # Mock user selecting a folder
    mock_askdir.return_value = "/Custom/Games/MTGA_Data"
    # Mock that 'Downloads/Raw' exists inside the selected folder
    mock_exists.return_value = True

    menu_bar._locate_mtga_data()

    # Verify config update
    assert (
        mock_app_context.configuration.settings.database_location
        == "/Custom/Games/MTGA_Data"
    )
    mock_write.assert_called_once()

    # Verify the database cache was cleared and the UI was refreshed
    mock_app_context.orchestrator.scanner.set_data.unknown_id_cache.clear.assert_called_once()
    mock_app_context.orchestrator.request_math_update.assert_called_once()
    mock_app_context._refresh_ui_data.assert_called_once()
    mock_showinfo.assert_called_once()


@patch("src.ui.menu_bar.filedialog.asksaveasfile")
@patch("tkinter.messagebox.showinfo")
def test_export_csv_routing(mock_msg, mock_file, root, mock_app_context):
    """Verify the export CSV menu item routes correctly to the card logic exporter."""
    menu_bar = AppMenuBar(root, mock_app_context)

    mock_app_context.orchestrator.scanner.retrieve_draft_history.return_value = [
        {"Pack": 1, "Pick": 1, "Cards": ["123"]}
    ]
    mock_f = MagicMock()
    mock_f.__enter__.return_value = mock_f
    mock_file.return_value = mock_f

    with patch(
        "src.card_logic.export_draft_to_csv", return_value="csv_data"
    ) as mock_export:
        menu_bar._export_csv()

        mock_export.assert_called_once()
        mock_f.write.assert_called_once_with("csv_data")
        mock_msg.assert_called_once()


@patch("src.ui.menu_bar.filedialog.asksaveasfile")
@patch("tkinter.messagebox.showinfo")
def test_export_json_routing(mock_msg, mock_file, root, mock_app_context):
    """Verify the export JSON menu item routes correctly to the card logic exporter."""
    menu_bar = AppMenuBar(root, mock_app_context)

    mock_app_context.orchestrator.scanner.retrieve_draft_history.return_value = [
        {"Pack": 1, "Pick": 1, "Cards": ["123"]}
    ]
    mock_f = MagicMock()
    mock_f.__enter__.return_value = mock_f
    mock_file.return_value = mock_f

    with patch(
        "src.card_logic.export_draft_to_json", return_value='{"mock": "data"}'
    ) as mock_export:
        menu_bar._export_json()

        mock_export.assert_called_once()
        mock_f.write.assert_called_once_with('{"mock": "data"}')
        mock_msg.assert_called_once()

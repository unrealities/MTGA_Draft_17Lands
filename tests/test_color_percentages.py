import pytest
import json
import tkinter
from unittest.mock import MagicMock, patch
from src.dataset import Dataset
from src.log_scanner import ArenaScanner
from src.overlay import Overlay
from src.configuration import Configuration, Settings, Features


def test_dropdown_percentage_mapping_order_invariance(tmp_path):
    # 1. Setup mock data
    dummy_cards = {
        str(i): {"name": f"c{i}", "deck_colors": {"All Decks": {"gihwr": 0.0}}}
        for i in range(101)
    }
    mock_data = {
        "meta": {"version": 2, "start_date": "2024-01-01", "end_date": "2024-01-02"},
        "color_ratings": {"GW": 57.7, "RW": 55.0},
        "card_ratings": dummy_cards,
    }
    data_file = tmp_path / "test_set_Data.json"
    with open(data_file, "w") as f:
        json.dump(mock_data, f)

    # 2. Setup UI environment
    root = tkinter.Tk()
    try:
        conf = Configuration(
            settings=Settings(filter_format="Colors", ui_size="100%"),
            features=Features(hotkey_enabled=False),
        )

        with patch("src.overlay.read_configuration", return_value=(conf, True)), patch(
            "src.overlay.LimitedSets.retrieve_limited_sets"
        ), patch(
            "src.overlay.ArenaScanner.retrieve_data_sources",
            return_value={"Source": str(data_file)},
        ), patch(
            "os.path.getsize", return_value=1000
        ), patch(
            "os.stat"
        ) as mock_stat:

            mock_stat.return_value.st_mtime = 1000

            # Initialize app
            app = Overlay(MagicMock(file="fake.log", data=None, step=False))

            # Trigger load
            app.data_source_selection.set("Source")
            app._Overlay__update_draft_data()
            app._Overlay__update_column_options()

            root.update()

            # 3. Verify labels
            menu = app.deck_colors_options["menu"]
            labels = [menu.entrycget(i, "label") for i in range(menu.index("end") + 1)]

            assert "WG (57.7%)" in labels
            assert "WR (55.0%)" in labels

    finally:
        root.destroy()

import pytest
from unittest.mock import MagicMock, patch
from src.notifications import Notifications
from src.configuration import Configuration


@pytest.fixture
def config():
    c = Configuration()
    c.settings.update_notifications_enabled = True
    c.card_data.latest_dataset = "M10_PremierDraft_All_Data.json"
    return c


@pytest.fixture
def notifications(config):
    mock_expansions = MagicMock()
    mock_expansions.data = {"Outlaws": MagicMock(seventeenlands=["OTJ"])}

    return Notifications(
        root=MagicMock(),
        expansions=mock_expansions,
        configuration=config,
        dataset_window=MagicMock(),
    )


def test_check_for_updates(notifications):
    with patch.object(notifications, "check_arena_log", return_value=True):
        assert notifications.check_for_updates() == True

    with patch.object(notifications, "check_arena_log", return_value=False):
        with patch.object(notifications, "check_dataset") as mock_check_dataset:
            assert notifications.check_for_updates() == True
            mock_check_dataset.assert_called()


def test_prompt_missing_dataset(notifications):
    with patch("tkinter.messagebox.askyesno", return_value=True):
        notifications.prompt_missing_dataset("OTJ", "PremierDraft")

        notifications.root.event_generate.assert_called_with("<<ShowDataTab>>")
        notifications.dataset_window.enter.assert_called()

        args = notifications.dataset_window.enter.call_args[0][0]
        assert args.draft_set == "OTJ"
        assert args.draft == "PremierDraft"


def test_update_latest_dataset(notifications):
    with patch("src.notifications.write_configuration") as mock_write:
        notifications.update_latest_dataset("/path/to/New_Dataset.json")
        assert (
            notifications.configuration.card_data.latest_dataset == "New_Dataset.json"
        )
        mock_write.assert_called_once()


def test_check_arena_log(notifications):
    notifications.configuration.settings.arena_log_location = ""
    assert notifications.check_arena_log() == True

    notifications.configuration.settings.arena_log_location = "path/to/log.txt"
    assert notifications.check_arena_log() == False


def test_check_dataset(notifications):
    # Patch threading.Thread directly since it's locally imported
    with patch("threading.Thread.start") as mock_start:
        notifications.check_dataset()
        mock_start.assert_called_once()


@patch("src.dataset_updater.DatasetUpdater")
def test_update_dataset(mock_updater_cls, notifications):
    # Patch DatasetUpdater from its source since it's locally imported
    mock_instance = mock_updater_cls.return_value
    notifications.update_dataset()
    mock_instance.sync_datasets.assert_called_once()

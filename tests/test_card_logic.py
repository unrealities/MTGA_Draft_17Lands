import pytest
import os
import json
from src import constants
from src.set_metrics import SetMetrics
from src.configuration import Configuration, Settings
from src.card_logic import CardResult
from src.dataset import Dataset
from src.tier_list import TierList, Meta, Rating
from unittest.mock import MagicMock
from src.card_logic import export_draft_to_csv, export_draft_to_json

# 17Lands OTJ data from 2024-4-16 to 2024-5-3
OTJ_PREMIER_SNAPSHOT = os.path.join(
    os.getcwd(), "tests", "data", "OTJ_PremierDraft_Data_2024_5_3.json"
)

TEST_TIER_LIST = {
    "TIER0": TierList(
        meta=Meta(collection_date="", label="", set="", version=3),
        ratings={
            "Push // Pull": Rating(rating="C+", comment=""),
            "Etali, Primal Conqueror": Rating(rating="A+", comment=""),
            "Virtue of Persistence": Rating(rating="A+", comment=""),
            "Consign // Oblivion": Rating(rating="C+", comment=""),
            "The Mightstone and Weakstone": Rating(rating="B-", comment=""),
            "Invasion of Gobakhan": Rating(rating="B+", comment=""),
        },
    )
}

TIER_TESTS = [
    ([{"name": "Push // Pull"}], "C+"),
    ([{"name": "Consign /// Oblivion"}], "C+"),
    ([{"name": "Etali, Primal Conqueror"}], "A+"),
    ([{"name": "Invasion of Gobakhan"}], "B+"),
    ([{"name": "The Mightstone and Weakstone"}], "B-"),
    ([{"name": "Virtue of Persistence"}], "A+"),
    ([{"name": "Fake Card"}], "NA"),
]

OTJ_GRADE_TESTS = [
    (
        "Colossal Rattlewurm",
        "All Decks",
        constants.DATA_FIELD_GIHWR,
        constants.LETTER_GRADE_A_MINUS,
    ),
    (
        "Colossal Rattlewurm",
        "All Decks",
        constants.DATA_FIELD_OHWR,
        constants.LETTER_GRADE_A_MINUS,
    ),
    (
        "Colossal Rattlewurm",
        "All Decks",
        constants.DATA_FIELD_GPWR,
        constants.LETTER_GRADE_B_PLUS,
    ),
    (
        "Colossal Rattlewurm",
        "WG",
        constants.DATA_FIELD_GIHWR,
        constants.LETTER_GRADE_A_MINUS,
    ),
    (
        "Colossal Rattlewurm",
        "WG",
        constants.DATA_FIELD_OHWR,
        constants.LETTER_GRADE_B_PLUS,
    ),
    (
        "Colossal Rattlewurm",
        "WG",
        constants.DATA_FIELD_GPWR,
        constants.LETTER_GRADE_B_PLUS,
    ),
]


@pytest.fixture(name="card_result", scope="module")
def fixture_card_result():
    return CardResult(SetMetrics(None), TEST_TIER_LIST, Configuration(), 1)


@pytest.fixture(name="otj_premier", scope="module")
def fixture_otj_premier():
    dataset = Dataset()
    dataset.open_file(OTJ_PREMIER_SNAPSHOT)
    set_metrics = SetMetrics(dataset, 2)

    return set_metrics, dataset


# The card data is pulled from the JSON set files downloaded from 17Lands, excluding the fake card
@pytest.mark.parametrize("card_list, expected_tier", TIER_TESTS)
def test_tier_results(card_result, card_list, expected_tier):
    # Go through a list of non-standard cards and confirm that the CardResults class is producing the expected result
    result_list = card_result.return_results(card_list, ["All Decks"], ["TIER0"])

    assert result_list[0]["results"][0] == expected_tier


@pytest.mark.parametrize("card_name, colors, field, expected_grade", OTJ_GRADE_TESTS)
def test_otj_grades(otj_premier, card_name, colors, field, expected_grade):
    metrics, dataset = otj_premier
    data_list = dataset.get_data_by_name([card_name])
    assert data_list

    config = Configuration(
        settings=Settings(result_format=constants.RESULT_FORMAT_GRADE)
    )
    results = CardResult(metrics, None, config, 2)
    card_data = data_list[0]
    result_list = results.return_results([card_data], [colors], [field])

    assert result_list[0]["results"][0] == expected_grade


def test_export_draft_to_csv():
    # Mock History
    history = [
        {"Pack": 1, "Pick": 1, "Cards": ["123", "789"]},
    ]

    # Mock Picked Cards (List of lists)
    # Pack 1, Pick 1 was "123"
    picked_cards = [["123"]]

    # Mock Dataset
    mock_dataset = MagicMock()
    mock_dataset.get_data_by_id.side_effect = [
        [
            {constants.DATA_FIELD_NAME: "Card A", constants.DATA_FIELD_CMC: 2},
            {constants.DATA_FIELD_NAME: "Card B", constants.DATA_FIELD_CMC: 3},
        ]
    ]

    csv_output = export_draft_to_csv(history, mock_dataset, picked_cards)

    lines = csv_output.strip().split("\n")
    header = lines[0].split(",")
    assert "Picked" in header

    # Row 1 (Card A, ID 123) should be picked (1)
    row1 = lines[1].split(",")
    assert row1[2] == "1"
    assert "Card A" in lines[1]

    # Row 2 (Card B, ID 789) should not be picked (0)
    row2 = lines[2].split(",")
    assert row2[2] == "0"
    assert "Card B" in lines[2]


def test_export_draft_to_json():
    # ... similar update ...
    history = [{"Pack": 1, "Pick": 1, "Cards": ["123"]}]
    picked_cards = [["123"]]

    mock_dataset = MagicMock()
    mock_dataset.get_data_by_id.return_value = [
        {constants.DATA_FIELD_NAME: "Card A", constants.DATA_FIELD_CMC: 2}
    ]

    json_output = export_draft_to_json(history, mock_dataset, picked_cards)
    data = json.loads(json_output)

    assert data[0]["Cards"][0]["Picked"] == True


def test_export_draft_to_csv_edge_cases():
    """Verify export handles missing picks, unicode names, and empty stats."""
    history = [{"Pack": 1, "Pick": 1, "Cards": ["999"]}]
    # Picked cards map is empty (user disconnect? parsing error?)
    picked_cards = []

    mock_dataset = MagicMock()
    # Mock a card with unicode and missing stats
    mock_dataset.get_data_by_id.return_value = [
        {
            constants.DATA_FIELD_NAME: "Æther Potion",
            # Missing CMC, Colors, etc.
            constants.DATA_FIELD_DECK_COLORS: {},  # Empty stats
        }
    ]

    csv_output = export_draft_to_csv(history, mock_dataset, picked_cards)

    lines = csv_output.strip().split("\n")
    assert len(lines) == 2
    row = lines[1].split(",")

    # 1. Picked should be 0 (False) safely
    assert row[2] == "0"

    # 2. Name should be preserved (CSV module handles quotes/encoding)
    assert "Æther Potion" in lines[1]

    # 3. Stats should be empty strings/zeros, not crash
    # ALSA is index 15
    assert row[15] == ""

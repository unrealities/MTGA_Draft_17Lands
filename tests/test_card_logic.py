import pytest
import os
import json
from src import constants
from src.set_metrics import SetMetrics
from src.configuration import Configuration, Settings
from src.card_logic import CardResult

# 17Lands OTJ data from 2024-4-16 to 2024-5-3
OTJ_PREMIER_SNAPSHOT = os.path.join(os.getcwd(), "tests", "data","OTJ_PremierDraft_Data_2024_5_3.json")

# Cards pulled from various tier lists that were downloaded using the chrome plugin
TEST_TIER_LIST = {
    "TIER0" : {
        "meta": {
            "collection_date": "",
            "label": "",
            "set": "",
            "version": 3
        },
        "ratings":{
            #Split sample
            "Push // Pull": {
                "rating": "C+",
                "comment": ""
            },
            #Double-sided sample
            "Etali, Primal Conqueror": {
                "rating": "A+",
                "comment": ""
            },
            #Adventure sample
            "Virtue of Persistence": {
                "rating": "A+",
                "comment": ""
            },
            #Aftermath sample
            "Consign // Oblivion": {
                "rating": "C+",
                "comment": ""
            },
            #Meld sample
            "The Mightstone and Weakstone": {
                "rating": "B-",
                "comment": ""
            },
            #Battle sample
            "Invasion of Gobakhan": {
                "rating": "B+",
                "comment": ""
            },
        }
    }
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
    ("Colossal Rattlewurm", "All Decks", constants.DATA_FIELD_GIHWR, constants.LETTER_GRADE_A_MINUS),
    ("Colossal Rattlewurm", "All Decks", constants.DATA_FIELD_OHWR, constants.LETTER_GRADE_A_MINUS),
    ("Colossal Rattlewurm", "All Decks", constants.DATA_FIELD_GPWR, constants.LETTER_GRADE_B_PLUS),
    ("Colossal Rattlewurm", "WG", constants.DATA_FIELD_GIHWR, constants.LETTER_GRADE_A_MINUS),
    ("Colossal Rattlewurm", "WG", constants.DATA_FIELD_OHWR, constants.LETTER_GRADE_B_PLUS),
    ("Colossal Rattlewurm", "WG", constants.DATA_FIELD_GPWR, constants.LETTER_GRADE_B_PLUS),
]

@pytest.fixture(name="card_result", scope="module")
def fixture_card_result():
    return CardResult(SetMetrics(None), TEST_TIER_LIST, Configuration(), 1)
    
@pytest.fixture(name="otj_premier", scope="module")
def fixture_otj_premier():
    with open(OTJ_PREMIER_SNAPSHOT, 'r', encoding="utf-8", errors="replace") as json_file:
        set_data = json.loads(json_file.read())
        set_metrics = SetMetrics(set_data, 2)
        # Remove the arena ID part of the dictionary and make the card name the key
        transformed_data = {v["name"]: v for v in set_data["card_ratings"].values()}
        
    return set_metrics, transformed_data
    
#The card data is pulled from the JSON set files downloaded from 17Lands, excluding the fake card
@pytest.mark.parametrize("card_list, expected_tier",TIER_TESTS)
def test_tier_results(card_result, card_list, expected_tier):
    # Go through a list of non-standard cards and confirm that the CardResults class is producing the expected result
    result_list = card_result.return_results(card_list, ["All Decks"], {"Column1" : "TIER0"})
    
    assert result_list[0]["results"][0] == expected_tier
    
@pytest.mark.parametrize("card_name, colors, field, expected_grade", OTJ_GRADE_TESTS)
def test_otj_grades(otj_premier, card_name, colors, field, expected_grade):
    metrics, transformed_data = otj_premier
    assert card_name in transformed_data
    
    config = Configuration(settings=Settings(result_format=constants.RESULT_FORMAT_GRADE))
    results = CardResult(metrics, None, config, 2)
    card_data = transformed_data[card_name]
    result_list = results.return_results([card_data], [colors],  {"Column1" : field})
    
    assert result_list[0]["results"][0] == expected_grade
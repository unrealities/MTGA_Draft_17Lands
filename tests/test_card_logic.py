import pytest
from src.card_logic import CardResult, SetMetrics
from src.configuration import Configuration

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

@pytest.fixture
def card_result():
    return CardResult(SetMetrics(), TEST_TIER_LIST, Configuration(), 1)
    
#The card data is pulled from the JSON set files downloaded from 17Lands, excluding the fake card
@pytest.mark.parametrize("card_list, expected_tier",[
        ([{"name": "Push // Pull"}], "C+"),
        ([{"name": "Consign /// Oblivion"}], "C+"),
        ([{"name": "Etali, Primal Conqueror"}], "A+"),
        ([{"name": "Invasion of Gobakhan"}], "B+"),
        ([{"name": "The Mightstone and Weakstone"}], "B-"),
        ([{"name": "Virtue of Persistence"}], "A+"),
        ([{"name": "Fake Card"}], "NA"),
    ]
)

def test_tier_results(card_result, card_list, expected_tier):
    #Go through a list of non-standard cards and confirm that the CardResults class is producing the expected result
    result_list = card_result.return_results(card_list, ["All Decks"], {"Column1" : "TIER0"})
    
    assert result_list[0]["results"][0] == expected_tier

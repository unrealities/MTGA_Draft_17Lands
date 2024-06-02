import pytest
import os
from src.dataset import Dataset
from src.utils import Result

# 17Lands OTJ data from 2024-4-16 to 2024-5-3
OTJ_PREMIER_SNAPSHOT = os.path.join(os.getcwd(), "tests", "data","OTJ_PremierDraft_Data_2024_5_3.json")

OTJ_GET_IDS_BY_NAME_TESTS_PASS = [
    (["Rest in Peace", "Thoughtseize", "Djinn of Fool's Fall", "Slick Sequence"], False, ["87050", "90718", "90389", "90579"]),
    (["Rest in Peace", "Thoughtseize", "Djinn of Fool's Fall", "Slick Sequence"], True, [87050, 90718, 90389, 90579]),
    (["Brazen Borrower", "Fake Card", "Mentor of the Meek", "Crime /// Punishment"], False, ["90652", "90737"]),
    (["Brazen Borrower", "Fake Card", "Mentor of the Meek", "Crime /// Punishment"], True, [90652, 90737]),
    (["Consign /// Oblivion", "Shock", "Enlisted Wurm"], False, []),
    (["Consign /// Oblivion", "Shock", "Enlisted Wurm"], True, []),
    ([], False, []),
    ([], True, []),
]

OTJ_GET_NAMES_BY_ID_TESTS_PASS = [
    (["73807", "73905", "90389", "90579"], ["Rest in Peace", "Thoughtseize", "Djinn of Fool's Fall", "Slick Sequence"]),
    ([73807, 73905, 90389, 90579], ["Rest in Peace", "Thoughtseize", "Djinn of Fool's Fall", "Slick Sequence"]),
    (["70186", "90737"], ["Brazen Borrower", "Crime /// Punishment"]),
    ([70186, 90737], ["Brazen Borrower", "Crime /// Punishment"]),
    (["73807", "73905", "ABCD", 90579], ["Rest in Peace", "Thoughtseize", "Slick Sequence"]),
    (["73807", "73905", "", 90579], ["Rest in Peace", "Thoughtseize", "Slick Sequence"]),
    ([], []),
]

OTJ_GET_DATA_BY_ID_TEST_PASS = [
    (["73807"], [{"name": "Rest in Peace", "cmc": 2, "mana_cost": "{1}{W}"}]),
    ([73807], [{"name": "Rest in Peace", "cmc": 2, "mana_cost": "{1}{W}"}]),
    ([90389], [{"name": "Djinn of Fool's Fall", "cmc": 5, "mana_cost": "{4}{U}"}]),
    (["73905", 90389], [{"name": "Thoughtseize", "cmc": 1, "mana_cost": "{B}"},{"name": "Djinn of Fool's Fall", "cmc": 5, "mana_cost": "{4}{U}"}]),
    ([], []),
]

OTJ_GET_DATA_BY_NAME_TEST_PASS = [
    (["Rest in Peace"], [{"name": "Rest in Peace", "cmc": 2, "mana_cost": "{1}{W}"}]),
    (["Djinn of Fool's Fall"], [{"name": "Djinn of Fool's Fall", "cmc": 5, "mana_cost": "{4}{U}"}]),
    (["Thoughtseize", "Djinn of Fool's Fall"], [{"name": "Thoughtseize", "cmc": 1, "mana_cost": "{B}"},{"name": "Djinn of Fool's Fall", "cmc": 5, "mana_cost": "{4}{U}"}]),
    ([], []),
]

@pytest.fixture(name="otj_dataset", scope="module")
def fixture_otj_dataset():
    dataset = Dataset()
    dataset.open_file(OTJ_PREMIER_SNAPSHOT)
    return dataset
    
@pytest.mark.parametrize("name_list, return_int, expected_ids", OTJ_GET_IDS_BY_NAME_TESTS_PASS)
def test_otj_get_ids_by_name(otj_dataset, name_list, return_int, expected_ids):
    assert otj_dataset.get_ids_by_name(name_list, return_int) == expected_ids
    
    
@pytest.mark.parametrize("id_list, expected_names", OTJ_GET_NAMES_BY_ID_TESTS_PASS)
def test_otj_get_names_by_id(otj_dataset, id_list,  expected_names):
    assert otj_dataset.get_names_by_id(id_list) == expected_names
    
@pytest.mark.parametrize("id_list, expected_data", OTJ_GET_DATA_BY_ID_TEST_PASS)
def test_otj_get_data_by_id(otj_dataset, id_list, expected_data):
    data_list = otj_dataset.get_data_by_id(id_list)
    assert len(data_list) == len(expected_data)
    
    for i in range(len(data_list)):
        # Compare the matching fields, ignoring all of the other fields
        assert all(data_list[i].get(key) == expected_data[i].get(key) for key in data_list[i].keys() & expected_data[i].keys()), f"Get Data by ID: Collected:{data_list[i]}, Expected:{expected_data[i]}"
    
@pytest.mark.parametrize("name_list, expected_data", OTJ_GET_DATA_BY_NAME_TEST_PASS)
def test_otj_get_data_by_name(otj_dataset, name_list, expected_data):
    data_list = otj_dataset.get_data_by_name(name_list)
    assert len(data_list) == len(expected_data)
    
    for i in range(len(data_list)):
        # Compare the matching fields, ignoring all of the other fields
        assert all(data_list[i].get(key) == expected_data[i].get(key) for key in data_list[i].keys() & expected_data[i].keys()), f"Get Data by Name: Collected:{data_list[i]}, Expected:{expected_data[i]}"
    
def test_open_file_fail():
    dataset = Dataset()
    assert Result.ERROR_MISSING_FILE == dataset.open_file("fake_location")
    


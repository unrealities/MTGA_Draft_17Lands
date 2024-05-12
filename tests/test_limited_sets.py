import pytest
import os
import json
from src.limited_sets import LimitedSets, SetInfo, SetDictionary, LIMITED_SETS_VERSION

# Test data
SETS_FILE_LOCATION = os.path.join(os.getcwd(), "Temp", "unit_test_sets.json")
CHECKED_SETS_COMBINED = {
    "Outlaws of Thunder Junction" : SetInfo(arena=["ALL"],scryfall=[],seventeenlands=["OTJ"]),
    "Wilds of Eldraine" : SetInfo(arena=["ALL"],scryfall=[],seventeenlands=["WOE"]),
    "March of the Machine" : SetInfo(arena=["ALL"],scryfall=[],seventeenlands=["MOM"]),
    "March of the Machine: The Aftermath": SetInfo(arena=["ALL"],scryfall=[],seventeenlands=["MAT"]),
    "Shadows over Innistrad Remastered": SetInfo(arena=["ALL"],scryfall=[],seventeenlands=["SIR"]),
    "Phyrexia: All Will Be One": SetInfo(arena=["ALL"],scryfall=[],seventeenlands=["ONE"]), 
    "Alchemy: Phyrexia": SetInfo(arena=["ALL"],scryfall=[],seventeenlands=["Y23ONE"]), 
    "The Brothers' War": SetInfo(arena=["ALL"],scryfall=[],seventeenlands=["BRO"]), 
    "Alchemy: The Brothers' War": SetInfo(arena=["ALL"],scryfall=[],seventeenlands=["Y23BRO"]),
    "CORE": SetInfo(arena=["ALL"],scryfall=[],seventeenlands=["CORE"],start_date="2021-03-26"),
}

CHECKED_SETS_SCRYFALL = {
    "Outlaws of Thunder Junction" : SetInfo(arena=["ALL"],scryfall=[],seventeenlands=["OTJ"]),
    "Wilds of Eldraine" : SetInfo(arena=["ALL"],scryfall=[],seventeenlands=["WOE"]),
    "March of the Machine" : SetInfo(arena=["ALL"],scryfall=[],seventeenlands=["MOM"]),
    "March of the Machine: The Aftermath": SetInfo(arena=["ALL"],scryfall=[],seventeenlands=["MAT"]),
    "Shadows over Innistrad Remastered": SetInfo(arena=["ALL"],scryfall=[],seventeenlands=["SIR"]),
    "Phyrexia: All Will Be One": SetInfo(arena=["ALL"],scryfall=[],seventeenlands=["ONE"]), 
    "Alchemy: Phyrexia": SetInfo(arena=["ALL"],scryfall=[],seventeenlands=["Y23ONE"]), 
    "The Brothers' War": SetInfo(arena=["ALL"],scryfall=[],seventeenlands=["BRO"]), 
    "Alchemy: The Brothers' War": SetInfo(arena=["ALL"],scryfall=[],seventeenlands=["Y23BRO"]),
}

CHECKED_SETS_17LANDS = {
    "OTJ" : SetInfo(arena=["ALL"],scryfall=[],seventeenlands=["OTJ"],start_date="2024-04-16"),
    "WOE" : SetInfo(arena=["ALL"],scryfall=[],seventeenlands=["WOE"],start_date="2023-09-05"),
    "MOM" : SetInfo(arena=["ALL"],scryfall=[],seventeenlands=["MOM"],start_date="2023-04-18"),
    "MAT": SetInfo(arena=["ALL"],scryfall=[],seventeenlands=["MAT"],start_date="2023-05-09"),
    "SIR": SetInfo(arena=["ALL"],scryfall=[],seventeenlands=["SIR"],start_date="2023-03-21"),
    "ONE": SetInfo(arena=["ALL"],scryfall=[],seventeenlands=["ONE"],start_date="2023-02-07"),
    "Y23ONE": SetInfo(arena=["ALL"],scryfall=[],seventeenlands=["Y23ONE"],start_date="2023-02-28"),
    "BRO": SetInfo(arena=["ALL"],scryfall=[],seventeenlands=["BRO"],start_date="2022-11-15"),
    "Y23BRO": SetInfo(arena=["ALL"],scryfall=[],seventeenlands=["Y23BRO"],start_date="2022-12-13"),
}

TEST_SETS = {
    "Test1" : SetInfo(arena=["aDfafdfasdf"],scryfall=[],seventeenlands=["ggdgdgsge"],start_date="111111111"),
    "Test2" : SetInfo(arena=[""],scryfall=["12345abdf"],seventeenlands=[""]),
}

INVALID_SETS = {
    "Test1" : {"arena" : "aDfafdfasdf", "scryfall" : []},
    "Test2" : {"arena" : [""], "scryfall" : [12345]},
    "Test3" : {"start_date" : ["111111111"]},
}

OLD_SETS_FORMAT = {
    "WOE": SetInfo(arena=["WOE", "WOT"], scryfall=["WOE", "WOT"], seventeenlands=["WOE"]),
    "OTJ": SetInfo(arena=["OTJ", "BIG", "OTP", "SPG"], scryfall=["OTJ", "BIG", "OTP", "SPG"], seventeenlands=["OTJ"])
}

@pytest.fixture
def limited_sets():
    return LimitedSets(SETS_FILE_LOCATION)

def check_for_sets(sets_data, check_data):
    for key in check_data:
        assert key in sets_data
        assert check_data[key] == sets_data[key]

def test_retrieve_limited_sets_success(limited_sets):
    if os.path.exists(SETS_FILE_LOCATION):
        os.remove(SETS_FILE_LOCATION)
        assert os.path.exists(SETS_FILE_LOCATION) == False
    
    output_sets = limited_sets.retrieve_limited_sets()
    
    assert type(output_sets) == SetDictionary
    assert len(output_sets.data) > 0
    assert os.path.exists(SETS_FILE_LOCATION)
    
    check_for_sets(output_sets.data, CHECKED_SETS_COMBINED)

def test_retrieve_scryfall_sets_success(limited_sets):
    output_sets = limited_sets.retrieve_scryfall_sets()
    
    assert type(output_sets) == SetDictionary
    assert len(output_sets.data) > 0
    
    check_for_sets(output_sets.data, CHECKED_SETS_SCRYFALL)

def test_retrieve_17lands_sets_success(limited_sets):
    output_sets = limited_sets.retrieve_17lands_sets()
    
    assert type(output_sets) == SetDictionary
    assert len(output_sets.data) > 0
    
    check_for_sets(output_sets.data, CHECKED_SETS_17LANDS)

def test_write_sets_file_success(limited_sets):
    if os.path.exists(SETS_FILE_LOCATION):
        os.remove(SETS_FILE_LOCATION)
        assert os.path.exists(SETS_FILE_LOCATION) == False
    
    test_data = SetDictionary(data=CHECKED_SETS_COMBINED, version=LIMITED_SETS_VERSION)
    
    result = limited_sets.write_sets_file(test_data)
    
    assert result == True
    assert os.path.exists(SETS_FILE_LOCATION) == True

def test_read_sets_file_success(limited_sets):
    assert os.path.exists(SETS_FILE_LOCATION) == True
    
    output_sets, result = limited_sets.read_sets_file()
    
    assert result == True
    assert type(output_sets) == SetDictionary
    assert len(output_sets.data) > 0
    
    check_for_sets(output_sets.data, CHECKED_SETS_COMBINED)
    
def test_write_sets_file_append_success(limited_sets):
    if os.path.exists(SETS_FILE_LOCATION):
        os.remove(SETS_FILE_LOCATION)
        assert os.path.exists(SETS_FILE_LOCATION) == False
    
    #Remove checked sets
    test_data = SetDictionary(data=CHECKED_SETS_COMBINED, version=LIMITED_SETS_VERSION)
    del test_data.data["March of the Machine"]
    del test_data.data["Alchemy: The Brothers' War"]
    
    #Add a test set
    for key, value in TEST_SETS.items():
        test_data.data[key] = value
    
    result = limited_sets.write_sets_file(test_data)
    
    assert result == True
    assert os.path.exists(SETS_FILE_LOCATION) == True
    
    output_sets = limited_sets.retrieve_limited_sets()
    
    assert type(output_sets) == SetDictionary
    assert len(output_sets.data) > 0
    
    check_for_sets(output_sets.data, CHECKED_SETS_COMBINED)
    
    #Confirm that the added test sets remain
    check_for_sets(output_sets.data, TEST_SETS)
    
def test_write_sets_file_fail_wrong_type(limited_sets):
    if os.path.exists(SETS_FILE_LOCATION):
        os.remove(SETS_FILE_LOCATION)
        assert os.path.exists(SETS_FILE_LOCATION) == False
                                  
    test_data = {}
    
    result = limited_sets.write_sets_file(test_data)
    
    assert result == False
    assert os.path.exists(SETS_FILE_LOCATION) == False
    
def test_read_sets_file_fail_invalid_fields(limited_sets):
    if os.path.exists(SETS_FILE_LOCATION):
        os.remove(SETS_FILE_LOCATION)
        assert os.path.exists(SETS_FILE_LOCATION) == False
                                  
    test_data = INVALID_SETS
    
    expected_result = SetDictionary(version=LIMITED_SETS_VERSION)
    
    with open(SETS_FILE_LOCATION, 'w', encoding="utf-8", errors="replace") as file:
        json.dump(test_data, file, ensure_ascii=False, indent=4)

    output_sets, result = limited_sets.read_sets_file()
    
    assert result == False
    assert output_sets == expected_result 

def test_replace_old_sets(limited_sets):
    """
    Verify that the old sets file is overwritten
    """
    test_data = SetDictionary(data=OLD_SETS_FORMAT)
    
    # Create a file with old entries
    assert limited_sets.write_sets_file(test_data) is True
    
    # Read the file back
    output_sets = limited_sets.retrieve_limited_sets()
    
    # Verify that the file now has the correct content
    check_for_sets(output_sets.data, CHECKED_SETS_COMBINED)
    
    # Verify the version
    assert output_sets.version == LIMITED_SETS_VERSION
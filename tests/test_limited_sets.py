import pytest
import os
import json
import datetime
from unittest.mock import patch
from src.limited_sets import (
    LimitedSets,
    SetInfo,
    SetDictionary,
    LIMITED_SETS_VERSION
)

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

MOCK_URL_RESPONSE_17LANDS_FILTERS = b'''{
    "expansions":[
        "MH3",
        "OTJ",
        "Y24OTJ",
        "MKM",
        "Y24MKM",
        "LCI",
        "Y24LCI",
        "WOE",
        "Y24WOE",
        "LTR",
        "MOM",
        "MAT",
        "SIR",
        "ONE",
        "Y23ONE",
        "BRO",
        "Y23BRO",
        "DMU",
        "Y23DMU",
        "HBG",
        "SNC",
        "Y22SNC",
        "NEO",
        "DBL",
        "VOW",
        "RAVM",
        "MID",
        "AFR",
        "STX",
        "CORE",
        "KHM",
        "KLR",
        "ZNR",
        "AKR",
        "M21",
        "IKO",
        "THB",
        "ELD",
        "Ravnica",
        "M20",
        "WAR",
        "M19",
        "DOM",
        "RIX",
        "GRN",
        "RNA",
        "KTK",
        "XLN",
        "Cube",
        "Chaos"
    ],
    "start_dates":{
        "2X2":"2022-07-08T00:00:00Z",
        "2XM":"2000-03-01T00:00:00Z",
        "AFR":"2021-07-08T00:00:00Z",
        "AKR":"2020-08-12T00:00:00Z",
        "BRO":"2022-11-15T15:00:00Z",
        "CLB":"2022-06-10T00:00:00Z",
        "CORE":"2021-03-26T00:00:00Z",
        "Chaos":"2024-06-03T18:31:12.496525Z",
        "Cube":"2024-06-03T18:31:12.496522Z",
        "DBL":"2022-01-28T00:00:00Z",
        "DMR":"2023-01-13T00:00:00Z",
        "DMU":"2022-09-01T15:00:00Z",
        "DOM":"2019-03-04T00:00:00Z",
        "ELD":"2019-09-23T00:00:00Z",
        "GRN":"2019-02-15T00:00:00Z",
        "HBG":"2022-07-07T15:00:00Z",
        "IKO":"2020-04-14T00:00:00Z",
        "KHM":"2021-01-27T00:00:00Z",
        "KLR":"2020-11-11T00:00:00Z",
        "KTK":"2014-09-26T00:00:00Z",
        "LCI":"2023-11-14T15:00:00Z",
        "LTR":"2023-06-20T15:00:00Z",
        "M19":"2019-03-29T00:00:00Z",
        "M20":"2019-06-29T00:00:00Z",
        "M21":"2020-06-24T00:00:00Z",
        "MAT":"2023-05-09T15:00:00Z",
        "MH1":"2000-04-01T00:00:00Z",
        "MH2":"2000-05-01T00:00:00Z",
        "MH3":"2024-06-11T15:00:00Z",
        "MID":"2021-09-16T00:00:00Z",
        "MKM":"2024-02-06T00:00:00Z",
        "MOM":"2023-04-18T15:00:00Z",
        "NEO":"2022-02-10T00:00:00Z",
        "ONE":"2023-02-07T15:00:00Z",
        "OTJ":"2024-04-16T15:00:00Z",
        "RAVM":"2021-10-29T00:00:00Z",
        "RIX":"2019-03-01T00:00:00Z",
        "RNA":"2019-01-17T00:00:00Z",
        "ROE":"2010-04-23T00:00:00Z",
        "Ravnica":"2024-06-03T18:31:12.496483Z",
        "SIR":"2023-03-21T15:00:00Z",
        "SNC":"2022-04-28T00:00:00Z",
        "STX":"2021-04-15T00:00:00Z",
        "THB":"2020-01-14T00:00:00Z",
        "TSR":"2000-02-01T00:00:00Z",
        "VOW":"2021-11-11T00:00:00Z",
        "WAR":"2019-04-22T00:00:00Z",
        "WOE":"2023-09-05T15:00:00Z",
        "XLN":"2000-06-01T00:00:00Z",
        "Y22SNC":"2022-06-02T15:00:00Z",
        "Y23BRO":"2022-12-13T15:00:00Z",
        "Y23DMU":"2022-10-06T15:00:00Z",
        "Y23ONE":"2023-02-28T15:00:00Z",
        "Y24LCI":"2023-12-05T15:00:00Z",
        "Y24MKM":"2024-03-05T15:00:00Z",
        "Y24OTJ":"2024-05-07T15:00:00Z",
        "Y24WOE":"2023-10-10T15:00:00Z",
        "ZNR":"2020-09-16T00:00:00Z"
    }
}'''


MOCK_URL_RESPONSE_SCRYFALL_SETS = b'''{
    "object":"list","has_more":false,"data": [
        {
            "object":"set",
            "code":"mh3",
            "arena_code":"mh3",
            "digital":true,
            "name":"Modern Horizons 3",
            "set_type":"draft_innovation"
        },
        {
            "object":"set",
            "code":"otj",
            "arena_code":"otj",
            "digital":true,
            "name":"Outlaws of Thunder Junction",
            "set_type":"expansion"
        },
        {
            "object":"set",
            "code":"woe",
            "arena_code":"woe",
            "digital":true,
            "name":"Wilds of Eldraine",
            "set_type":"expansion"
        },
        {
            "object":"set",
            "code":"mom",
            "arena_code":"mom",
            "digital":true,
            "name":"March of the Machine",
            "set_type":"expansion"
        },
        {
            "object":"set",
            "code":"mom",
            "arena_code":"mom",
            "digital":true,
            "name":"March of the Machine",
            "set_type":"expansion"
        },
        {
            "object":"set",
            "code":"mat",
            "arena_code":"mat",
            "digital":true,
            "name":"March of the Machine: The Aftermath",
            "set_type":"expansion"
        },
        {
            "object":"set",
            "code":"sir",
            "arena_code":"sir",
            "digital":true,
            "name":"Shadows over Innistrad Remastered",
            "set_type":"masters"
        },
        {
            "object":"set",
            "code":"one",
            "arena_code":"one",
            "digital":true,
            "name":"Phyrexia: All Will Be One",
            "set_type":"expansion"
        },
        {
            "object":"set",
            "code":"yone",
            "digital":true,
            "parent_set_code":"one",
            "name":"Alchemy: Phyrexia",
            "block_code":"y23",
            "set_type":"alchemy"
        },
        {
            "object":"set",
            "code":"bro",
            "arena_code":"bro",
            "digital":true,
            "name":"The Brothers' War",
            "set_type":"expansion"
        },
        {
            "object":"set",
            "code":"ybro",
            "digital":true,
            "parent_set_code":"bro",
            "name":"Alchemy: The Brothers' War",
            "block_code":"y23",
            "set_type":"alchemy"
        }
    ]   
}'''

@pytest.fixture(name="limited_sets",scope="function") 
def fixture_limited_sets():
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

@patch("src.limited_sets.urllib.request.urlopen")
def test_overwrite_old_sets(mock_urlopen, limited_sets):
    """
    Verify the old sets file is overwritten
    """
    test_data = SetDictionary(data=OLD_SETS_FORMAT)

    # Create a file with old entries
    assert limited_sets.write_sets_file(test_data)

    # Mock the urlopen responses - 17Lands and then Scryfall
    mock_urlopen.return_value.read.side_effect = [MOCK_URL_RESPONSE_17LANDS_FILTERS, MOCK_URL_RESPONSE_SCRYFALL_SETS]

    # Read the file back - this will make calls to the mocked urlopen method
    output_sets = limited_sets.retrieve_limited_sets()

    # Verify that the file now has the correct content
    check_for_sets(output_sets.data, CHECKED_SETS_COMBINED)

    # Verify that the file has the new version
    assert output_sets.version == LIMITED_SETS_VERSION

    # Verify that the new special events section was added
    assert output_sets.special_events[0].label == "OpenDay1"
    assert output_sets.special_events[1].label == "OpenDay2"

@patch("src.limited_sets.urllib.request.urlopen")
def test_substitute_string_latest(mock_urlopen, limited_sets):
    """
    Verify that string '{LATEST}' gets replaced with the latest 17Lands set code
    """
    test_data = SetDictionary()
         
    # Create a file with the new special event
    assert limited_sets.write_sets_file(test_data)

    # Mock the urlopen responses - 17Lands and then Scryfall
    test_response = b'{"expansions":["MKM","OTJ"],"start_dates":{"MKM":"2024-02-06T00:00:00Z", "OTJ":"2024-04-16T15:00:00Z"}}'
    mock_urlopen.return_value.read.side_effect = [test_response, MOCK_URL_RESPONSE_SCRYFALL_SETS]

    # Read the file back - this will make calls to the mocked urlopen method
    output_sets = limited_sets.retrieve_limited_sets()

    # Verify that the set_code is updated
    assert output_sets.special_events[0].label == "OpenDay1"
    assert output_sets.special_events[0].set_code == "MKM"
    assert output_sets.special_events[1].label == "OpenDay2"
    assert output_sets.special_events[1].set_code == "MKM"

    # Mock the urlopen responses - 17Lands and then Scryfall
    # Switch the set codes
    test_response = b'{"expansions":["OTJ","MKM"],"start_dates":{"MKM":"2024-02-06T00:00:00Z", "OTJ":"2024-04-16T15:00:00Z"}}'
    mock_urlopen.return_value.read.side_effect = [test_response, MOCK_URL_RESPONSE_SCRYFALL_SETS]

    # Read the file back - this will make calls to the mocked urlopen method
    output_sets = limited_sets.retrieve_limited_sets()

    # Verify that the set_code is updated
    assert output_sets.special_events[0].label == "OpenDay1"
    assert output_sets.special_events[0].set_code == "OTJ"
    assert output_sets.special_events[1].label == "OpenDay2"
    assert output_sets.special_events[1].set_code == "OTJ"

@patch("src.limited_sets.urllib.request.urlopen")
def test_substitute_string_date_shift(mock_urlopen, limited_sets):
    """
    Verify that string '{DATESHIFT}' gets replaced with a date that is 30 days from the mocked date
    """
    test_data = SetDictionary()

    # Create a new sets file
    assert limited_sets.write_sets_file(test_data)

    # Mock the urlopen responses - 17Lands and then Scryfall
    mock_urlopen.return_value.read.side_effect = [MOCK_URL_RESPONSE_17LANDS_FILTERS, MOCK_URL_RESPONSE_SCRYFALL_SETS]
    mocked_today = datetime.date(2024, 5, 15)
    mocked_min = datetime.date.min
    expected_shift_date = "2024-04-15"

    # Read the file back - this will make calls to the mocked urlopen method and the mocked date methods
    with patch("src.limited_sets.datetime.date") as mock_date:
        # Mocked start date
        mock_date.today.return_value = mocked_today
        mock_date.min = mocked_min
        output_sets = limited_sets.retrieve_limited_sets()

    # Verify that the {DATESHIFT} response is substituted for the expected shift date 
    assert "Arena Cube" in output_sets.data
    assert output_sets.data["Arena Cube"].start_date == expected_shift_date
    


import pytest
import os
import json
from src.set_metrics import SetMetrics
from src.constants import (
    DATA_FIELD_GIHWR,
    DATA_FIELD_OHWR,
    DATA_FIELD_GPWR
)

# 17Lands MKM data from 2024-2-5 to 2024-5-3
MKM_PREMIER_SNAPSHOT = os.path.join(os.getcwd(), "tests", "data","MKM_PremierDraft_Data_2024_5_3.json")

# These values were retrieved by going to the 17Lands card data page and hovering over an occupied entry in the GIH WR column (mean and std are represented as {mean}%+-{std})
MKM_PREMIER_EXPECTED_RESULTS = [
    ("All Decks", DATA_FIELD_GIHWR, 54.6, 3.9),
    ("WU", DATA_FIELD_GIHWR, 54.1, 3.7),
    ("WB", DATA_FIELD_GIHWR, 54.8, 3.7),
    ("WR", DATA_FIELD_GIHWR, 55.8, 3.9),
    ("WG", DATA_FIELD_GIHWR, 56.0, 4.1),
    ("UB", DATA_FIELD_GIHWR, 53.7, 3.8),
    ("UR", DATA_FIELD_GIHWR, 54.8, 3.4),
    ("UG", DATA_FIELD_GIHWR, 56.4, 3.8),
    ("BR", DATA_FIELD_GIHWR, 53.6, 3.5),
    ("BG", DATA_FIELD_GIHWR, 55.2, 3.5),
    ("RG", DATA_FIELD_GIHWR, 53.9, 3.5),
    ("WUB", DATA_FIELD_GIHWR, 51.9, 3.4),
    ("WUR", DATA_FIELD_GIHWR, 53.3, 3.4),
    ("WUG", DATA_FIELD_GIHWR, 56.1, 4.0),
    ("WBR", DATA_FIELD_GIHWR, 51.7, 2.8),
    ("WBG", DATA_FIELD_GIHWR, 54.4, 3.2),
    ("WRG", DATA_FIELD_GIHWR, 53.3, 3.5),
    ("UBR", DATA_FIELD_GIHWR, 54.5, 2.8),
    ("UBG", DATA_FIELD_GIHWR, 55.2, 3.5),
    ("URG", DATA_FIELD_GIHWR, 55.3, 3.0),
    ("BRG", DATA_FIELD_GIHWR, 52.2, 2.9),
]

# 17Lands OTJ data from 2024-4-16 to 2024-5-3
OTJ_PREMIER_SNAPSHOT = os.path.join(os.getcwd(), "tests", "data","OTJ_PremierDraft_Data_2024_5_3.json")

# These values were retrieved by going to the 17Lands card data page and hovering over an occupied entry in the win rate columns (mean and std are represented as {mean}%+-{std})
OTJ_PREMIER_EXPECTED_RESULTS = [
    ("All Decks", DATA_FIELD_GIHWR, 54.7, 4.0),
    ("All Decks", DATA_FIELD_OHWR, 53.9, 4.3),
    ("All Decks", DATA_FIELD_GPWR, 53.1, 2.9),
    ("WU", DATA_FIELD_GIHWR, 53.3, 3.1),
    ("WU", DATA_FIELD_OHWR, 51.5, 3.1),
    ("WU", DATA_FIELD_GPWR, 51.2, 1.9),
    ("WB", DATA_FIELD_GIHWR, 57.4, 2.9),
    ("WB", DATA_FIELD_OHWR, 56.3, 3.1),
    ("WB", DATA_FIELD_GPWR, 55.5, 2.0),
    ("WR", DATA_FIELD_GIHWR, 54.5, 3.4),
    ("WR", DATA_FIELD_OHWR, 55.2, 3.4),
    ("WR", DATA_FIELD_GPWR, 54.3, 2.1),
    ("WG", DATA_FIELD_GIHWR, 57.5, 3.7),
    ("WG", DATA_FIELD_OHWR, 58.1, 4.2),
    ("WG", DATA_FIELD_GPWR, 57.0, 2.0),
    ("UB", DATA_FIELD_GIHWR, 55.7, 3.6),
    ("UB", DATA_FIELD_OHWR, 53.3, 3.9),
    ("UB", DATA_FIELD_GPWR, 52.7, 2.5),
    ("UR", DATA_FIELD_GIHWR, 51.9, 3.0),
    ("UR", DATA_FIELD_OHWR, 50.4, 3.4),
    ("UR", DATA_FIELD_GPWR, 49.4, 2.1),
    ("UG", DATA_FIELD_GIHWR, 55.4, 4.1),
    ("UG", DATA_FIELD_OHWR, 54.0, 3.9),
    ("UG", DATA_FIELD_GPWR, 53.6, 2.1),
    ("BR", DATA_FIELD_GIHWR, 53.4, 3.3),
    ("BR", DATA_FIELD_OHWR, 52.9, 3.6),
    ("BR", DATA_FIELD_GPWR, 52.5, 2.0),
    ("BG", DATA_FIELD_GIHWR, 57.8, 3.7),
    ("BG", DATA_FIELD_OHWR, 56.9, 4.2),
    ("BG", DATA_FIELD_GPWR, 55.6, 2.3),
    ("RG", DATA_FIELD_GIHWR, 55.4, 3.7),
    ("RG", DATA_FIELD_OHWR, 55.8, 3.7),
    ("RG", DATA_FIELD_GPWR, 55.0, 1.8),
    ("WUB", DATA_FIELD_GIHWR, 52.6, 2.6),
    # "WUB" OHWR - 17Lands isn't displaying the standard deviation
    ("WUB", DATA_FIELD_GPWR, 48.6, 2.2),
    ("WUR", DATA_FIELD_GIHWR, 48.4, 2.9),
    # "WUR" OHWR - 17Lands isn't displaying the standard deviation or mean
    ("WUR", DATA_FIELD_GPWR, 47.3, 2.3),
    ("WUG", DATA_FIELD_GIHWR, 52.6, 3.1),
    ("WUG", DATA_FIELD_OHWR, 51.7, 3.3),
    ("WUG", DATA_FIELD_GPWR, 50.8, 2.2),
    ("WBR", DATA_FIELD_GIHWR, 51.7, 2.5),
    # "WBR" OHWR - 17Lands isn't displaying the standard deviation or mean
    ("WBR", DATA_FIELD_GPWR, 50.0, 2.0), 
    ("WBG", DATA_FIELD_GIHWR, 55.9, 2.9),
    ("WBG", DATA_FIELD_OHWR, 54.9, 3.1),
    ("WBG", DATA_FIELD_GPWR, 54.3, 2.2),
    ("WRG", DATA_FIELD_GIHWR, 54.3, 3.2),
    ("WRG", DATA_FIELD_OHWR, 54.3, 3.4),
    ("WRG", DATA_FIELD_GPWR, 53.5, 2.1),
    ("UBR", DATA_FIELD_GIHWR, 52.6, 3.2),
    ("UBR", DATA_FIELD_OHWR, 50.2, 3.1),
    ("UBR", DATA_FIELD_GPWR, 49.3, 2.3),
    ("UBG", DATA_FIELD_GIHWR, 55.4, 3.3),
    ("UBG", DATA_FIELD_OHWR, 53.3, 3.8),
    ("UBG", DATA_FIELD_GPWR, 52.6, 2.6),
    ("URG", DATA_FIELD_GIHWR, 53.7, 3.3),
    ("URG", DATA_FIELD_OHWR, 53.5, 2.6),
    ("URG", DATA_FIELD_GPWR, 51.2, 2.1),
    ("BRG", DATA_FIELD_GIHWR, 52.2, 3.1),
    ("BRG", DATA_FIELD_OHWR, 52.9, 3.1),
    ("BRG", DATA_FIELD_GPWR, 50.8, 2.3),
]

@pytest.fixture(name="mkm_premier", scope="module")
def fixture_mkm_premier():
    set_data = {}
    with open(MKM_PREMIER_SNAPSHOT, 'r', encoding="utf-8", errors="replace") as json_file:
        set_data = json.loads(json_file.read())
        
    return SetMetrics(set_data, 1)
    
@pytest.fixture(name="otj_premier", scope="module")
def fixture_otj_premier():
    set_data = {}
    with open(OTJ_PREMIER_SNAPSHOT, 'r', encoding="utf-8", errors="replace") as json_file:
        set_data = json.loads(json_file.read())
        
    return SetMetrics(set_data, 1)
    
@pytest.fixture(name="missing_set", scope="module")
def fixture_missing_set():
    return SetMetrics(None)

@pytest.mark.parametrize("colors, field, expected_mean, expected_std", MKM_PREMIER_EXPECTED_RESULTS)
def test_metrics_mkm_premier(mkm_premier, colors, field, expected_mean, expected_std):
    # Compare the calculated values with the values from 17Lands
    mean, std = mkm_premier.get_metrics(colors, field)
    
    assert mean == pytest.approx(expected_mean, abs=0.1)  
    assert std == pytest.approx(expected_std, abs=0.1)  
    
@pytest.mark.parametrize("colors, field, expected_mean, expected_std", OTJ_PREMIER_EXPECTED_RESULTS)
def test_metrics_otj_premier(otj_premier, colors, field, expected_mean, expected_std):
    # Compare the calculated values with the values from 17Lands
    mean, std = otj_premier.get_metrics(colors, field)
    
    assert mean == pytest.approx(expected_mean, 0.1)
    assert std == pytest.approx(expected_std, 0.1)
    
@pytest.mark.parametrize("colors, field, expected_mean, expected_std", MKM_PREMIER_EXPECTED_RESULTS)
def test_metrics_missing_set(missing_set, colors, field, expected_mean, expected_std):
    # SetMetrics will return a value of 0.0 for mean and std if a set file isn't specified
    mean, std = missing_set.get_metrics(colors, field)
    
    assert mean == 0.0
    assert std == 0.0 
    
def test_metrics_unknown_color(otj_premier):
    # SetMetrics will return a value of 0.0 for mean and std if an unknown color argument is used
    mean, std = otj_premier.get_metrics("Unknown Color", DATA_FIELD_GIHWR)
    
    assert mean == 0.0
    assert std == 0.0
    
def test_metrics_unknown_field(otj_premier):
    # SetMetrics will return a value of 0.0 for mean and std if an unknown field argument is used
    mean, std = otj_premier.get_metrics("All Decks", "Unknown Field")
    
    assert mean == 0.0
    assert std == 0.0 
# --- Timeseries API Tests ---

import os
import json
import pytest
from test_02_ingest_api import LOAD_DATA_PAYLOAD, PV_GENERATION_PAYLOAD

# Constants for test timeframes
START_TIMESTAMP = "2024-01-01T00:00:00Z"
END_TIMESTAMP = "2024-12-31T23:59:59Z"
EXPECTED_RESPONSES_DIR = "expected_responses"

# Tests for the timeseries API endpoints

def load_expected(filename):
    path = os.path.join(os.path.dirname(__file__), EXPECTED_RESPONSES_DIR, filename)
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def test_get_price_timeseries(http_client, base_url):
    """Test getting price timeseries."""
    # discover a price region
    resp = http_client.get(f"{base_url}/metadata/price_regions")
    assert resp.status_code == 200
    regions = resp.json()
    assert isinstance(regions, list) and regions, "No price regions available"
    region_id = regions[0]["price_region_id"]
    url = f"{base_url}/timeseries/price?price_region_id={region_id}&start={START_TIMESTAMP}&end={END_TIMESTAMP}"
    response = http_client.get(url)
    assert response.status_code == 200
    data = response.json()
    expected = load_expected('prices_timeseries.json')
    assert data == expected


def test_get_weather_obs_timeseries(http_client, base_url):
    """Test getting weather observation timeseries."""
    # discover a location
    resp = http_client.get(f"{base_url}/metadata/locations")
    assert resp.status_code == 200
    locs = resp.json()
    assert isinstance(locs, list) and locs, "No locations available"
    location_id = locs[0]["location_id"]
    url = f"{base_url}/timeseries/weather_obs?location_id={location_id}&start={START_TIMESTAMP}&end={END_TIMESTAMP}"
    response = http_client.get(url)
    assert response.status_code == 200
    data = response.json()
    expected = load_expected('weather_obs_timeseries.json')
    assert data == expected


def test_get_weather_fcst_timeseries(http_client, base_url):
    """Test getting weather forecast timeseries."""
    # discover a location
    resp = http_client.get(f"{base_url}/metadata/locations")
    assert resp.status_code == 200
    locs = resp.json()
    assert isinstance(locs, list) and locs, "No locations available"
    location_id = locs[0]["location_id"]
    url = f"{base_url}/timeseries/weather_fcst?location_id={location_id}&start={START_TIMESTAMP}&end={END_TIMESTAMP}"
    response = http_client.get(url)
    assert response.status_code == 200
    data = response.json()
    expected = load_expected('weather_fc_timeseries.json')
    assert data == expected


def test_get_load_timeseries(http_client, base_url):
    """Test getting load timeseries."""
    # discover a household
    resp = http_client.get(f"{base_url}/metadata/households")
    assert resp.status_code == 200
    hhs = resp.json()
    assert isinstance(hhs, list) and hhs, "No households available"
    household_id = hhs[0]["household_id"]
    
    # Use original timestamps for API query parameters
    original_start_time = LOAD_DATA_PAYLOAD["data"][0]["time"]
    original_end_time = LOAD_DATA_PAYLOAD["data"][-1]["time"]

    # expected load data matches the ingest payload for household
    payload = LOAD_DATA_PAYLOAD.copy()
    payload["data"] = [item.copy() for item in LOAD_DATA_PAYLOAD["data"]]
    for rec in payload["data"]:
        rec["household_id"] = household_id
        # Normalize timestamp format for comparison with response body
        rec["time"] = rec["time"].replace("Z", "+00:00")
        
    url = f"{base_url}/timeseries/load?household_id={household_id}&start={original_start_time}&end={original_end_time}"
    response = http_client.get(url)
    assert response.status_code == 200
    data = response.json()
    # sort by time to ensure consistent order
    data_sorted = sorted(data, key=lambda x: x['time'])
    assert data_sorted == payload["data"]


def test_get_pv_timeseries(http_client, base_url):
    """Test getting PV timeseries."""
    # discover a household
    resp = http_client.get(f"{base_url}/metadata/households")
    assert resp.status_code == 200
    hhs = resp.json()
    assert isinstance(hhs, list) and hhs, "No households available"
    household_id = hhs[0]["household_id"]

    # Use original timestamps for API query parameters
    original_start_time = PV_GENERATION_PAYLOAD["data"][0]["time"]
    original_end_time = PV_GENERATION_PAYLOAD["data"][-1]["time"]

    payload = PV_GENERATION_PAYLOAD.copy()
    payload["data"] = [item.copy() for item in PV_GENERATION_PAYLOAD["data"]]
    for rec in payload["data"]:
        rec["household_id"] = household_id
        # Normalize timestamp format for comparison with response body
        rec["time"] = rec["time"].replace("Z", "+00:00")
        
    url = f"{base_url}/timeseries/pv?household_id={household_id}&start={original_start_time}&end={original_end_time}"
    response = http_client.get(url)
    assert response.status_code == 200
    data = response.json()
    data_sorted = sorted(data, key=lambda x: x['time'])
    assert data_sorted == payload["data"]

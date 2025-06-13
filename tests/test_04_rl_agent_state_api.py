# --- RL Agent State API Tests ---

import os
import json

EXPECTED_RESPONSES_DIR = "expected_responses/rl_agent_state"

# Helper to load expected JSON responses
def load_expected(filename):
    path = os.path.join(os.path.dirname(__file__), EXPECTED_RESPONSES_DIR, filename)
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

# Helper to pick an existing household
def get_household_id(http_client, base_url):
    resp = http_client.get(f"{base_url}/metadata/households")
    assert resp.status_code == 200
    hhs = resp.json()
    assert isinstance(hhs, list) and hhs, "No households available"
    return hhs[0]["household_id"]

# --- Tests for the RL Agent State API endpoint ---

def test_rl_agent_state_example_request(http_client, base_url):
    """Test RL agent state with all example parameters (fields, forecast_fields, forecast_hours, start/end)."""
    household_id = get_household_id(http_client, base_url)
    start = "2024-01-01T12:59:00Z"
    end = "2024-01-01T13:58:00Z"
    fields = [
        "prices",
        "pv_generation_kwh", "load_consumption_kwh",
        "obs_temp", "obs_humidity", "obs_windspeed", "obs_cloudcover", "obs_solarradiation", "forecasts"
    ]
    forecast_fields = ["temp", "windspeed", "windspeedmax"]
    params = [
        f"household_id={household_id}",
        f"start_time={start}",
        f"end_time={end}",
        "forecast_hours=10"
    ]
    for f in fields:
        params.append(f"fields={f}")
    for ff in forecast_fields:
        params.append(f"forecast_fields={ff}")
    url = f"{base_url}/rl_agent_state/?{'&'.join(params)}"
    response = http_client.get(url)
    assert response.status_code == 200
    data = response.json()
    expected = load_expected('rl_agent_state_example.json')
    assert data == expected


def test_rl_agent_state_start_only(http_client, base_url):
    """Test RL agent state with only start_time (end_time omitted, should default to start_time)."""
    household_id = get_household_id(http_client, base_url)
    start = "2024-01-02T00:00:00Z"
    url = f"{base_url}/rl_agent_state/?household_id={household_id}&start_time={start}"
    response = http_client.get(url)
    assert response.status_code == 200
    data = response.json()
    expected = load_expected('rl_agent_state_start_only.json')
    assert data == expected


def test_rl_agent_state_different_forecast_hours(http_client, base_url):
    """Test RL agent state with different forecast_hours parameter (always include minimal required fields)."""
    household_id = get_household_id(http_client, base_url)
    start = "2024-01-01T00:00:00Z"
    end = "2024-01-01T01:00:00Z"
    # Always include minimal required fields
    fields = ["timestamp", "forecasts"]
    params = [
        f"household_id={household_id}",
        f"start_time={start}",
        f"end_time={end}",
        "forecast_hours=5"
    ]
    for f in fields:
        params.append(f"fields={f}")
    url = f"{base_url}/rl_agent_state/?{'&'.join(params)}"
    response = http_client.get(url)
    assert response.status_code == 200
    data = response.json()
    expected = load_expected('rl_agent_state_fc5.json')
    assert data == expected


def test_rl_agent_state_different_fields(http_client, base_url):
    """Test RL agent state with a subset of fields (always include minimal required fields)."""
    household_id = get_household_id(http_client, base_url)
    start = "2024-01-01T00:00:00Z"
    end = "2024-01-01T01:00:00Z"
    # Always include minimal required fields (e.g., timestamp, forecasts)
    fields = ["timestamp", "prices", "pv_generation_kwh", "obs_temp"]
    params = [
        f"household_id={household_id}",
        f"start_time={start}",
        f"end_time={end}"
    ]
    for f in fields:
        params.append(f"fields={f}")
    url = f"{base_url}/rl_agent_state/?{'&'.join(params)}"
    response = http_client.get(url)
    assert response.status_code == 200
    data = response.json()
    expected = load_expected('rl_agent_state_fields_subset.json')
    assert data == expected


def test_rl_agent_state_different_minute_resolutions(http_client, base_url):
    """Test RL agent state with different minute resolutions (always include minimal required fields)."""
    household_id = get_household_id(http_client, base_url)
    start = "2024-01-01T00:00:00Z"
    end = "2024-01-01T01:00:00Z"
    # Always include minimal required fields
    fields = ["timestamp", "forecasts"]
    params = [
        f"household_id={household_id}",
        f"start_time={start}",
        f"end_time={end}",
        "resolution_minutes=60",
        "forecast_hours=48"
    ]
    for f in fields:
        params.append(f"fields={f}")
    url = f"{base_url}/rl_agent_state/?{'&'.join(params)}"
    response = http_client.get(url)
    assert response.status_code == 200
    data = response.json()
    expected = load_expected('rl_agent_state_res60.json')
    assert data == expected


def test_rl_agent_state_invalid_end_time(http_client, base_url):
    """Test RL agent state with end_time before start_time returns 400."""
    household_id = get_household_id(http_client, base_url)
    start = "2024-01-02T01:00:00Z"
    end = "2024-01-02T00:00:00Z"
    url = f"{base_url}/rl_agent_state/?household_id={household_id}&start_time={start}&end_time={end}"
    response = http_client.get(url)
    assert response.status_code == 400

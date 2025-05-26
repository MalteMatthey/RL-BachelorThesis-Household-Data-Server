# --- Ingest API Tests ---

LOAD_DATA_PAYLOAD = {
    "data": [
        {"time": "2024-01-01T05:00:00Z", "household_id": None, "consumption_kwh": 2.1},
        {"time": "2024-01-01T06:00:00Z", "household_id": None, "consumption_kwh": 2.2},
        {"time": "2024-01-02T01:00:00Z", "household_id": None, "consumption_kwh": 3.0}
    ]
}

EXPECTED_LOAD_RESPONSE = {
    "inserted_load": 3,
    "fetched_weather_obs": 0,
    "fetched_weather_fc": 0,
    "fetched_prices": 0,
    "simulated_pv_records": "No simulation performed",
    "detail": "Load data ingested. Related data fetched for overlapping time period or simulation period if applicable."
}

PV_GENERATION_PAYLOAD = {
    "data": [
        {"time": "2024-01-01T06:00:00Z", "household_id": None, "generation_kwh": 1.2},
        {"time": "2024-01-02T01:00:00Z", "household_id": None, "generation_kwh": 1.3},
        {"time": "2024-01-02T02:00:00Z", "household_id": None, "generation_kwh": 1.9}
    ]
}

EXPECTED_PV_RESPONSE = {
    "inserted_pv": 3,
    "fetched_weather_obs": 48,
    "fetched_weather_fc": 384,
    "fetched_prices": 48,
    "simulated_pv_records": "No simulation performed",
    "detail": "Pv data ingested. Related data fetched for overlapping time period or simulation period if applicable."
}

LOAD_DATA_SIMULATE_PV_PAYLOAD = {
    "data": [
        {"time": "2024-01-01T05:00:00Z", "household_id": None, "consumption_kwh": 2.1},
        {"time": "2024-01-01T06:00:00Z", "household_id": None, "consumption_kwh": 2.2},
        {"time": "2024-01-02T01:00:00Z", "household_id": None, "consumption_kwh": 3.0}
    ],
    "simulate_pv_generation": "true"
}

EXPECTED_LOAD_SIMULATE_PV_RESPONSE = {
    "inserted_load": 3,
    "fetched_weather_obs": 48,
    "fetched_weather_fc": 384,
    "fetched_prices": 48,
    "simulated_pv_records": 192,
    "detail": "Load data ingested and PV simulated using fetched weather."
}


def test_ingest_load_data_household_1(http_client, base_url):
    """Test ingesting load data for household 1."""
    # discover an existing household via metadata API
    resp = http_client.get(f"{base_url}/metadata/households")
    assert resp.status_code == 200
    hhs = resp.json()
    assert isinstance(hhs, list) and hhs, "No households available for ingest tests"
    household_id = hhs[0]["household_id"]

    # Update payload with dynamic household_id
    payload = LOAD_DATA_PAYLOAD.copy()
    # Deep copy data to avoid modifying the constant
    payload["data"] = [item.copy() for item in LOAD_DATA_PAYLOAD["data"]]
    for record in payload["data"]:
        record["household_id"] = household_id

    url = f"{base_url}/ingest/load_data"
    response = http_client.post(url, json=payload)
    assert response.status_code == 200
    response_data = response.json()

    assert response_data == EXPECTED_LOAD_RESPONSE

def test_ingest_pv_generation_household_1(http_client, base_url):
    """Test ingesting PV generation data for household 1."""
    # discover an existing household via metadata API
    resp = http_client.get(f"{base_url}/metadata/households")
    assert resp.status_code == 200
    hhs = resp.json()
    assert isinstance(hhs, list) and hhs, "No households available for ingest tests"
    household_id = hhs[0]["household_id"]

    # Update payload with dynamic household_id
    payload = PV_GENERATION_PAYLOAD.copy()
    # Deep copy data to avoid modifying the constant
    payload["data"] = [item.copy() for item in PV_GENERATION_PAYLOAD["data"]]
    for record in payload["data"]:
        record["household_id"] = household_id

    url = f"{base_url}/ingest/pv_generation"
    response = http_client.post(url, json=payload)
    assert response.status_code == 200
    response_data = response.json()

    assert response_data == EXPECTED_PV_RESPONSE

def test_ingest_load_data_with_pv_simulation_household_2(http_client, base_url):
    """Test ingesting load data with PV simulation for household 2."""
    # discover existing households via metadata API
    resp = http_client.get(f"{base_url}/metadata/households")
    assert resp.status_code == 200
    hhs = resp.json()
    assert isinstance(hhs, list) and len(hhs) >= 2, "At least 2 households needed for this test"
    household_id = hhs[1]["household_id"]  # Use second household (index 1)

    # Update payload with dynamic household_id
    payload = LOAD_DATA_SIMULATE_PV_PAYLOAD.copy()
    # Deep copy data to avoid modifying the constant
    payload["data"] = [item.copy() for item in LOAD_DATA_SIMULATE_PV_PAYLOAD["data"]]
    for record in payload["data"]:
        record["household_id"] = household_id

    url = f"{base_url}/ingest/load_data"
    response = http_client.post(url, json=payload)
    assert response.status_code == 200
    response_data = response.json()

    # Verify all fields, including the expected number of simulated PV records
    assert response_data == EXPECTED_LOAD_SIMULATE_PV_RESPONSE

def test_ingest_load_data_non_existent_household(http_client, base_url):
    """Test ingesting load data for a non-existent household."""
    payload = LOAD_DATA_PAYLOAD.copy()
    for record in payload["data"]:
        record["household_id"] = 99999  # Assuming this ID does not exist

    url = f"{base_url}/ingest/load_data"
    response = http_client.post(url, json=payload)
    assert response.status_code == 404

def test_ingest_pv_data_non_existent_household(http_client, base_url):
    """Test ingesting PV data for a non-existent household."""
    payload = PV_GENERATION_PAYLOAD.copy()
    for record in payload["data"]:
        record["household_id"] = 99999  # Assuming this ID does not exist

    url = f"{base_url}/ingest/pv_generation"
    response = http_client.post(url, json=payload)
    assert response.status_code == 404


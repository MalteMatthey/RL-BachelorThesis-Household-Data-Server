# --- Metadata API Tests ---

import pytest

# Test data for price region
PRICE_REGION_PAYLOAD_ALPHA = {
    "name": "Test Region Alpha",
    "bidding_zone_eic_code": "10Y1001A1001A82H"
}
PRICE_REGION_PAYLOAD_BETA = {
    "name": "Test Region Beta",
    "bidding_zone_eic_code": "10Y1001A1001A82H"
}

# Store the ID of the created price regions for use in other tests
created_price_region_id_alpha = None
created_price_region_id_beta = None

# Test data for locations
# Locations will be created under "Test Region Beta"
LOCATION_PAYLOAD_1 = {
    # price_region_id will be set dynamically after Test Region Beta is created
    "name": "Loc1InRegionBeta",
    "latitude": 49.01,
    "longitude": 8.41
}
LOCATION_PAYLOAD_2 = {
    # price_region_id will be set dynamically
    "name": "Loc2InRegionBeta",
    "latitude": 49.02,
    "longitude": 8.42
}

created_location_id_1 = None
created_location_id_2 = None

# Test data for households
# Households will be created under the locations created above
HOUSEHOLD_PAYLOAD_1 = {
    # location_id will be set dynamically
    "name": "Household1Loc1",
    "enduser_price_formula": "price * 1.19 + 0.5"
}
HOUSEHOLD_PAYLOAD_2 = {
    # location_id will be set dynamically
    "name": "Household1Loc2",
    "enduser_price_formula": "price * 1.1"
}

created_household_id_1 = None
created_household_id_2 = None


# --- Price Region Tests ---

def test_empty_price_regions(http_client, base_url):
    """Test no price regions exist before any are created."""
    url = f"{base_url}/metadata/price_regions"
    response = http_client.get(url)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert data == [], "Expected no regions on fresh service start"


def test_create_price_region_alpha(http_client, base_url):
    """Test creating the first new price region (Alpha)."""
    global created_price_region_id_alpha
    url = f"{base_url}/metadata/price_regions"
    response = http_client.post(url, json=PRICE_REGION_PAYLOAD_ALPHA)
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["name"] == PRICE_REGION_PAYLOAD_ALPHA["name"]
    assert response_data["bidding_zone_eic_code"] == PRICE_REGION_PAYLOAD_ALPHA["bidding_zone_eic_code"]
    assert "price_region_id" in response_data
    created_price_region_id_alpha = response_data["price_region_id"]

def test_create_price_region_beta(http_client, base_url):
    """Test creating the second new price region (Beta)."""
    global created_price_region_id_beta
    url = f"{base_url}/metadata/price_regions"
    response = http_client.post(url, json=PRICE_REGION_PAYLOAD_BETA)
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["name"] == PRICE_REGION_PAYLOAD_BETA["name"]
    assert response_data["bidding_zone_eic_code"] == PRICE_REGION_PAYLOAD_BETA["bidding_zone_eic_code"]
    assert "price_region_id" in response_data
    created_price_region_id_beta = response_data["price_region_id"]

def test_get_specific_price_region_alpha(http_client, base_url):
    """Test retrieving a specific price region by its ID (Alpha)."""
    assert created_price_region_id_alpha is not None, "Price region Alpha must be created before it can be retrieved"
    url = f"{base_url}/metadata/price_regions/{created_price_region_id_alpha}"
    response = http_client.get(url)
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["price_region_id"] == created_price_region_id_alpha
    assert response_data["name"] == PRICE_REGION_PAYLOAD_ALPHA["name"]
    assert response_data["bidding_zone_eic_code"] == PRICE_REGION_PAYLOAD_ALPHA["bidding_zone_eic_code"]

def test_get_all_price_regions(http_client, base_url):
    """Test retrieving all price regions."""
    assert created_price_region_id_alpha is not None, "Price region Alpha must be created"
    assert created_price_region_id_beta is not None, "Price region Beta must be created"
    url = f"{base_url}/metadata/price_regions"
    response = http_client.get(url)
    assert response.status_code == 200
    response_data = response.json()
    assert isinstance(response_data, list)
    assert len(response_data) >= 2 # Expecting at least the two created regions

    ids_found = {pr["price_region_id"] for pr in response_data if "price_region_id" in pr}
    assert created_price_region_id_alpha in ids_found, "Created price region Alpha not found"
    assert created_price_region_id_beta in ids_found, "Created price region Beta not found"

    for pr in response_data:
        if pr["price_region_id"] == created_price_region_id_alpha:
            assert pr["name"] == PRICE_REGION_PAYLOAD_ALPHA["name"]
            assert pr["bidding_zone_eic_code"] == PRICE_REGION_PAYLOAD_ALPHA["bidding_zone_eic_code"]
        elif pr["price_region_id"] == created_price_region_id_beta:
            assert pr["name"] == PRICE_REGION_PAYLOAD_BETA["name"]
            assert pr["bidding_zone_eic_code"] == PRICE_REGION_PAYLOAD_BETA["bidding_zone_eic_code"]

def test_get_price_regions_by_name(http_client, base_url):
    """Test retrieving price regions filtered by name."""
    assert created_price_region_id_alpha is not None, "Price region Alpha must be created for this test."
    # Test with the name of the first created region
    url = f"{base_url}/metadata/price_regions?name={PRICE_REGION_PAYLOAD_ALPHA['name']}"
    response = http_client.get(url)
    assert response.status_code == 200
    response_data = response.json()
    assert isinstance(response_data, list)
    assert len(response_data) >= 1
    found = any(
        pr["price_region_id"] == created_price_region_id_alpha and
        pr["name"] == PRICE_REGION_PAYLOAD_ALPHA["name"]
        for pr in response_data
    )
    assert found, "Filtered price region Alpha not found by name."

    # Test with a name that should not exist
    url = f"{base_url}/metadata/price_regions?name=NonExistentRegionName"
    response = http_client.get(url)
    assert response.status_code == 200
    response_data = response.json()
    assert isinstance(response_data, list)
    assert len(response_data) == 0, "Expected no regions for a non-existent name."


def test_get_price_region_not_found(http_client, base_url):
    """Test retrieving a non-existent price region."""
    non_existent_id = 999999
    url = f"{base_url}/metadata/price_regions/{non_existent_id}"
    response = http_client.get(url)
    assert response.status_code == 404


# --- Location Tests ---

def test_empty_locations(http_client, base_url):
    """Test no locations exist before any are created (or after cleanup if tests are isolated)."""
    url = f"{base_url}/metadata/locations"
    response = http_client.get(url)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

def test_create_location_1(http_client, base_url):
    """Test creating the first new location."""
    global created_location_id_1
    assert created_price_region_id_beta is not None, "Price Region Beta must be created first"
    LOCATION_PAYLOAD_1["price_region_id"] = created_price_region_id_beta

    url = f"{base_url}/metadata/locations"
    response = http_client.post(url, json=LOCATION_PAYLOAD_1)
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["name"] == LOCATION_PAYLOAD_1["name"]
    assert response_data["price_region_id"] == LOCATION_PAYLOAD_1["price_region_id"]
    assert response_data["latitude"] == LOCATION_PAYLOAD_1["latitude"]
    assert response_data["longitude"] == LOCATION_PAYLOAD_1["longitude"]
    assert "location_id" in response_data
    created_location_id_1 = response_data["location_id"]

def test_create_location_2(http_client, base_url):
    """Test creating the second new location."""
    global created_location_id_2
    assert created_price_region_id_beta is not None, "Price Region Beta must be created first"
    LOCATION_PAYLOAD_2["price_region_id"] = created_price_region_id_beta

    url = f"{base_url}/metadata/locations"
    response = http_client.post(url, json=LOCATION_PAYLOAD_2)
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["name"] == LOCATION_PAYLOAD_2["name"]
    assert response_data["price_region_id"] == LOCATION_PAYLOAD_2["price_region_id"]
    assert response_data["latitude"] == LOCATION_PAYLOAD_2["latitude"]
    assert response_data["longitude"] == LOCATION_PAYLOAD_2["longitude"]
    assert "location_id" in response_data
    created_location_id_2 = response_data["location_id"]

def test_create_location_with_non_existent_region(http_client, base_url):
    """Test creating a location with a non-existent price_region_id."""
    non_existent_region_id = 999998
    payload = {
        "price_region_id": non_existent_region_id,
        "name": "LocationWithInvalidRegion",
        "latitude": 50.0,
        "longitude": 9.0
    }
    url = f"{base_url}/metadata/locations"
    response = http_client.post(url, json=payload)
    assert response.status_code == 404 # As per API definition for non-existent region

def test_get_specific_location_1(http_client, base_url):
    """Test retrieving a specific location by its ID (Location 1)."""
    assert created_location_id_1 is not None, "Location 1 must be created first"
    url = f"{base_url}/metadata/locations/{created_location_id_1}"
    response = http_client.get(url)
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["location_id"] == created_location_id_1
    assert response_data["name"] == LOCATION_PAYLOAD_1["name"]
    assert response_data["price_region_id"] == LOCATION_PAYLOAD_1["price_region_id"]
    assert response_data["latitude"] == LOCATION_PAYLOAD_1["latitude"]
    assert response_data["longitude"] == LOCATION_PAYLOAD_1["longitude"]

def test_get_all_locations(http_client, base_url):
    """Test retrieving all locations."""
    assert created_location_id_1 is not None, "Location 1 must be created"
    assert created_location_id_2 is not None, "Location 2 must be created"
    url = f"{base_url}/metadata/locations"
    response = http_client.get(url)
    assert response.status_code == 200
    response_data = response.json()
    assert isinstance(response_data, list)
    assert len(response_data) >= 2

    ids_found = {loc["location_id"] for loc in response_data if "location_id" in loc}
    assert created_location_id_1 in ids_found
    assert created_location_id_2 in ids_found

    for loc in response_data:
        if loc["location_id"] == created_location_id_1:
            assert loc["name"] == LOCATION_PAYLOAD_1["name"]
            assert loc["price_region_id"] == LOCATION_PAYLOAD_1["price_region_id"]
        elif loc["location_id"] == created_location_id_2:
            assert loc["name"] == LOCATION_PAYLOAD_2["name"]
            assert loc["price_region_id"] == LOCATION_PAYLOAD_2["price_region_id"]

def test_get_locations_by_price_region_id(http_client, base_url):
    """Test retrieving locations filtered by price_region_id."""
    assert created_location_id_1 is not None, "Location 1 must be created"
    assert created_location_id_2 is not None, "Location 2 must be created"
    assert created_price_region_id_beta is not None, "Price Region Beta must exist"

    url = f"{base_url}/metadata/locations?price_region_id={created_price_region_id_beta}"
    response = http_client.get(url)
    assert response.status_code == 200
    response_data = response.json()
    assert isinstance(response_data, list)
    # Both created locations belong to created_price_region_id_beta
    assert len(response_data) >= 2
    
    ids_found = {loc["location_id"] for loc in response_data}
    assert created_location_id_1 in ids_found
    assert created_location_id_2 in ids_found
    for loc in response_data:
        assert loc["price_region_id"] == created_price_region_id_beta

    # Test with a region ID that should have no locations (e.g., alpha, if we didn't add any)
    # or a non-existent one.
    assert created_price_region_id_alpha is not None
    url = f"{base_url}/metadata/locations?price_region_id={created_price_region_id_alpha}"
    response = http_client.get(url)
    assert response.status_code == 200
    response_data = response.json()
    assert isinstance(response_data, list)
    # Assuming no locations were added to region alpha in these tests
    assert len(response_data) == 0


def test_get_location_not_found(http_client, base_url):
    """Test retrieving a non-existent location."""
    non_existent_id = 999997
    url = f"{base_url}/metadata/locations/{non_existent_id}"
    response = http_client.get(url)
    assert response.status_code == 404


# --- Household Tests ---

def test_empty_households(http_client, base_url):
    """Test no households exist before any are created (or after cleanup)."""
    url = f"{base_url}/metadata/households"
    response = http_client.get(url)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

def test_create_household_1(http_client, base_url):
    """Test creating the first new household."""
    global created_household_id_1
    assert created_location_id_1 is not None, "Location 1 must be created first"
    HOUSEHOLD_PAYLOAD_1["location_id"] = created_location_id_1

    url = f"{base_url}/metadata/households"
    response = http_client.post(url, json=HOUSEHOLD_PAYLOAD_1)
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["name"] == HOUSEHOLD_PAYLOAD_1["name"]
    assert response_data["location_id"] == HOUSEHOLD_PAYLOAD_1["location_id"]
    assert response_data.get("enduser_price_formula") == HOUSEHOLD_PAYLOAD_1["enduser_price_formula"]
    assert "household_id" in response_data
    created_household_id_1 = response_data["household_id"]

def test_create_household_2(http_client, base_url):
    """Test creating the second new household."""
    global created_household_id_2
    assert created_location_id_2 is not None, "Location 2 must be created first"
    HOUSEHOLD_PAYLOAD_2["location_id"] = created_location_id_2

    url = f"{base_url}/metadata/households"
    response = http_client.post(url, json=HOUSEHOLD_PAYLOAD_2)
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["name"] == HOUSEHOLD_PAYLOAD_2["name"]
    assert response_data["location_id"] == HOUSEHOLD_PAYLOAD_2["location_id"]
    assert response_data.get("enduser_price_formula") == HOUSEHOLD_PAYLOAD_2["enduser_price_formula"]
    assert "household_id" in response_data
    created_household_id_2 = response_data["household_id"]

def test_create_household_with_non_existent_location(http_client, base_url):
    """Test creating a household with a non-existent location."""
    non_existent_location_id = 999996
    payload = {
        "location_id": non_existent_location_id,
        "name": "HouseholdWithInvalidLocation",
        "enduser_price_formula": "price * 1.0"
    }
    url = f"{base_url}/metadata/households"
    response = http_client.post(url, json=payload)
    assert response.status_code == 404 # As per API definition

def test_get_specific_household_1(http_client, base_url):
    """Test retrieving a specific household by its ID (Household 1)."""
    assert created_household_id_1 is not None, "Household 1 must be created first"
    url = f"{base_url}/metadata/households/{created_household_id_1}"
    response = http_client.get(url)
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["household_id"] == created_household_id_1
    assert response_data["name"] == HOUSEHOLD_PAYLOAD_1["name"]
    assert response_data["location_id"] == HOUSEHOLD_PAYLOAD_1["location_id"]

def test_get_all_households(http_client, base_url):
    """Test retrieving all households."""
    assert created_household_id_1 is not None, "Household 1 must be created"
    assert created_household_id_2 is not None, "Household 2 must be created"
    url = f"{base_url}/metadata/households"
    response = http_client.get(url)
    assert response.status_code == 200
    response_data = response.json()
    assert isinstance(response_data, list)
    assert len(response_data) >= 2

    ids_found = {hh["household_id"] for hh in response_data if "household_id" in hh}
    assert created_household_id_1 in ids_found
    assert created_household_id_2 in ids_found

    for hh in response_data:
        if hh["household_id"] == created_household_id_1:
            assert hh["name"] == HOUSEHOLD_PAYLOAD_1["name"]
            assert hh["location_id"] == HOUSEHOLD_PAYLOAD_1["location_id"]
        elif hh["household_id"] == created_household_id_2:
            assert hh["name"] == HOUSEHOLD_PAYLOAD_2["name"]
            assert hh["location_id"] == HOUSEHOLD_PAYLOAD_2["location_id"]

def test_get_households_by_location_id(http_client, base_url):
    """Test retrieving households filtered by location_id."""
    assert created_household_id_1 is not None, "Household 1 must be created (implies Location 1 exists)"
    assert created_location_id_1 is not None

    url = f"{base_url}/metadata/households?location_id={created_location_id_1}"
    response = http_client.get(url)
    assert response.status_code == 200
    response_data = response.json()
    assert isinstance(response_data, list)
    assert len(response_data) >= 1 # Expect at least Household 1

    found_hh1 = False
    for hh in response_data:
        assert hh["location_id"] == created_location_id_1
        if hh["household_id"] == created_household_id_1:
            assert hh["name"] == HOUSEHOLD_PAYLOAD_1["name"]
            found_hh1 = True
    assert found_hh1

    # Test with a location ID that should have no households (e.g., a newly created one without households)
    # or a non-existent one.
    non_existent_location_id_for_filter = 999995
    url = f"{base_url}/metadata/households?location_id={non_existent_location_id_for_filter}"
    response = http_client.get(url)
    assert response.status_code == 200 # API returns empty list for non-matching filter
    response_data = response.json()
    assert isinstance(response_data, list)
    assert len(response_data) == 0


def test_get_household_not_found(http_client, base_url):
    """Test retrieving a non-existent household."""
    non_existent_id = 999994
    url = f"{base_url}/metadata/households/{non_existent_id}"
    response = http_client.get(url)
    assert response.status_code == 404

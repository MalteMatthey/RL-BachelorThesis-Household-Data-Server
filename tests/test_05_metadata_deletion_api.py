# --- Metadata Deletion API Tests ---

import pytest
import json

# Constants for checking timeseries data
START_TIMESTAMP = "2024-01-01T00:00:00Z" 
END_TIMESTAMP = "2024-12-31T23:59:59Z"

# Helper function to find entities by name
def find_entity_by_name(http_client, base_url, entity_type, name):
    """Find an entity ID by its name through the API."""
    response = http_client.get(f"{base_url}/metadata/{entity_type}")
    if response.status_code == 200:
        entities = response.json()
        for entity in entities:
            if entity.get("name") == name:
                return entity
    return None


# --- Helper Functions ---

def check_household_timeseries_deleted(http_client, base_url, household_id):
    """Helper to verify that all timeseries data for a household is deleted."""
    
    # Check PV generation data is deleted
    pv_url = f"{base_url}/timeseries/pv?household_id={household_id}&start={START_TIMESTAMP}&end={END_TIMESTAMP}"
    response = http_client.get(pv_url)
    if response.status_code == 200:
        pv_data = response.json()
        assert len(pv_data) == 0, f"PV data still exists for deleted household {household_id}"
    elif response.status_code == 404:
        # 404 is also acceptable - means no data found
        pass
    else:
        pytest.fail(f"Unexpected status code {response.status_code} when checking PV data for household {household_id}")
    
    # Check load data is deleted  
    load_url = f"{base_url}/timeseries/load?household_id={household_id}&start={START_TIMESTAMP}&end={END_TIMESTAMP}"
    response = http_client.get(load_url)
    if response.status_code == 200:
        load_data = response.json()
        assert len(load_data) == 0, f"Load data still exists for deleted household {household_id}"
    elif response.status_code == 404:
        # 404 is also acceptable - means no data found
        pass
    else:
        pytest.fail(f"Unexpected status code {response.status_code} when checking load data for household {household_id}")

    # Check household-specific price data is deleted (if any was calculated)
    price_url = f"{base_url}/timeseries/price?household_id={household_id}&start={START_TIMESTAMP}&end={END_TIMESTAMP}"
    response = http_client.get(price_url)
    if response.status_code == 200:
        price_data = response.json()
        assert len(price_data) == 0, f"Price data still exists for deleted household {household_id}"
    elif response.status_code == 404:
        # 404 is also acceptable - means no data found
        pass
    else:
        pytest.fail(f"Unexpected status code {response.status_code} when checking price data for household {household_id}")


def check_location_timeseries_deleted(http_client, base_url, location_id):
    """Helper to verify that all weather data for a location is deleted."""
    
    # Check weather observations are deleted
    weather_obs_url = f"{base_url}/timeseries/weather_observations?location_id={location_id}&start={START_TIMESTAMP}&end={END_TIMESTAMP}"
    response = http_client.get(weather_obs_url)
    if response.status_code == 200:
        weather_data = response.json()
        assert len(weather_data) == 0, f"Weather observation data still exists for deleted location {location_id}"
    elif response.status_code == 404:
        # 404 is also acceptable - means no data found
        pass
    else:
        pytest.fail(f"Unexpected status code {response.status_code} when checking weather observations for location {location_id}")
    
    # Check weather forecasts are deleted
    weather_fc_url = f"{base_url}/timeseries/weather_forecasts?location_id={location_id}&start={START_TIMESTAMP}&end={END_TIMESTAMP}"
    response = http_client.get(weather_fc_url)
    if response.status_code == 200:
        weather_data = response.json()
        assert len(weather_data) == 0, f"Weather forecast data still exists for deleted location {location_id}"
    elif response.status_code == 404:
        # 404 is also acceptable - means no data found
        pass
    else:
        pytest.fail(f"Unexpected status code {response.status_code} when checking weather forecasts for location {location_id}")


def check_price_region_timeseries_deleted(http_client, base_url, price_region_id):
    """Helper to verify that all price data for a price region is deleted."""
    
    price_url = f"{base_url}/timeseries/price?price_region_id={price_region_id}&start={START_TIMESTAMP}&end={END_TIMESTAMP}"
    response = http_client.get(price_url)
    if response.status_code == 200:
        price_data = response.json()
        assert len(price_data) == 0, f"Price data still exists for deleted price region {price_region_id}"
    elif response.status_code == 404:
        # 404 is also acceptable - means no data found
        pass
    else:
        pytest.fail(f"Unexpected status code {response.status_code} when checking price data for price region {price_region_id}")


# --- Test Deletion of Individual Household ---

def test_delete_household_1_success(http_client, base_url):
    """Test successful deletion of household 1 created in previous tests."""
    # Find household 1 by name from previous tests
    household_1 = find_entity_by_name(http_client, base_url, "households", "Household1Loc1")
    assert household_1 is not None, "Household 'Household1Loc1' must have been created in previous tests"
    household_id_1 = household_1["household_id"]
    
    # Verify household exists before deletion
    response = http_client.get(f"{base_url}/metadata/households/{household_id_1}")
    assert response.status_code == 200, "Household 1 should exist before deletion"
    
    # Delete household
    response = http_client.delete(f"{base_url}/metadata/households/{household_id_1}")
    assert response.status_code == 200
    response_data = response.json()
    assert "message" in response_data
    assert str(household_id_1) in response_data["message"]
    
    # Verify household is deleted - should return 404
    response = http_client.get(f"{base_url}/metadata/households/{household_id_1}")
    assert response.status_code == 404
    
    # Verify all timeseries data for this household is deleted
    check_household_timeseries_deleted(http_client, base_url, household_id_1)


def test_delete_household_not_found(http_client, base_url):
    """Test deletion of non-existent household returns 404."""
    non_existent_id = 999999
    response = http_client.delete(f"{base_url}/metadata/households/{non_existent_id}")
    assert response.status_code == 404
    response_data = response.json()
    assert "not found" in response_data["detail"].lower()


# --- Test Deletion of Location with Cascading ---

def test_delete_location_2_with_cascade(http_client, base_url):
    """Test deletion of location 2 cascades to delete household 2 and related data."""
    # Find location 2 by name from previous tests  
    location_2 = find_entity_by_name(http_client, base_url, "locations", "Loc2InRegionBeta")
    assert location_2 is not None, "Location 'Loc2InRegionBeta' must have been created in previous tests"
    location_id_2 = location_2["location_id"]
    
    # Find household 2 by name from previous tests
    household_2 = find_entity_by_name(http_client, base_url, "households", "Household1Loc2")
    assert household_2 is not None, "Household 'Household1Loc2' must have been created in previous tests"
    household_id_2 = household_2["household_id"]
    
    # Verify location and household exist before deletion
    response = http_client.get(f"{base_url}/metadata/locations/{location_id_2}")
    assert response.status_code == 200, "Location 2 should exist before deletion"
    
    response = http_client.get(f"{base_url}/metadata/households/{household_id_2}")
    assert response.status_code == 200, "Household 2 should exist before deletion"
    
    # Get households in the location before deletion
    response = http_client.get(f"{base_url}/metadata/households?location_id={location_id_2}")
    assert response.status_code == 200
    households_before = response.json()
    household_ids_to_check = [hh['household_id'] for hh in households_before]
    
    # Delete location
    response = http_client.delete(f"{base_url}/metadata/locations/{location_id_2}")
    assert response.status_code == 200
    response_data = response.json()
    assert "message" in response_data
    assert str(location_id_2) in response_data["message"]
    
    # Verify location is deleted
    response = http_client.get(f"{base_url}/metadata/locations/{location_id_2}")
    assert response.status_code == 404
    
    # Verify all households in that location are also deleted
    for household_id in household_ids_to_check:
        response = http_client.get(f"{base_url}/metadata/households/{household_id}")
        assert response.status_code == 404
        
        # Verify timeseries data for each household is deleted
        check_household_timeseries_deleted(http_client, base_url, household_id)
    
    # Verify weather data for the location is deleted
    check_location_timeseries_deleted(http_client, base_url, location_id_2)


def test_delete_location_not_found(http_client, base_url):
    """Test deletion of non-existent location returns 404."""
    non_existent_id = 999999
    response = http_client.delete(f"{base_url}/metadata/locations/{non_existent_id}")
    assert response.status_code == 404
    response_data = response.json()
    assert "not found" in response_data["detail"].lower()


# --- Test Deletion of Price Region with Full Cascade ---

def test_delete_price_region_alpha_with_full_cascade(http_client, base_url):
    """Test deletion of price region Alpha (which should be empty) works correctly."""
    # Find price region Alpha by name from previous tests
    price_region_alpha = find_entity_by_name(http_client, base_url, "price_regions", "Test Region Alpha")
    assert price_region_alpha is not None, "Price region 'Test Region Alpha' must have been created in previous tests"
    price_region_id_alpha = price_region_alpha["price_region_id"]
    
    # Verify price region exists before deletion
    response = http_client.get(f"{base_url}/metadata/price_regions/{price_region_id_alpha}")
    assert response.status_code == 200, "Price region Alpha should exist before deletion"
    
    # Get all locations in the price region before deletion (should be none for Alpha)
    response = http_client.get(f"{base_url}/metadata/locations?price_region_id={price_region_id_alpha}")
    assert response.status_code == 200
    locations_before = response.json()
    location_ids_to_check = [loc['location_id'] for loc in locations_before]
    
    # Get all households in all locations
    all_household_ids_to_check = []
    for location in locations_before:
        response = http_client.get(f"{base_url}/metadata/households?location_id={location['location_id']}")
        if response.status_code == 200:
            households = response.json()
            all_household_ids_to_check.extend([hh['household_id'] for hh in households])
    
    # Delete price region
    response = http_client.delete(f"{base_url}/metadata/price_regions/{price_region_id_alpha}")
    assert response.status_code == 200
    response_data = response.json()
    assert "message" in response_data
    assert str(price_region_id_alpha) in response_data["message"]
    
    # Verify price region is deleted
    response = http_client.get(f"{base_url}/metadata/price_regions/{price_region_id_alpha}")
    assert response.status_code == 404
    
    # Verify all locations in that price region are deleted
    for location_id in location_ids_to_check:
        response = http_client.get(f"{base_url}/metadata/locations/{location_id}")
        assert response.status_code == 404
        
        # Verify weather data for each location is deleted
        check_location_timeseries_deleted(http_client, base_url, location_id)
    
    # Verify all households are deleted
    for household_id in all_household_ids_to_check:
        response = http_client.get(f"{base_url}/metadata/households/{household_id}")
        assert response.status_code == 404
        
        # Verify timeseries data for each household is deleted
        check_household_timeseries_deleted(http_client, base_url, household_id)
    
    # Verify price data for this region is deleted
    check_price_region_timeseries_deleted(http_client, base_url, price_region_id_alpha)


def test_delete_price_region_beta_with_remaining_data(http_client, base_url):
    """Test deletion of price region Beta with remaining location 1 and associated data."""
    # Find price region Beta by name from previous tests
    price_region_beta = find_entity_by_name(http_client, base_url, "price_regions", "Test Region Beta")
    assert price_region_beta is not None, "Price region 'Test Region Beta' must have been created in previous tests"
    price_region_id_beta = price_region_beta["price_region_id"]
    
    # Verify price region exists before deletion
    response = http_client.get(f"{base_url}/metadata/price_regions/{price_region_id_beta}")
    assert response.status_code == 200, "Price region Beta should exist before deletion"
    
    # Get all locations in the price region before deletion
    response = http_client.get(f"{base_url}/metadata/locations?price_region_id={price_region_id_beta}")
    assert response.status_code == 200
    locations_before = response.json()
    location_ids_to_check = [loc['location_id'] for loc in locations_before]
    
    # Get all households in all locations
    all_household_ids_to_check = []
    for location in locations_before:
        response = http_client.get(f"{base_url}/metadata/households?location_id={location['location_id']}")
        assert response.status_code == 200
        households = response.json()
        all_household_ids_to_check.extend([hh['household_id'] for hh in households])
    
    # Delete price region
    response = http_client.delete(f"{base_url}/metadata/price_regions/{price_region_id_beta}")
    assert response.status_code == 200
    response_data = response.json()
    assert "message" in response_data
    assert str(price_region_id_beta) in response_data["message"]
    
    # Verify price region is deleted
    response = http_client.get(f"{base_url}/metadata/price_regions/{price_region_id_beta}")
    assert response.status_code == 404
    
    # Verify all locations in that price region are deleted
    for location_id in location_ids_to_check:
        response = http_client.get(f"{base_url}/metadata/locations/{location_id}")
        assert response.status_code == 404
        
        # Verify weather data for each location is deleted
        check_location_timeseries_deleted(http_client, base_url, location_id)
    
    # Verify all households are deleted
    for household_id in all_household_ids_to_check:
        response = http_client.get(f"{base_url}/metadata/households/{household_id}")
        assert response.status_code == 404
        
        # Verify timeseries data for each household is deleted
        check_household_timeseries_deleted(http_client, base_url, household_id)
    
    # Verify price data for this region is deleted
    check_price_region_timeseries_deleted(http_client, base_url, price_region_id_beta)


def test_delete_price_region_not_found(http_client, base_url):
    """Test deletion of non-existent price region returns 404."""
    non_existent_id = 999999
    response = http_client.delete(f"{base_url}/metadata/price_regions/{non_existent_id}")
    assert response.status_code == 404
    response_data = response.json()
    assert "not found" in response_data["detail"].lower()


# --- Test Edge Cases ---

def test_create_and_delete_empty_entities(http_client, base_url):
    """Test creation and deletion of entities without associated data."""
    
    # Create a price region without any locations
    empty_pr = {"name": "Empty PR for Testing", "bidding_zone_eic_code": "10Y1001A1001A90H"}
    response = http_client.post(f"{base_url}/metadata/price_regions", json=empty_pr)
    assert response.status_code == 200
    empty_pr_id = response.json()["price_region_id"]
    
    # Delete the empty price region
    response = http_client.delete(f"{base_url}/metadata/price_regions/{empty_pr_id}")
    assert response.status_code == 200
    
    # Verify deletion
    response = http_client.get(f"{base_url}/metadata/price_regions/{empty_pr_id}")
    assert response.status_code == 404
    
    # Create a price region and location without any households
    empty_pr = {"name": "Empty PR 2", "bidding_zone_eic_code": "10Y1001A1001A91H"}
    response = http_client.post(f"{base_url}/metadata/price_regions", json=empty_pr)
    assert response.status_code == 200
    empty_pr_id = response.json()["price_region_id"]
    
    empty_location = {
        "name": "Empty Location",
        "price_region_id": empty_pr_id,
        "latitude": 52.0,
        "longitude": 11.0
    }
    response = http_client.post(f"{base_url}/metadata/locations", json=empty_location)
    assert response.status_code == 200
    empty_location_id = response.json()["location_id"]
    
    # Delete the empty location
    response = http_client.delete(f"{base_url}/metadata/locations/{empty_location_id}")
    assert response.status_code == 200
    
    # Verify location deletion
    response = http_client.get(f"{base_url}/metadata/locations/{empty_location_id}")
    assert response.status_code == 404
    
    # Clean up price region
    response = http_client.delete(f"{base_url}/metadata/price_regions/{empty_pr_id}")
    assert response.status_code == 200


# --- Test Error Handling ---

def test_delete_endpoints_with_invalid_ids(http_client, base_url):
    """Test that deletion endpoints handle invalid ID formats gracefully."""
    # Test with non-numeric ID (should return 422 for validation error)
    invalid_ids = ["abc", "null", "undefined", "-1"]
    
    for invalid_id in invalid_ids:
        # Test household deletion with invalid ID
        response = http_client.delete(f"{base_url}/metadata/households/{invalid_id}")
        # Should return either 404 or 422 depending on validation
        assert response.status_code in [404, 422, 400]
        
        # Test location deletion with invalid ID
        response = http_client.delete(f"{base_url}/metadata/locations/{invalid_id}")
        assert response.status_code in [404, 422, 400]
        
        # Test price region deletion with invalid ID
        response = http_client.delete(f"{base_url}/metadata/price_regions/{invalid_id}")
        assert response.status_code in [404, 422, 400]


def test_verify_all_test_data_cleaned_up(http_client, base_url):
    """Final test to verify all test data has been properly cleaned up."""
    
    # Check that test entities no longer exist
    response = http_client.get(f"{base_url}/metadata/price_regions")
    assert response.status_code == 200
    regions = response.json()
    
    # Should only contain regions that were not part of our test data
    test_region_names = ["Test Region Alpha", "Test Region Beta", "Region To Delete", "Empty PR for Testing", "Empty PR 2"]
    for region in regions:
        assert region["name"] not in test_region_names, f"Test region '{region['name']}' was not properly cleaned up"
    
    response = http_client.get(f"{base_url}/metadata/locations")
    assert response.status_code == 200
    locations = response.json()
    
    # Should only contain locations that were not part of our test data  
    test_location_names = ["Loc1InRegionBeta", "Loc2InRegionBeta", "Location To Delete", "Second Location for PR Deletion", "Empty Location"]
    for location in locations:
        assert location["name"] not in test_location_names, f"Test location '{location['name']}' was not properly cleaned up"
    
    response = http_client.get(f"{base_url}/metadata/households")
    assert response.status_code == 200
    households = response.json()
    
    # Should only contain households that were not part of our test data
    test_household_names = ["Household1Loc1", "Household1Loc2", "Household To Delete", "Household 1 for Location Deletion", "Household 2 for Location Deletion", "Household in Second Location"]
    for household in households:
        assert household["name"] not in test_household_names, f"Test household '{household['name']}' was not properly cleaned up"

from datetime import datetime
from typing import Set, Dict, Tuple, List

from sqlalchemy import select

from api.db import database
import api.db as db
from api.services.fetch_electricity_price_data import fetch_external_electricity_prices
from api.services.fetch_weather_data import fetch_external_weather_observations, fetch_external_weather_forecasts
from api.helpers.database_queries import get_existing_weather_time_ranges
from api.helpers.time_range_utils import calculate_missing_time_ranges


async def fetch_external_data(
        location_time_ranges: Dict[int, Tuple[datetime, datetime]],
        price_region_ids: Set[int],
        price_start_time: datetime,
        price_end_time: datetime
) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """
    Fetches weather and price data for the relevant location/region IDs.
    Weather data is fetched per location with individual time ranges.
    Only fetches weather data that doesn't already exist in the database.
    Price data is fetched per region with the global time range.
    """
    weather_obs_to_insert: List[Dict] = []
    weather_fc_to_insert: List[Dict] = []
    prices_to_insert: List[Dict] = []

    # Get existing weather data ranges for all locations
    location_ids = set(location_time_ranges.keys())
    all_start_time = min(start_time for start_time, _ in location_time_ranges.values())
    all_end_time = max(end_time for _, end_time in location_time_ranges.values())
    
    print(f"Checking existing weather data for {len(location_ids)} locations from {all_start_time} to {all_end_time}")
    existing_obs_ranges, existing_fc_ranges = await get_existing_weather_time_ranges(
        location_ids, all_start_time, all_end_time
    )

    # Fetch weather data once for each unique location ID with its specific time range
    for loc_id, (start_time, end_time) in location_time_ranges.items():
        # Get longitude and latitude from the location ID
        query = select(db.locations_tbl.c.latitude, db.locations_tbl.c.longitude).where(
            db.locations_tbl.c.location_id == loc_id)
        location = await database.fetch_one(query)
        if not location:
            print(f"Warning: Location ID {loc_id} not found. Skipping weather fetch for this location.")
            continue
        lat = location['latitude']
        lon = location['longitude']

        # Calculate missing observation time ranges
        existing_obs = existing_obs_ranges.get(loc_id, [])
        missing_obs_ranges = calculate_missing_time_ranges(start_time, end_time, existing_obs)
        
        # Calculate missing forecast time ranges
        existing_fc = existing_fc_ranges.get(loc_id, [])
        missing_fc_ranges = calculate_missing_time_ranges(start_time, end_time, existing_fc)

        # Fetch only missing observation data
        if missing_obs_ranges:
            print(f"Fetching {len(missing_obs_ranges)} missing observation time range(s) for location {loc_id}")
            for obs_start, obs_end in missing_obs_ranges:
                print(f"  - Observations from {obs_start} to {obs_end}")
                obs_data = await fetch_external_weather_observations(loc_id, lat, lon, obs_start, obs_end)
                weather_obs_to_insert.extend(obs_data)
        else:
            print(f"All weather observations already exist for location {loc_id} in requested time range")

        # Fetch only missing forecast data
        if missing_fc_ranges:
            print(f"Fetching {len(missing_fc_ranges)} missing forecast time range(s) for location {loc_id}")
            for fc_start, fc_end in missing_fc_ranges:
                print(f"  - Forecasts from {fc_start} to {fc_end}")
                fc_data = await fetch_external_weather_forecasts(loc_id, lat, lon, fc_start, fc_end)
                weather_fc_to_insert.extend(fc_data)
        else:
            print(f"All weather forecasts already exist for location {loc_id} in requested time range")

    # Fetch price data once for each unique region ID present in the batch.
    # This avoids redundant calls if multiple locations share the same region.
    for reg_id in price_region_ids:
        print(f"Fetching electricity prices for region {reg_id} from {price_start_time} to {price_end_time}")
        price_data = await fetch_external_electricity_prices(reg_id, price_start_time, price_end_time)
        prices_to_insert.extend(price_data)

    return weather_obs_to_insert, weather_fc_to_insert, prices_to_insert

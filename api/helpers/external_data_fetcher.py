from datetime import datetime, timezone
from typing import Set, Dict, Tuple, List

from sqlalchemy import select, and_

from api.db import database
import api.db as db
from api.services.fetch_electricity_price_data import fetch_external_electricity_prices
from api.services.fetch_weather_data import fetch_external_weather_observations, fetch_external_weather_forecasts
from api.helpers.database_queries import get_existing_weather_time_ranges
from api.helpers.time_range_utils import calculate_missing_time_ranges
from api.helpers.synthetic_forecast.main import create_synthetic_forecast


_MIN_FORECAST_DATE = datetime(2020, 1, 1, tzinfo=timezone.utc)
_HISTORICAL_END_DATE = datetime(2023, 12, 31, 23, 59, 59, tzinfo=timezone.utc)


async def _handle_historical_data(
    loc_id: int, lat: float, lon: float, start_time: datetime,
    existing_obs_ranges_for_loc: List[Tuple[datetime, datetime]],
    existing_fc_ranges_for_loc: List[Tuple[datetime, datetime]]
) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """
    Handles fetching historical weather data and generating synthetic forecasts.
    It ensures that the synthetic forecast generation has access to all historical data,
    both existing and newly fetched, while only returning the new data for insertion.
    """
    print(f"Request for location {loc_id} starts before {_MIN_FORECAST_DATE}. Checking for historical data for synthetic forecast generation.")
    historical_start = _MIN_FORECAST_DATE
    historical_end = _HISTORICAL_END_DATE

    # 1. Fetch pre-2020 observation data to use as a base for synthetic forecasts
    # First, check what's in the DB
    pre_2020_obs_query = select(db.weather_obs_tbl).where(
        and_(db.weather_obs_tbl.c.location_id == loc_id,
             db.weather_obs_tbl.c.datetime >= start_time,
             db.weather_obs_tbl.c.datetime < _MIN_FORECAST_DATE))
    pre_2020_obs_data = [dict(row) for row in await database.fetch_all(pre_2020_obs_query)]

    # Then, fetch any missing pre-2020 observations from the external API
    existing_pre_2020_ranges = [(r['datetime'], r['datetime']) for r in pre_2020_obs_data]
    missing_pre_2020_ranges = calculate_missing_time_ranges(start_time, _MIN_FORECAST_DATE, existing_pre_2020_ranges)

    newly_fetched_pre_2020_obs = []
    if missing_pre_2020_ranges:
        print(f"Fetching {len(missing_pre_2020_ranges)} missing pre-2020 observation time range(s) for location {loc_id}")
        for obs_start, obs_end in missing_pre_2020_ranges:
            hist_obs_data = await fetch_external_weather_observations(loc_id, lat, lon, obs_start, obs_end)
            if hist_obs_data:
                newly_fetched_pre_2020_obs.extend(hist_obs_data)
    
    pre_2020_obs_data.extend(newly_fetched_pre_2020_obs)


    # 2. Fetch existing historical data from the database (2020-2024)
    obs_query = select(db.weather_obs_tbl).where(
        and_(db.weather_obs_tbl.c.location_id == loc_id,
             db.weather_obs_tbl.c.datetime >= historical_start,
             db.weather_obs_tbl.c.datetime <= historical_end))
    existing_obs_data = [dict(row) for row in await database.fetch_all(obs_query)]

    fc_query = select(db.weather_fc_tbl).where(
        and_(db.weather_fc_tbl.c.location_id == loc_id,
             db.weather_fc_tbl.c.target_time >= historical_start,
             db.weather_fc_tbl.c.target_time <= historical_end))
    existing_fc_data = [dict(row) for row in await database.fetch_all(fc_query)]

    # 3. Determine and fetch missing historical data from the external API
    # 3.1 Calculate and fetch missing historical observation data
    newly_fetched_obs = []
    missing_hist_obs_ranges = calculate_missing_time_ranges(historical_start, historical_end, existing_obs_ranges_for_loc)
    if missing_hist_obs_ranges:
        print(f"Fetching {len(missing_hist_obs_ranges)} missing historical observation time range(s) for location {loc_id}")
        for obs_start, obs_end in missing_hist_obs_ranges:
            hist_obs_data = await fetch_external_weather_observations(loc_id, lat, lon, obs_start, obs_end)
            if hist_obs_data:
                newly_fetched_obs.extend(hist_obs_data)

    # 3.2 Calculate and fetch missing historical forecast data
    newly_fetched_fc = []
    missing_hist_fc_ranges = calculate_missing_time_ranges(historical_start, historical_end, existing_fc_ranges_for_loc)
    if missing_hist_fc_ranges:
        print(f"Fetching {len(missing_hist_fc_ranges)} missing historical forecast time range(s) for location {loc_id}")
        for fc_start, fc_end in missing_hist_fc_ranges:
            hist_fc_data = await fetch_external_weather_forecasts(loc_id, lat, lon, fc_start, fc_end)
            if hist_fc_data:
                newly_fetched_fc.extend(hist_fc_data)

    # 4. Combine existing and new data to pass to the forecast generator
    all_historical_obs = existing_obs_data + newly_fetched_obs
    all_historical_fc = existing_fc_data + newly_fetched_fc

    # 5. Generate synthetic forecast using the complete historical dataset
    synthetic_fc_result = await create_synthetic_forecast(
        loc_id, start_time, _MIN_FORECAST_DATE, pre_2020_obs_data, all_historical_obs, all_historical_fc
    )
    # Extract only the synthetic forecast data (first element of the tuple)
    synthetic_fc_data = synthetic_fc_result[0] if synthetic_fc_result else []

    # 6. Return only the newly fetched data for insertion by the caller
    # The newly fetched pre-2020 data also needs to be inserted.
    newly_fetched_obs.extend(newly_fetched_pre_2020_obs)
    return newly_fetched_obs, newly_fetched_fc, synthetic_fc_data


async def _fetch_weather_for_location(
    loc_id: int, lat: float, lon: float, start_time: datetime, end_time: datetime,
    existing_obs_ranges: Dict[int, List[Tuple[datetime, datetime]]],
    existing_fc_ranges: Dict[int, List[Tuple[datetime, datetime]]]
) -> Tuple[List[Dict], List[Dict]]:
    """
    Fetches missing weather observation and forecast data for a single location.
    """
    weather_obs_to_insert = []
    weather_fc_to_insert = []

    # Calculate missing observation time ranges
    missing_obs_ranges = calculate_missing_time_ranges(start_time, end_time, existing_obs_ranges.get(loc_id, []))
    if missing_obs_ranges:
        print(f"Fetching {len(missing_obs_ranges)} missing observation time range(s) for location {loc_id}")
        for obs_start, obs_end in missing_obs_ranges:
            print(f"  - Observations from {obs_start} to {obs_end}")
            obs_data = await fetch_external_weather_observations(loc_id, lat, lon, obs_start, obs_end)
            weather_obs_to_insert.extend(obs_data)

    # Calculate missing forecast time ranges
    missing_fc_ranges = calculate_missing_time_ranges(start_time, end_time, existing_fc_ranges.get(loc_id, []))
    if missing_fc_ranges:
        print(f"Fetching {len(missing_fc_ranges)} missing forecast time range(s) for location {loc_id}")
        for fc_start, fc_end in missing_fc_ranges:
            print(f"  - Forecasts from {fc_start} to {fc_end}")
            fc_data = await fetch_external_weather_forecasts(loc_id, lat, lon, fc_start, fc_end)
            weather_fc_to_insert.extend(fc_data)

    return weather_obs_to_insert, weather_fc_to_insert


async def _fetch_price_data(
    price_region_ids: Set[int], start_time: datetime, end_time: datetime
) -> List[Dict]:
    """
    Fetches electricity price data for the given regions and time range.
    """
    prices_to_insert = []
    # Fetch price data once for each unique region ID present in the batch.
    # This avoids redundant calls if multiple locations share the same region.
    for reg_id in price_region_ids:
        print(f"Fetching electricity prices for region {reg_id} from {start_time} to {end_time}")
        price_data = await fetch_external_electricity_prices(reg_id, start_time, end_time)
        prices_to_insert.extend(price_data)
    return prices_to_insert


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

        # Define the time periods
        historical_period_end = min(end_time, _MIN_FORECAST_DATE)
        future_period_start = max(start_time, _MIN_FORECAST_DATE)

        # 1. Handle historical/synthetic period
        if start_time < _MIN_FORECAST_DATE:
            # Check if synthetic data for this period already exists to avoid re-generating it.
            pre_2020_fc_exists = False
            if loc_id in existing_fc_ranges:
                for fc_start, fc_end in existing_fc_ranges[loc_id]:
                    if fc_start <= start_time and fc_end >= _MIN_FORECAST_DATE:
                        pre_2020_fc_exists = True
                        print(f"Synthetic forecast for location {loc_id} in range {start_time}-{_MIN_FORECAST_DATE} already exists. Skipping generation.")
                        break
            
            if not pre_2020_fc_exists:
                # Pass only the relevant time range to the handler
                hist_obs, hist_fc, synthetic_fc = await _handle_historical_data(
                    loc_id, lat, lon, start_time,
                    existing_obs_ranges.get(loc_id, []),
                    existing_fc_ranges.get(loc_id, [])
                )
                weather_obs_to_insert.extend(hist_obs)
                weather_fc_to_insert.extend(hist_fc)
                weather_fc_to_insert.extend(synthetic_fc)

                # Update the existing ranges with the data we just fetched
                # to prevent _fetch_weather_for_location from fetching it again.
                for obs in hist_obs:
                    existing_obs_ranges.setdefault(loc_id, []).append((obs['datetime'], obs['datetime']))
                for fc in hist_fc:
                    existing_fc_ranges.setdefault(loc_id, []).append((fc['target_time'], fc['target_time']))


        # 2. Handle standard forecast/observation period
        if future_period_start < end_time:
            obs_data, fc_data = await _fetch_weather_for_location(
                loc_id, lat, lon, future_period_start, end_time, existing_obs_ranges, existing_fc_ranges
            )
            weather_obs_to_insert.extend(obs_data)
            weather_fc_to_insert.extend(fc_data)

    prices_to_insert = await _fetch_price_data(price_region_ids, price_start_time, price_end_time)

    return weather_obs_to_insert, weather_fc_to_insert, prices_to_insert


from datetime import datetime
from typing import Set, Dict, Tuple, Optional, List

from fastapi import HTTPException
from sqlalchemy import select, func, Table

from api.db import database
import api.db as db
from api.helpers.time_range_utils import build_continuous_ranges


async def get_existing_weather_time_ranges(
        location_ids: Set[int], 
        time_start: datetime, 
        time_end: datetime
) -> Tuple[Dict[int, List[Tuple[datetime, datetime]]], Dict[int, List[Tuple[datetime, datetime]]]]:
    """
    Get existing weather data time ranges for locations within the specified time window.
    Returns a tuple of (existing_obs_ranges, existing_fc_ranges) where each is a dict
    mapping location_id to a list of (start_time, end_time) tuples representing continuous time ranges.
    """
    obs_ranges = {}
    fc_ranges = {}
    
    for location_id in location_ids:
        # Build actual observation ranges by detecting hourly gaps
        ts_query = select(db.weather_obs_tbl.c.datetime).where(
            db.weather_obs_tbl.c.location_id == location_id,
            db.weather_obs_tbl.c.datetime >= time_start,
            db.weather_obs_tbl.c.datetime <= time_end
        ).order_by(db.weather_obs_tbl.c.datetime)
        rows = await database.fetch_all(ts_query)
        times = [r['datetime'] for r in rows]
        obs_ranges[location_id] = build_continuous_ranges(times, time_start, time_end)

        # Build actual forecast ranges by detecting hourly gaps
        ts_fc_query = select(db.weather_fc_tbl.c.target_time).where(
            db.weather_fc_tbl.c.location_id == location_id,
            db.weather_fc_tbl.c.target_time >= time_start,
            db.weather_fc_tbl.c.target_time <= time_end
        ).order_by(db.weather_fc_tbl.c.target_time)
        fc_rows = await database.fetch_all(ts_fc_query)
        fc_times = [r['target_time'] for r in fc_rows]
        fc_ranges[location_id] = build_continuous_ranges(fc_times, time_start, time_end)
    
    return obs_ranges, fc_ranges


async def get_household_metadata(household_ids: Set[int]) -> Tuple[Dict[int, int], Set[int], Set[int]]:
    """
    Fetches location and region IDs for given household IDs.
    Returns a tuple containing:
    - household_to_location: Mapping of household ID to location ID.
    - location_ids: Set of unique location IDs involved across all households in the input set.
    - price_region_ids: Set of unique region IDs involved across all locations.
    """    
    location_ids: Set[int] = set()
    price_region_ids: Set[int] = set()

    query_households = select(db.households_tbl.c.household_id, db.households_tbl.c.location_id).where(
        db.households_tbl.c.household_id.in_(household_ids))
    fetched_households = await database.fetch_all(query_households)
    household_to_location = {h['household_id']: h['location_id'] for h in fetched_households}

    if len(household_to_location) != len(household_ids):
        missing_hids = household_ids - set(household_to_location.keys())
        raise HTTPException(status_code=404, detail=f"Could not find metadata for household IDs: {missing_hids}")

    location_ids.update(household_to_location.values())

    query_locations = select(db.locations_tbl.c.location_id, db.locations_tbl.c.price_region_id).where(
        db.locations_tbl.c.location_id.in_(location_ids))
    fetched_locations = await database.fetch_all(query_locations)
    location_to_region = {loc['location_id']: loc['price_region_id'] for loc in fetched_locations}

    if len(location_to_region) != len(location_ids):
        missing_lids = location_ids - set(location_to_region.keys())
        raise HTTPException(status_code=404, detail=f"Could not find metadata for location IDs: {missing_lids}")

    price_region_ids.update(location_to_region.values())

    # We return the sets of unique location_ids and price_region_ids because
    # external data needs to be fetched once per unique location/region
    # present in the batch of households.
    return household_to_location, location_ids, price_region_ids


async def get_existing_time_range(table: Table, household_ids: Set[int]) -> Tuple[
    Optional[datetime], Optional[datetime]]:
    """Queries a table for the min/max timestamps for a set of household IDs."""
    if not household_ids:
        return None, None
    query = select(
        func.min(table.c.time).label("min_time"),
        func.max(table.c.time).label("max_time")
    ).where(table.c.household_id.in_(household_ids))
    result = await database.fetch_one(query)
    if result and result["min_time"] is not None and result["max_time"] is not None:
        return result["min_time"], result["max_time"]
    return None, None

from datetime import datetime
from typing import List, Dict, Set

from fastapi import APIRouter
from sqlalchemy import Table

from api.db import database
import api.db as db
from api.schemas import BulkPV, BulkLoad
from api.services.fetch_simulated_pv_data import fetch_simulated_pv_data_per_household
from api.helpers.time_range_utils import (
    calculate_overlap,
    calculate_household_time_ranges,
    calculate_location_time_ranges
)
from api.helpers.database_queries import (
    get_household_metadata,
    get_existing_time_range
)
from api.helpers.external_data_fetcher import fetch_external_data
from api.helpers.bulk_insert import insert_records

router = APIRouter(prefix="/ingest", tags=["ingest"])


# --- API Endpoints ---

@router.post("/pv_generation")
async def ingest_pv(payload: BulkPV):
    """Ingests PV generation data and fetches related external data if load data exists for the overlap."""
    records = [item.model_dump() for item in payload.data]
    return await _handle_ingestion(records, db.pv_tbl, db.load_tbl, "pv")


@router.post("/load_data")
async def ingest_load(payload: BulkLoad):
    """
    Ingests load data.
    Optionally fetches/simulates PV data and related external data if `simulate_pv_generation` is true.
    Otherwise, fetches related external data if PV data exists for the overlap.
    """    
    records = [item.model_dump() for item in payload.data]
    simulate_flag = bool(payload.simulate_pv_generation)
    return await _handle_ingestion(
        records,
        db.load_tbl,
        db.pv_tbl,
        "load",
        simulate_pv_generation=simulate_flag
    )


# --- Core Ingestion Logic ---

async def _handle_ingestion(
        records: List[Dict],
        primary_table: Table,
        secondary_table: Table,
        record_type: str,  # e.g., "load" or "pv"
        simulate_pv_generation: bool = False
):
    """Handles the ingestion process for load or PV data."""

    print(f"Handling ingestion for {record_type} data...")

    if not records:
        return {f"inserted_{record_type}": 0, "detail": f"No {record_type} data provided."}

    household_ids: Set[int] = set(r['household_id'] for r in records)
    min_incoming_time: datetime = min(r['time'] for r in records)
    max_incoming_time: datetime = max(r['time'] for r in records)

    # Get metadata: household->location mapping, and UNIQUE location/region IDs for this batch
    household_to_location, unique_location_ids, unique_price_region_ids = await get_household_metadata(household_ids)

    # Simulation mode: fetch and insert weather/prices before simulating PV
    if record_type == "load" and simulate_pv_generation:
        # Calculate individual time ranges for each household
        household_time_ranges = calculate_household_time_ranges(records)
        # Calculate location-specific time ranges based on households at each location
        location_time_ranges = calculate_location_time_ranges(household_time_ranges, household_to_location)
        # For price data, use the overall min/max since prices are per region, not per location
        sim_start_time = min_incoming_time
        sim_end_time = max_incoming_time
        
        print("Fetching external weather and price data for simulation period:")
        print("  - Weather data per location with individual time ranges")
        print(f"  - Price data for overall period: {sim_start_time} to {sim_end_time}")
        
        weather_obs, weather_fc, prices = await fetch_external_data(
            location_time_ranges, unique_price_region_ids, sim_start_time, sim_end_time
        )
        async with database.transaction():
            # insert load data
            pk_cols = [col.name for col in primary_table.primary_key.columns]
            await insert_records(records, primary_table, record_type, unique_keys=pk_cols)

            # insert fetched weather and prices
            await insert_records(weather_obs, db.weather_obs_tbl, "weather observation", unique_keys=["location_id", "datetime"])
            await insert_records(weather_fc, db.weather_fc_tbl, "weather forecast", unique_keys=["location_id", "forecast_run", "target_time"])
            await insert_records(prices, db.price_tbl, "electricity price", unique_keys=["price_region_id", "time"])

            # simulate PV for each household with its individual time range
            simulated = await fetch_simulated_pv_data_per_household(household_time_ranges)
            await insert_records(simulated, db.pv_tbl, "simulated PV", unique_keys=["household_id", "time"])
        return {
            f"inserted_{record_type}": len(records),
            "fetched_weather_obs": len(weather_obs),
            "fetched_weather_fc": len(weather_fc),
            "fetched_prices": len(prices),
            "simulated_pv_records": len(simulated),
            "detail": "Load data ingested and PV simulated using fetched weather."
        }

    # Non-simulation mode: calculate overlap with existing data
    # Calculate individual time ranges for each household from incoming records
    household_time_ranges = calculate_household_time_ranges(records)
    
    # Get time range of existing data in the *other* table for each household
    min_secondary_time, max_secondary_time = await get_existing_time_range(secondary_table, household_ids)

    # Calculate overlap between incoming data and existing secondary data
    overlap_start, overlap_end = calculate_overlap(
        min_incoming_time, max_incoming_time,
        min_secondary_time, max_secondary_time
    )

    weather_obs_to_insert: List[Dict] = []
    weather_fc_to_insert: List[Dict] = []
    prices_to_insert: List[Dict] = []

    if overlap_start and overlap_end:
        print(f"Overlap detected. Fetching external data for overlap period: {overlap_start} to {overlap_end}")
        # For weather data, only fetch for the overlapping period for each location
        # Filter household time ranges to only include the overlap period
        overlap_household_time_ranges = {}
        for household_id, (household_start, household_end) in household_time_ranges.items():
            # Calculate overlap for this specific household
            household_overlap_start, household_overlap_end = calculate_overlap(
                household_start, household_end,
                min_secondary_time, max_secondary_time
            )
            if household_overlap_start and household_overlap_end:
                overlap_household_time_ranges[household_id] = (household_overlap_start, household_overlap_end)
        
        if overlap_household_time_ranges:
            # Calculate location time ranges for the overlap period only
            overlap_location_time_ranges = calculate_location_time_ranges(
                overlap_household_time_ranges, household_to_location
            )
            
            print(f"Fetching weather data for {len(overlap_location_time_ranges)} locations with individual overlap periods")
            weather_obs_to_insert, weather_fc_to_insert, prices_to_insert = await fetch_external_data(
                overlap_location_time_ranges, unique_price_region_ids, overlap_start, overlap_end
            )
        else:
            print("No household-level overlap found, skipping weather data fetch")
    else:
        print(f"No time overlap found with existing {secondary_table.name} data for these households, and not simulating PV. Skipping external data fetch.")

    async with database.transaction():
        pk_cols = [col.name for col in primary_table.primary_key.columns]
        await insert_records(records, primary_table, record_type, unique_keys=pk_cols)
        await insert_records(weather_obs_to_insert, db.weather_obs_tbl, "weather observation", unique_keys=["location_id", "datetime"])
        await insert_records(weather_fc_to_insert, db.weather_fc_tbl, "weather forecast", unique_keys=["location_id", "forecast_run", "target_time"])
        await insert_records(prices_to_insert, db.price_tbl, "electricity price", unique_keys=["price_region_id", "time"])

    return {
        f"inserted_{record_type}": len(records),
        "fetched_weather_obs": len(weather_obs_to_insert),
        "fetched_weather_fc": len(weather_fc_to_insert),
        "fetched_prices": len(prices_to_insert),
        "simulated_pv_records": "No simulation performed",
        "detail": f"{record_type.capitalize()} data ingested. Related data fetched for overlapping time period or simulation period if applicable."
    }

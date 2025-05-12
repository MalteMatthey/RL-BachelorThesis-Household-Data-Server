from datetime import datetime
from typing import List, Dict, Set, Tuple, Optional, Any

from fastapi import APIRouter, HTTPException
from sqlalchemy import select, func, Table
from sqlalchemy.dialects.postgresql import insert as pg_insert

from math import floor

import api.db as db
from api.db import database
from api.schemas import BulkLoad, BulkPV
from api.services.fetch_electricity_price_data import fetch_external_electricity_prices
from api.services.fetch_weather_data import fetch_external_weather_observations, fetch_external_weather_forecasts

router = APIRouter(prefix="/ingest", tags=["ingest"])


# --- API Endpoints ---

@router.post("/pv_generation")
async def ingest_pv(payload: BulkPV):
    """Ingests PV generation data and fetches related external data if load data exists for the overlap."""
    records = [item.model_dump() for item in payload.data]
    return await _handle_ingestion(records, db.pv_tbl, db.load_tbl, "pv")


@router.post("/load_data")
async def ingest_load(payload: BulkLoad):
    """Ingests load data and fetches related external data if PV data exists for the overlap."""
    records = [item.model_dump() for item in payload.data]
    return await _handle_ingestion(records, db.load_tbl, db.pv_tbl, "load")


# --- Helper Functions ---

async def _get_household_metadata(household_ids: Set[int]) -> Tuple[Dict[int, int], Set[int], Set[int]]:
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


async def _get_existing_time_range(table: Table, household_ids: Set[int]) -> Tuple[
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


def _calculate_overlap(
        min1: Optional[datetime], max1: Optional[datetime],
        min2: Optional[datetime], max2: Optional[datetime]
) -> Tuple[Optional[datetime], Optional[datetime]]:
    """Calculates the overlapping time range between two intervals."""
    if not all([min1, max1, min2, max2]):
        return None, None  # No overlap if one range is missing

    overlap_start = max(min1, min2)
    overlap_end = min(max1, max2)

    if overlap_start < overlap_end:
        return overlap_start, overlap_end
    else:
        return None, None  # No overlap


async def _fetch_external_data(
        location_ids: Set[int], price_region_ids: Set[int],
        start_time: datetime, end_time: datetime
) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """
    Fetches weather and price data for the unique location/region IDs
    relevant to the current batch of ingested data, within the specified time range.
    A batch might contain households from multiple locations/regions.
    """
    weather_obs_to_insert: List[Dict] = []
    weather_fc_to_insert: List[Dict] = []
    prices_to_insert: List[Dict] = []

    # Fetch weather data once for each unique location ID present in the batch.
    # This avoids redundant calls if multiple households share the same location.
    for loc_id in location_ids:
        # Get longitude and latitude from the location ID
        query = select(db.locations_tbl.c.latitude, db.locations_tbl.c.longitude).where(
            db.locations_tbl.c.location_id == loc_id)
        location = await database.fetch_one(query)
        if not location:
            print(f"Warning: Location ID {loc_id} not found. Skipping weather fetch for this location.")
            continue
        lat = location['latitude']
        lon = location['longitude']

        print(f"Fetching weather data for location {loc_id} (lat: {lat}, lon: {lon}) from {start_time} to {end_time}")
        # Pass location_id to the fetching functions
        obs_data = await fetch_external_weather_observations(loc_id, lat, lon, start_time, end_time)
        fc_data = await fetch_external_weather_forecasts(loc_id, lat, lon, start_time, end_time)
        weather_obs_to_insert.extend(obs_data)
        weather_fc_to_insert.extend(fc_data)

    # Fetch price data once for each unique region ID present in the batch.
    # This avoids redundant calls if multiple locations share the same region.
    for reg_id in price_region_ids:
        print(f"Fetching electricity prices for region {reg_id} from {start_time} to {end_time}")
        price_data = await fetch_external_electricity_prices(reg_id, start_time, end_time)
        prices_to_insert.extend(price_data)

    return weather_obs_to_insert, weather_fc_to_insert, prices_to_insert


def _chunkify(records: list, chunk_size: int):
    for i in range(0, len(records), chunk_size):
        yield records[i: i + chunk_size]


async def _insert_records(
        records: List[Dict[str, Any]],
        table,
        label: str,
        *,
        unique_keys: List[str]
):
    """
    Insert or update in chunks so we don't exceed Postgres' parameter limit.
    """
    if not records:
        return

    # how many columns per row
    # Ensure there's at least one record to get keys from, and all records have same keys.
    if not records[0]:
        print(f"Warning: First record for {label} is empty, cannot determine columns per row.")
        return

    cols_per_row = len(records[0].keys())
    if cols_per_row == 0:
        print(f"Warning: No columns found in records for {label}, skipping insertion.")
        return

    max_args = 32767  # PostgreSQL default limit for bind parameters
    # floor so we never exceed the limit
    rows_per_batch = floor(max_args / cols_per_row) or 1

    print(f"Preparing to insert/update {len(records)} {label} records in batches of up to {rows_per_batch}...")

    processed_total = 0
    for batch_idx, batch in enumerate(_chunkify(records, rows_per_batch)):
        if not batch:
            continue

        insert_stmt = pg_insert(table).values(batch)

        update_values = {
            col.name: insert_stmt.excluded[col.name]
            for col in table.columns
            if col.name not in unique_keys
        }

        if not update_values:
            upsert_query = insert_stmt.on_conflict_do_nothing(
                index_elements=unique_keys
            )
        else:
            upsert_query = insert_stmt.on_conflict_do_update(
                index_elements=unique_keys,
                set_=update_values
            )

        try:
            await database.execute(upsert_query)
            processed_total += len(batch)
        except Exception as e:
            print(f"Error during batch insert/update for {label} (batch {batch_idx + 1}, {len(batch)} records): {e}")
            raise  # Re-raise the exception to be handled by the caller

    print(f"Successfully processed {processed_total} {label} records.")


async def _handle_ingestion(
        records: List[Dict],
        primary_table: Table,
        secondary_table: Table,
        record_type: str  # e.g., "load" or "pv"
):
    """Handles the ingestion process for load or PV data."""

    print(f"Handling ingestion for {record_type} data...")

    if not records:
        return {f"inserted_{record_type}": 0, "detail": f"No {record_type} data provided."}

    household_ids: Set[int] = set(r['household_id'] for r in records)
    min_incoming_time: datetime = min(r['time'] for r in records)
    max_incoming_time: datetime = max(r['time'] for r in records)

    # Get metadata: household->location mapping, and UNIQUE location/region IDs for this batch
    _, unique_location_ids, unique_price_region_ids = await _get_household_metadata(household_ids)

    # Get time range of existing data in the *other* table
    min_secondary_time, max_secondary_time = await _get_existing_time_range(secondary_table, household_ids)

    # Calculate overlap between incoming data and existing secondary data
    min_fetch_time, max_fetch_time = _calculate_overlap(
        min_incoming_time, max_incoming_time,
        min_secondary_time, max_secondary_time
    )

    weather_obs_to_insert: List[Dict] = []
    weather_fc_to_insert: List[Dict] = []
    prices_to_insert: List[Dict] = []

    # Fetch external data only if there's an overlap
    if min_fetch_time and max_fetch_time:
        print(f"Overlap detected. Fetching external data from {min_fetch_time} to {max_fetch_time}")
        # Pass the unique sets of IDs for fetching. _fetch_external_data handles
        # fetching once per unique ID.
        weather_obs_to_insert, weather_fc_to_insert, prices_to_insert = await _fetch_external_data(
            unique_location_ids, unique_price_region_ids, min_fetch_time, max_fetch_time
        )
    else:
        print(
            f"No time overlap found with existing {secondary_table.name} data for these households, or secondary data missing. Skipping external data fetch.")

    async with database.transaction():
        # --- primary data (load or PV) ---
        # derive the PK columns from the table
        pk_cols = [col.name for col in primary_table.primary_key.columns]
        await _insert_records(
            records,
            primary_table,
            record_type,
            unique_keys=pk_cols
        )

        # --- weather observations ---
        await _insert_records(
            weather_obs_to_insert,
            db.weather_obs_tbl,
            "weather observation",
            unique_keys=["location_id", "datetime"]
        )

        # --- weather forecasts ---
        await _insert_records(
            weather_fc_to_insert,
            db.weather_fc_tbl,
            "weather forecast",
            unique_keys=["location_id", "forecast_run", "target_time"]
        )

        # --- electricity prices ---
        await _insert_records(
            prices_to_insert,
            db.price_tbl,
            "electricity price",
            unique_keys=["price_region_id", "time"]
        )

    return {
        f"inserted_{record_type}": len(records),
        "fetched_weather_obs": len(weather_obs_to_insert),
        "fetched_weather_fc": len(weather_fc_to_insert),
        "fetched_prices": len(prices_to_insert),
        "detail": f"{record_type.capitalize()} data ingested. Related data fetched for overlapping time period if applicable."
    }

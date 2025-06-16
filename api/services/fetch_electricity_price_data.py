import os
import httpx
import pandas as pd
import xml.etree.ElementTree as ET
from pydantic import ValidationError
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

from ..schemas import PriceIn
from .b2_backup import b2_handler
from api.db import database as app_db

# --- Configuration ---
ENTSOE_API_KEY = os.getenv("ENTSOE_API_KEY")
if not ENTSOE_API_KEY:
    print("Warning: ENTSOE_API_KEY environment variable not set. ENTSO-E price fetching will fail.")

# fallback if DB lookup fails
DEFAULT_EIC_CODE = "10YEU-CONT-SYNC"

_API_DATE_FORMAT = "%Y%m%d%H%M"  # Format for periodStart/periodEnd in ENTSO-E raw API


async def fetch_external_electricity_prices(price_region_id: int, start: datetime, end: datetime) -> List[Dict[str, Any]]:
    """
    Fetches day-ahead electricity prices for a given region and date range using ENTSO-E.
    Uses B2 for caching raw API XML responses and supports pagination via offset.
    Automatically splits large date ranges (>1year) into smaller chunks to comply with ENTSO-E API limits.
    """
    print(f"Fetching ENTSO-E day-ahead prices for price_region_id {price_region_id} from {start} to {end}")

    if not ENTSOE_API_KEY:
        print("Error: ENTSOE_API_KEY is not set. Cannot fetch prices from ENTSO-E.")
        return []

    # --- lookup bidding_zone_eic_code in price_regions table ---
    country_code: Optional[str] = None
    # Use the global app_db instance
    if app_db.is_connected:  # Check if the global instance is connected
        try:
            query = "SELECT bidding_zone_eic_code FROM price_regions WHERE price_region_id = :price_region_id"
            # The `databases` library uses :param_name style for placeholders
            row = await app_db.fetch_one(query=query, values={"price_region_id": price_region_id})
            if row:
                country_code = row["bidding_zone_eic_code"]
            else:
                print(f"Warning: no DB entry in price_regions for id {price_region_id}")
        except Exception as e:
            print(f"Error querying price_regions for id {price_region_id} using app_db: {e}")
    else:
        print("Warning: app_db (api.db.database) is not connected. Cannot look up EIC code.")

    if not country_code:
        print(f"Using DEFAULT_EIC_CODE fallback for price_region_id {price_region_id}")
        country_code = DEFAULT_EIC_CODE

    # Ensure start and end are timezone-aware (UTC)
    start_utc = start.astimezone(timezone.utc) if start.tzinfo else start.replace(tzinfo=timezone.utc)
    end_utc = end.astimezone(timezone.utc) if end.tzinfo else end.replace(tzinfo=timezone.utc)

    # Check if date range exceeds 1 year and split into chunks if needed
    date_chunks = _split_date_range_by_year(start_utc, end_utc)
    print(f"Split date range into {len(date_chunks)} chunks to comply with ENTSO-E API 1-year limit")
    
    all_records: List[Dict[str, Any]] = []
    
    # Process each date chunk separately
    for chunk_start, chunk_end in date_chunks:
        print(f"Processing chunk: {chunk_start} to {chunk_end}")
        chunk_records = await _fetch_prices_for_date_range(
            price_region_id, chunk_start, chunk_end, country_code
        )
        all_records.extend(chunk_records)
    
    # Deduplicate records across all chunks as safety measure
    seen_keys = set()
    deduplicated_records: List[Dict[str, Any]] = []
    duplicates_removed = 0
    
    for record in all_records:
        time_obj: datetime = record["time"]
        # Normalize the time component of the key to ensure robust deduplication
        # Uses (year, month, day, hour, minute, second) tuple from the UTC datetime
        normalized_time_key_tuple = (
            time_obj.year, 
            time_obj.month, 
            time_obj.day,
            time_obj.hour, 
            time_obj.minute, 
            time_obj.second
        )
        key = (record["price_region_id"], normalized_time_key_tuple)
        
        if key not in seen_keys:
            seen_keys.add(key)
            deduplicated_records.append(record)
        else:
            duplicates_removed += 1
    
    if duplicates_removed > 0:
        print(f"Removed {duplicates_removed} duplicate records across all chunks for price_region_id {price_region_id}")
    
    print(f"Processed {len(deduplicated_records)} unique price records for price_region_id {price_region_id}.")
    return deduplicated_records


def _split_date_range_by_year(start: datetime, end: datetime) -> List[tuple[datetime, datetime]]:
    """
    Splits a date range into chunks of maximum 1 year each to comply with ENTSO-E API limits.
    Returns list of (start, end) datetime tuples.
    """
    chunks = []
    current_start = start
    
    while current_start < end:
        # Calculate end of current chunk (1 year from start, but not exceeding original end)
        next_year = current_start.replace(year=current_start.year + 1)
        current_end = min(next_year, end)
        
        chunks.append((current_start, current_end))
        current_start = current_end
    
    return chunks


async def _fetch_prices_for_date_range(
    price_region_id: int, 
    start: datetime, 
    end: datetime, 
    country_code: str
) -> List[Dict[str, Any]]:
    """
    Fetches prices for a single date range (≤1 year) from ENTSO-E API.
    """
    # Convert to Brussels timezone for API consistency
    try:
        start_ts_brussels = pd.Timestamp(start).tz_convert('Europe/Brussels')
        end_ts_brussels = pd.Timestamp(end).tz_convert('Europe/Brussels')
    except Exception as e:
        print(f"Error converting datetimes to Pandas Timestamps with Brussels timezone: {e}")
        return []    # paginate through raw ENTSO-E XML (100 TimeSeries per page) using offset
    API_URL = "https://web-api.tp.entsoe.eu/api"
    offset = 0
    raw_records: List[Dict[str, Any]] = []
    while True:
        params = {
            "documentType": "A44",
            "periodStart": start_ts_brussels.strftime(_API_DATE_FORMAT),
            "periodEnd": end_ts_brussels.strftime(_API_DATE_FORMAT),
            "out_Domain": country_code,
            "in_Domain": country_code,
            "contract_MarketAgreement.type": "A01",
            "offset": str(offset)
        }
        raw = await _make_entsoe_request(API_URL, params)
        # if API/backup returns nothing, end loop
        if not raw:
            print("Warning: empty response from ENTSO-E API or cache")
            break
        try:
            root = ET.fromstring(raw)
        except Exception as e:
            print(f"Error parsing ENTSO-E XML: {e}")
            break
        # support namespaced XML: match any namespace for TimeSeries elements
        series = root.findall(".//{*}TimeSeries")
        if not series:
            print(f"Warning: no TimeSeries elements (with namespace) in ENTSO-E response (first 200 bytes): {raw[:200]!r}")
            break
        page_records: List[Dict[str, Any]] = []
        for ts in series:
            # use wildcard namespace on nested elements
            period = ts.find("{*}Period")
            if period is None:
                continue
            interval = period.find("{*}timeInterval")
            if interval is None:
                continue
            start_iso_element = interval.find("{*}start")
            if start_iso_element is None or start_iso_element.text is None:
                continue
            start_iso = start_iso_element.text

            resolution_element = period.find("{*}resolution")
            if resolution_element is None or resolution_element.text is None:
                continue
            resolution = resolution_element.text

            # Filter for hourly resolution only
            if resolution not in ("PT60M", "PT1H"):
                continue  # Skip this TimeSeries if it's not hourly

            try:
                base_dt = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
            except ValueError:
                continue

            
        
            
            if resolution.startswith("PT") and resolution.endswith("M"):
                step = timedelta(minutes=int(resolution[2:-1]))
            elif resolution.startswith("PT") and resolution.endswith("H"):
                step = timedelta(hours=int(resolution[2:-1]))
            else:
                step = timedelta()
            for pt in period.findall("{*}Point"):
                pos_element = pt.find("{*}position")
                price_element = pt.find("{*}price.amount")
                
                if pos_element is None or pos_element.text is None:
                    continue
                if price_element is None or price_element.text is None:
                    continue
                
                try:
                    pos = int(pos_element.text)
                    val = float(price_element.text)
                except (ValueError, TypeError):
                    continue
                ts_point = (base_dt + (pos - 1) * step).astimezone(timezone.utc)
                page_records.append({"time": ts_point, "price_eur_mwh": val})
        if not page_records:
            break
        raw_records.extend(page_records)
        if len(series) < 100:
            break
        offset += 100

    # Apply forward fill to handle missing data points due to ENTSO-E API behavior
    # (API omits data points when price is same as previous hour)
    filled_records = _apply_forward_fill(raw_records, start, end)
    
    # process records into Pydantic models
    processed_records: List[Dict[str, Any]] = []
    for rec in filled_records:
        data = {"price_region_id": price_region_id, "time": rec["time"], "price_eur_mwh": rec["price_eur_mwh"]}
        try:
            # exclude unset optional fields (e.g. calculated_price_eur_mwh) from insert payload
            processed_records.append(PriceIn(**data).model_dump(exclude_none=True))
        except ValidationError as e:
            print(f"Validation error for record {data}: {e}")
    
    # Deduplicate records as safety measure (should be minimal after hourly filtering)
    # Keep the first occurrence of each unique combination
    seen_keys = set()
    deduplicated_records: List[Dict[str, Any]] = []
    duplicates_removed = 0
    
    for record in processed_records:
        time_obj: datetime = record["time"]
        # Normalize the time component of the key to ensure robust deduplication
        # Uses (year, month, day, hour, minute, second) tuple from the UTC datetime
        normalized_time_key_tuple = (
            time_obj.year, 
            time_obj.month, 
            time_obj.day,
            time_obj.hour, 
            time_obj.minute, 
            time_obj.second
        )
        key = (record["price_region_id"], normalized_time_key_tuple)
        
        if key not in seen_keys:
            seen_keys.add(key)
            deduplicated_records.append(record)
        else:
            duplicates_removed += 1
    
    if duplicates_removed > 0:
        print(f"Removed {duplicates_removed} duplicate records for price_region_id {price_region_id}")
    
    print(f"Processed {len(deduplicated_records)} unique price records for price_region_id {price_region_id}.")
    return deduplicated_records

def _apply_forward_fill(
    raw_records: List[Dict[str, Any]], 
    start_dt: datetime, 
    end_dt: datetime
) -> List[Dict[str, Any]]:
    """
    Apply forward fill to handle missing data points in ENTSO-E API responses.
    The API sometimes omits data points when the price is the same as the previous hour.
    
    Args:
        raw_records: List of records with 'time' and 'price_eur_mwh' keys
        start_dt: Start datetime for the expected time range
        end_dt: End datetime for the expected time range
        
    Returns:
        List of records with gaps filled using forward fill
    """
    if not raw_records:
        return raw_records
    
    # Sort records by time to ensure proper ordering
    sorted_records = sorted(raw_records, key=lambda x: x["time"])
    
    # Convert to UTC and ensure timezone awareness
    start_utc = start_dt.astimezone(timezone.utc) if start_dt.tzinfo else start_dt.replace(tzinfo=timezone.utc)
    end_utc = end_dt.astimezone(timezone.utc) if end_dt.tzinfo else end_dt.replace(tzinfo=timezone.utc)
    
    # Create a complete hourly time series from start to end
    expected_times = []
    current_time = start_utc.replace(minute=0, second=0, microsecond=0)  # Round down to hour
    
    while current_time < end_utc:
        expected_times.append(current_time)
        current_time += timedelta(hours=1)
    
    # Create a mapping of existing data points
    existing_data = {rec["time"].replace(minute=0, second=0, microsecond=0): rec["price_eur_mwh"] 
                    for rec in sorted_records}
    
    # Fill gaps using forward fill
    filled_records = []
    last_price = None
    gaps_filled = 0
    
    for expected_time in expected_times:
        if expected_time in existing_data:
            # Data point exists, use it
            price = existing_data[expected_time]
            last_price = price
        elif last_price is not None:
            # Data point missing, use forward fill
            price = last_price
            gaps_filled += 1
        else:
            # No previous price available, skip this point
            continue
            
        filled_records.append({
            "time": expected_time,
            "price_eur_mwh": price
        })
    
    if gaps_filled > 0:
        print(f"Forward filled {gaps_filled} missing data points due to ENTSO-E API gaps")
    
    return filled_records

async def _make_entsoe_request(
        base_url: str,
        params: Dict[str, str],
        timeout: float = 30.0
) -> Optional[bytes]:
    """
    Makes a GET request to the ENTSO-E API, checking B2 backup first.
    Returns raw response bytes or None on error.
    """
    # prepare cache key
    params_for_backup = params.copy()
    backup_key = base_url
    backup_filename = await b2_handler.check_backup(backup_key, params_for_backup)
    if backup_filename:
        # retrieve raw bytes instead of JSON
        data_bytes = await b2_handler.get_backup_bytes(backup_filename)
        if data_bytes:
            print(f"Using cached raw ENTSO-E response: {backup_filename}")
            return data_bytes
        else:
            print(f"Failed to load raw backup {backup_filename}, fetching live...")    # live call
    request_params = params.copy()
    if ENTSOE_API_KEY:
        request_params["securityToken"] = ENTSOE_API_KEY
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(base_url, params=request_params, timeout=timeout)
            resp.raise_for_status()
            raw = resp.content
            # save cache without key param
            await b2_handler.save_backup(backup_key, params_for_backup, raw)
            return raw
    except Exception as exc:
        print(f"Error fetching ENTSO-E API: {exc}")
        return None

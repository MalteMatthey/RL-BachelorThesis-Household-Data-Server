import os
import asyncpg
import httpx
import pandas as pd
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
import json
import requests

from entsoe import EntsoePandasClient
from entsoe.exceptions import NoMatchingDataError, InvalidPSRTypeError

from ..schemas import PriceIn
from .b2_backup import b2_handler

# --- Configuration ---
ENTSOE_API_KEY = os.getenv("ENTSOE_API_KEY")
if not ENTSOE_API_KEY:
    print("Warning: ENTSOE_API_KEY environment variable not set. ENTSO-E price fetching will fail.")

# fallback if DB lookup fails
DEFAULT_EIC_CODE = "10YEU-CONT-SYNC"

# Database URL for asyncpg
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("Warning: DATABASE_URL env var not set; EIC lookup from DB will fail.")

_API_DATE_FORMAT = "%Y%m%d%H%M"  # Format for periodStart/periodEnd in ENTSO-E raw API
_B2_CONCEPTUAL_URL_PRICES = "entsoe_day_ahead_prices"  # For B2 filename generation


async def fetch_external_electricity_prices(price_region_id: int, start: datetime, end: datetime) -> List[Dict[str, Any]]:
    """
    Fetches day-ahead electricity prices for a given region and date range using ENTSO-E.
    Uses B2 for caching.
    """
    print(f"Fetching ENTSO-E day-ahead prices for price_region_id {price_region_id} from {start} to {end}")

    if not ENTSOE_API_KEY:
        print("Error: ENTSOE_API_KEY is not set. Cannot fetch prices from ENTSO-E.")
        return []

    # --- lookup bidding_zone_eic_code in price_regions table ---
    country_code: Optional[str] = None
    if DATABASE_URL:
        try:
            conn = await asyncpg.connect(DATABASE_URL)
            row = await conn.fetchrow(
                "SELECT bidding_zone_eic_code FROM price_regions WHERE price_region_id = $1",
                price_region_id
            )
            await conn.close()
            if row:
                country_code = row["bidding_zone_eic_code"]
            else:
                print(f"Warning: no DB entry in price_regions for id {price_region_id}")
        except Exception as e:
            print(f"Error querying price_regions for id {price_region_id}: {e}")

    if not country_code:
        print(f"Using DEFAULT_EIC_CODE fallback for price_region_id {price_region_id}")
        country_code = DEFAULT_EIC_CODE

    # Ensure start and end are timezone-aware (UTC for internal consistency, convert to Brussels for API)
    start_utc = start.astimezone(timezone.utc) if start.tzinfo else start.replace(tzinfo=timezone.utc)
    end_utc = end.astimezone(timezone.utc) if end.tzinfo else end.replace(tzinfo=timezone.utc)

    # entsoe-py expects pandas Timestamps with a timezone for start/end
    # 'Europe/Brussels' is commonly used for ENTSO-E API queries
    try:
        start_ts_brussels = pd.Timestamp(start_utc).tz_convert('Europe/Brussels')
        end_ts_brussels = pd.Timestamp(end_utc).tz_convert('Europe/Brussels')
    except Exception as e:
        print(f"Error converting datetimes to Pandas Timestamps with Brussels timezone: {e}")
        return []

    # --- B2 Backup Check ---
    # Parameters for B2 filename should be stable and reflect the query
    b2_params = {
        "country_code": country_code,
        "start_datetime": start_ts_brussels.strftime(_API_DATE_FORMAT),
        "end_datetime": end_ts_brussels.strftime(_API_DATE_FORMAT)
    }
    backup_filename = await b2_handler.check_backup(_B2_CONCEPTUAL_URL_PRICES, b2_params)

    price_data_series: Optional[pd.Series] = None

    if backup_filename:
        print(f"Backup found for ENTSO-E prices: {backup_filename}")
        cached_data_json_str = await b2_handler.get_backup(backup_filename)
        if cached_data_json_str:
            try:
                if isinstance(cached_data_json_str, list):
                    print(f"Successfully loaded {len(cached_data_json_str)} records from B2 cache.")
                    return cached_data_json_str
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON from B2 backup {backup_filename}: {e}. Fetching live data.")
            except Exception as e:
                print(f"Error processing B2 backup {backup_filename}: {e}. Fetching live data.")

    # --- Live API Call ---
    if price_data_series is None:
        print(f"Making live API request to ENTSO-E for {country_code} from {start_ts_brussels} to {end_ts_brussels}")
        try:
            client = EntsoePandasClient(api_key=ENTSOE_API_KEY)
            price_data_series = await client.query_day_ahead_prices(
                country_code=country_code,
                start=start_ts_brussels,
                end=end_ts_brussels
            )
            print(f"Successfully fetched {len(price_data_series) if price_data_series is not None else 0} price points from ENTSO-E.")

            # --- Save to B2 ---
            if price_data_series is not None and not price_data_series.empty:
                processed_records_for_b2 = []
                for ts, price in price_data_series.items():
                    record_time_utc = pd.Timestamp(ts).tz_convert('UTC').to_pydatetime()
                    processed_records_for_b2.append({
                        "time": record_time_utc.isoformat(),
                        "price_region_id": price_region_id,
                        "price_eur_mwh": float(price) if pd.notna(price) else None
                    })

                content_bytes = json.dumps(processed_records_for_b2).encode('utf-8')
                await b2_handler.save_backup(_B2_CONCEPTUAL_URL_PRICES, b2_params, content_bytes)
            elif price_data_series is not None and price_data_series.empty:
                print("ENTSO-E returned an empty series, nothing to save to B2.")
            else:
                print("No data received from ENTSO-E, nothing to save to B2.")

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                print(f"Authentication failed: Invalid ENTSOE_API_KEY ('{ENTSOE_API_KEY}' is not a valid API key)")
            else:
                print(f"HTTP error from ENTSO-E API: {e.response.status_code} - {e.response.text}")
            price_data_series = pd.Series(dtype=float)
        except NoMatchingDataError:
            print(f"No matching data found on ENTSO-E for {country_code} in the period.")
            price_data_series = pd.Series(dtype=float)
        except InvalidPSRTypeError:
            print(f"Invalid PSRType for ENTSO-E query (though not directly used here).")
            price_data_series = pd.Series(dtype=float)
        except httpx.HTTPStatusError as e:
            print(f"HTTP error from ENTSO-E API: {e.response.status_code} - {e.response.text}")
            price_data_series = pd.Series(dtype=float)
        except httpx.RequestError as e:
            print(f"Network request error connecting to ENTSO-E: {e}")
            price_data_series = pd.Series(dtype=float)
        except ValueError as e:
            print(f"Invalid country code '{country_code}' for ENTSO-E API: {e}")
            price_data_series = pd.Series(dtype=float)
        except Exception as e:
            print(f"An unexpected error occurred during ENTSO-E data fetch: {e}")
            import traceback
            traceback.print_exc()
            price_data_series = pd.Series(dtype=float)

    # --- Process Data ---
    processed_records: List[Dict[str, Any]] = []
    if price_data_series is not None and not price_data_series.empty:
        for ts, price in price_data_series.items():
            if pd.notna(price):
                record_time_utc = pd.Timestamp(ts).tz_convert('UTC').to_pydatetime()
                processed_records.append({
                    "time": record_time_utc,
                    "price_region_id": price_region_id,
                    "price_eur_mwh": float(price)
                })
        print(f"Processed {len(processed_records)} price records for price_region_id {price_region_id}.")
    elif price_data_series is not None and price_data_series.empty:
        print(f"No price data to process for price_region_id {price_region_id} (empty series).")
    else:
        print(f"No price data series available to process for price_region_id {price_region_id}.")

    return processed_records

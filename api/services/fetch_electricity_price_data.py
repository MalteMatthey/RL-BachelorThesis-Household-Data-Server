import os
import httpx
import pandas as pd
import xml.etree.ElementTree as ET
from pydantic import ValidationError
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

from ..schemas import PriceIn
from .b2_backup import b2_handler
# Import the global database instance from api.db
from api.db import database as app_db

# --- Configuration ---
ENTSOE_API_KEY = os.getenv("ENTSOE_API_KEY")
if not ENTSOE_API_KEY:
    print("Warning: ENTSOE_API_KEY environment variable not set. ENTSO-E price fetching will fail.")

# fallback if DB lookup fails
DEFAULT_EIC_CODE = "10YEU-CONT-SYNC"

_API_DATE_FORMAT = "%Y%m%d%H%M"  # Format for periodStart/periodEnd in ENTSO-E raw API
_B2_CONCEPTUAL_URL_PRICES = "entsoe_day_ahead_prices"  # For B2 filename generation


async def fetch_external_electricity_prices(price_region_id: int, start: datetime, end: datetime) -> List[Dict[str, Any]]:
    """
    Fetches day-ahead electricity prices for a given region and date range using ENTSO-E.
    Uses B2 for caching raw API XML responses and supports pagination via offset.
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

    # Ensure start and end are timezone-aware (UTC) and convert to Brussels for API consistency
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

    # paginate through raw ENTSO-E XML (100 TimeSeries per page) using offset
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
            "classificationSequence_AttributeInstanceComponent.position": "1",
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
            interval = period.find("{*}timeInterval")
            start_iso = interval.find("{*}start").text
            resolution = period.find("{*}resolution").text
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
                pos = int(pt.find("{*}position").text)
                price = pt.find("{*}price.amount").text
                try:
                    val = float(price)
                except ValueError:
                    continue
                ts_point = (base_dt + (pos - 1) * step).astimezone(timezone.utc)
                page_records.append({"time": ts_point, "price_eur_mwh": val})
        if not page_records:
            break
        raw_records.extend(page_records)
        if len(series) < 100:
            break
        offset += 100

    # process records into Pydantic models
    processed_records: List[Dict[str, Any]] = []
    for rec in raw_records:
        data = {"price_region_id": price_region_id, "time": rec["time"], "price_eur_mwh": rec["price_eur_mwh"]}
        try:
            # exclude unset optional fields (e.g. calculated_price_eur_mwh) from insert payload
            processed_records.append(PriceIn(**data).model_dump(exclude_none=True))
        except ValidationError as e:
            print(f"Validation error for record {data}: {e}")
    print(f"Processed {len(processed_records)} price records for price_region_id {price_region_id}.")
    return processed_records

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
            print(f"Failed to load raw backup {backup_filename}, fetching live...")
    # live call
    request_params = params.copy()
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

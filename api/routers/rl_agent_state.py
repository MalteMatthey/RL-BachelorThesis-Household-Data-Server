from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

import api.db as db
from api.db import database # This is our databases.Database instance

# Define the response model for the RL Agent State
class RLAgentStateData(BaseModel):
    timestamp: datetime

    # Price related fields
    price_region_id: Optional[int] = None
    raw_price_eur_mwh: Optional[float] = None
    calculated_price_eur_mwh: Optional[float] = None

    # PV related fields
    pv_generation_kwh: Optional[float] = None

    # Load related fields
    load_consumption_kwh: Optional[float] = None

    # Weather Observation fields
    obs_temp: Optional[float] = None
    obs_tempmin: Optional[float] = None
    obs_tempmax: Optional[float] = None
    obs_feelslike: Optional[float] = None
    obs_feelslikemax: Optional[float] = None
    obs_feelslikemin: Optional[float] = None
    obs_humidity: Optional[float] = None
    obs_dew: Optional[float] = None
    obs_precip: Optional[float] = None
    obs_precipprob: Optional[float] = None
    obs_precipcover: Optional[float] = None
    obs_preciptype: Optional[List[str]] = None
    obs_snow: Optional[float] = None
    obs_snowdepth: Optional[float] = None
    obs_windgust: Optional[float] = None
    obs_windspeed: Optional[float] = None
    obs_winddir: Optional[float] = None
    obs_pressure: Optional[float] = None
    obs_cloudcover: Optional[float] = None
    obs_visibility: Optional[float] = None
    obs_solarradiation: Optional[float] = None
    obs_solarenergy: Optional[float] = None
    obs_uvindex: Optional[float] = None
    obs_severerisk: Optional[float] = None
    obs_windspeedmax: Optional[float] = None
    obs_windspeedmean: Optional[float] = None
    obs_windspeedmin: Optional[float] = None
    obs_sunrise: Optional[str] = None
    obs_sunset: Optional[str] = None
    obs_moonphase: Optional[float] = None
    obs_conditions: Optional[str] = None
    obs_windspeed50: Optional[float] = None
    obs_winddir50: Optional[float] = None
    obs_windspeed80: Optional[float] = None
    obs_winddir80: Optional[float] = None
    obs_windspeed100: Optional[float] = None
    obs_winddir100: Optional[float] = None
    obs_ghiradiation: Optional[float] = None
    obs_dniradiation: Optional[float] = None
    obs_difradiation: Optional[float] = None
    obs_sunelevation: Optional[float] = None

    # Weather Forecast fields
    fc_run_time: Optional[datetime] = None
    fc_target_time: Optional[datetime] = None
    fc_temp: Optional[float] = None
    fc_tempmin: Optional[float] = None
    fc_tempmax: Optional[float] = None
    fc_feelslike: Optional[float] = None
    fc_feelslikemax: Optional[float] = None
    fc_feelslikemin: Optional[float] = None
    fc_dew: Optional[float] = None
    fc_humidity: Optional[float] = None
    fc_precip: Optional[float] = None
    fc_precipprob: Optional[float] = None
    fc_precipcover: Optional[float] = None
    fc_preciptype: Optional[List[str]] = None
    fc_snow: Optional[float] = None
    fc_snowdepth: Optional[float] = None
    fc_windgust: Optional[float] = None
    fc_windspeed: Optional[float] = None
    fc_winddir: Optional[float] = None
    fc_pressure: Optional[float] = None
    fc_cloudcover: Optional[float] = None
    fc_visibility: Optional[float] = None
    fc_solarradiation: Optional[float] = None
    fc_solarenergy: Optional[float] = None
    fc_uvindex: Optional[float] = None
    fc_severerisk: Optional[float] = None
    fc_windspeedmax: Optional[float] = None
    fc_windspeedmean: Optional[float] = None
    fc_windspeedmin: Optional[float] = None
    fc_sunrise: Optional[str] = None
    fc_sunset: Optional[str] = None
    fc_moonphase: Optional[float] = None
    fc_conditions: Optional[str] = None
    fc_windspeed50: Optional[float] = None
    fc_winddir50: Optional[float] = None
    fc_windspeed80: Optional[float] = None
    fc_winddir80: Optional[float] = None
    fc_windspeed100: Optional[float] = None
    fc_winddir100: Optional[float] = None
    fc_ghiradiation: Optional[float] = None
    fc_dniradiation: Optional[float] = None
    fc_difradiation: Optional[float] = None
    fc_sunelevation: Optional[float] = None


router = APIRouter(prefix="/rl_agent_state",tags=["rl_agent_state"])

# Replace complex function with a minimal example returning one variable per table
@router.get("/", response_model=List[RLAgentStateData], response_model_exclude_none=True)
async def get_rl_agent_state(
    household_id: int = Query(...),
    start_time: datetime = Query(...),
    end_time: Optional[datetime] = Query(None)
):
    if end_time is None:
        end_time = start_time
    if end_time < start_time:
        raise HTTPException(status_code=400, detail="end_time cannot be before start_time.")

    # Validate household and get related IDs
    household = await database.fetch_one(
        db.households_tbl.select().where(db.households_tbl.c.household_id == household_id)
    )
    if not household:
        raise HTTPException(status_code=404, detail="Household not found.")
    location_id = household.location_id
    price_region_id = (await database.fetch_one(
        db.locations_tbl.select().where(db.locations_tbl.c.location_id == location_id)
    ))["price_region_id"]

    # Prepare literal strings for start and end times
    start_str = start_time.isoformat()
    end_str = end_time.isoformat()
    # Build minute-level series with LOCF per table using literal values
    sql = f"""
    WITH minute_series AS (
      SELECT generate_series('{start_str}'::timestamptz, '{end_str}'::timestamptz, '1 minute') AS ts
    ),
    price_data AS (
      SELECT time_bucket_gapfill('1 minute', time, '{start_str}'::timestamptz, '{end_str}'::timestamptz) AS ts,
             locf(LAST(price_eur_mwh, time)) AS price_eur_mwh
      FROM {db.price_tbl.name}
      WHERE price_region_id = {price_region_id}
      GROUP BY ts
    ),
    pv_data AS (
      SELECT time_bucket_gapfill('1 minute', time, '{start_str}'::timestamptz, '{end_str}'::timestamptz) AS ts,
             locf(LAST(generation_kwh, time)) AS generation_kwh
      FROM {db.pv_tbl.name}
      WHERE household_id = {household_id}
      GROUP BY ts
    ),
    load_data AS (
      SELECT time_bucket_gapfill('1 minute', time, '{start_str}'::timestamptz, '{end_str}'::timestamptz) AS ts,
             locf(LAST(consumption_kwh, time)) AS consumption_kwh
      FROM {db.load_tbl.name}
      WHERE household_id = {household_id}
      GROUP BY ts
    ),
    obs_data AS (
      SELECT time_bucket_gapfill('1 minute', datetime, '{start_str}'::timestamptz, '{end_str}'::timestamptz) AS ts,
             locf(LAST(temp, datetime)) AS obs_temp
      FROM {db.weather_obs_tbl.name}
      WHERE location_id = {location_id}
      GROUP BY ts
    ),
    fc_data AS (
      SELECT time_bucket_gapfill('1 minute', forecast_run, '{start_str}'::timestamptz, '{end_str}'::timestamptz) AS ts,
             locf(LAST(temp, forecast_run)) AS fc_temp
      FROM {db.weather_fc_tbl.name}
      WHERE location_id = {location_id}
      GROUP BY ts
    )
    SELECT
      ms.ts AS timestamp,
      price.price_eur_mwh,
      pv.generation_kwh,
      load.consumption_kwh,
      obs.obs_temp,
      fc.fc_temp
    FROM minute_series ms
    LEFT JOIN price_data price ON ms.ts = price.ts
    LEFT JOIN pv_data pv ON ms.ts = pv.ts
    LEFT JOIN load_data load ON ms.ts = load.ts
    LEFT JOIN obs_data obs ON ms.ts = obs.ts
    LEFT JOIN fc_data fc ON ms.ts = fc.ts
    ORDER BY ms.ts
    """
    raw_rows = await database.fetch_all(sql)
    rows = [dict(r) for r in raw_rows]

    return [RLAgentStateData(
         timestamp             = r["timestamp"],
         raw_price_eur_mwh     = r.get("price_eur_mwh"),
         pv_generation_kwh     = r.get("generation_kwh"),
         load_consumption_kwh  = r.get("consumption_kwh"),
         obs_temp              = r.get("obs_temp"),
         fc_temp               = r.get("fc_temp")
    ) for r in rows]
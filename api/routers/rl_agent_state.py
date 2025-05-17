from datetime import datetime
from typing import List, Optional
import json

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

import api.db as db
from api.db import database
from api.helpers.dynamic_query_builder import build_rl_agent_state_query, REQUESTABLE_DB_FIELDS, FORECAST_ENTRY_FIELDS

# Insert nested forecast model
class ForecastEntry(BaseModel):
    forecast_run: datetime
    target_time: datetime
    temp: Optional[float] = None
    tempmin: Optional[float] = None
    tempmax: Optional[float] = None
    feelslikemax: Optional[float] = None
    feelslikemin: Optional[float] = None
    feelslike: Optional[float] = None
    dew: Optional[float] = None
    humidity: Optional[float] = None
    precip: Optional[float] = None
    precipprob: Optional[float] = None
    precipcover: Optional[float] = None
    snow: Optional[float] = None
    snowdepth: Optional[float] = None
    windgust: Optional[float] = None
    windspeed: Optional[float] = None
    winddir: Optional[float] = None
    pressure: Optional[float] = None
    cloudcover: Optional[float] = None
    visibility: Optional[float] = None
    solarradiation: Optional[float] = None
    solarenergy: Optional[float] = None
    uvindex: Optional[float] = None
    severerisk: Optional[float] = None
    windspeedmax: Optional[float] = None
    windspeedmean: Optional[float] = None
    windspeedmin: Optional[float] = None
    sunrise: Optional[str] = None
    sunset: Optional[str] = None
    moonphase: Optional[float] = None
    conditions: Optional[str] = None
    windspeed50: Optional[float] = None
    winddir50: Optional[float] = None
    windspeed80: Optional[float] = None
    winddir80: Optional[float] = None
    windspeed100: Optional[float] = None
    winddir100: Optional[float] = None
    ghiradiation: Optional[float] = None
    dniradiation: Optional[float] = None
    difradiation: Optional[float] = None
    sunelevation: Optional[float] = None


# Define the response model for the RL Agent State
class RLAgentStateData(BaseModel):
    timestamp: datetime
    forecasts: List[ForecastEntry]  # hourly forecast next 7 days per minute

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


router = APIRouter(prefix="/rl_agent_state", tags=["rl_agent_state"])

@router.get("/", response_model=List[RLAgentStateData], response_model_exclude_none=True)
async def get_rl_agent_state(
    household_id: int = Query(...),
    start_time: datetime = Query(...),
    end_time: Optional[datetime] = Query(None),
    fields: Optional[List[str]] = Query(None, description=f"Available fields: {', '.join(REQUESTABLE_DB_FIELDS)}"),
    forecast_fields: Optional[List[str]] = Query(None, description=f"Available forecast fields: {', '.join(FORECAST_ENTRY_FIELDS)}")
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

    # Build the query dynamically
    sql = build_rl_agent_state_query(
        requested_fields_input=fields,
        forecast_fields_input=forecast_fields,
        household_id=household_id,
        location_id=location_id,
        price_region_id=price_region_id,
        start_str=start_time.isoformat(),
        end_str=(end_time or start_time).isoformat()
    )
    raw_rows = await database.fetch_all(sql)

    results = []
    for r in (dict(r) for r in raw_rows):
        # parse forecasts
        try:
            raw_f = r.get("forecasts") or []
            if isinstance(raw_f, str):
                raw_f = json.loads(raw_f)
            if not isinstance(raw_f, list):
                raw_f = []
            forecast_list = [ForecastEntry(**e) for e in raw_f]
        except Exception:
            forecast_list = []

        # base kwargs
        data_kwargs = {
            "timestamp": r["timestamp"],
            "forecasts": forecast_list,
            "price_region_id": r.get("price_region_id"),
            "raw_price_eur_mwh": r.get("price_eur_mwh"),
            "pv_generation_kwh": r.get("generation_kwh"),
            "load_consumption_kwh": r.get("consumption_kwh"),
        }
        # copy any obs_* keys
        for k, v in r.items():
            if k.startswith("obs_"):
                data_kwargs[k] = v

        results.append(RLAgentStateData(**data_kwargs))
    return results
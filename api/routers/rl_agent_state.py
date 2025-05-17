from datetime import datetime
from typing import List, Optional, Set
import json

from fastapi import APIRouter, Query, HTTPException
from api.schemas import ForecastEntry, RLAgentStateData
from api.db import database
from api.helpers.dynamic_query_builder import build_rl_agent_state_query, REQUESTABLE_DB_FIELDS, FORECAST_ENTRY_FIELDS
from api.helpers.formula_calculator import calculate_price_with_formula
import api.db as db


router = APIRouter(prefix="/rl_agent_state", tags=["rl_agent_state"])

@router.get("/", response_model=List[RLAgentStateData], response_model_exclude_none=True)
async def get_rl_agent_state(
    household_id: int = Query(...),
    start_time: datetime = Query(...),
    end_time: Optional[datetime] = Query(None),
    resolution_minutes: int = Query(1, ge=1, le=1440, description="Resolution of the data in minutes, from 1 to 1440. Default is 1 minute."),
    fields: Optional[List[str]] = Query(None, description=f"Available fields: {', '.join(REQUESTABLE_DB_FIELDS)}"),
    forecast_fields: Optional[List[str]] = Query(None, description=f"Available forecast fields: {', '.join(FORECAST_ENTRY_FIELDS)}"),
    forecast_hours: Optional[int] = Query(None, ge=1, le=192, description="Number of hours for weather forecast data, from 1 to 192.")
):
    if end_time is None:
        end_time = start_time
    if end_time < start_time:
        raise HTTPException(status_code=400, detail="end_time cannot be before start_time.")

    # Determine effective fields for the SQL query.
    # Start with a copy of the user's requested fields (if any).
    effective_sql_fields: Set[str] = set(fields) if fields else set()

    # If 'calculated_price_eur_mwh' is requested in the API call, enforce inclusion of necessary raw price for calculation.
    if fields and "calculated_price_eur_mwh" in fields:
        effective_sql_fields.add("raw_price_eur_mwh")

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
        requested_fields_input=list(effective_sql_fields) if effective_sql_fields else None,
        forecast_fields_input=forecast_fields,
        household_id=household_id,
        location_id=location_id,
        price_region_id=price_region_id,
        start_str=start_time.isoformat(),
        end_str=(end_time or start_time).isoformat(),
        forecast_hours=forecast_hours,
        resolution_minutes=resolution_minutes
    )
    raw_rows = await database.fetch_all(sql)

    results = []
    for r_mapping in raw_rows:
        r = dict(r_mapping)
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

        # Initialize data_kwargs with guaranteed fields
        data_kwargs = {
            "timestamp": r["timestamp"], # 'timestamp' is always expected
        }

        if (fields is None) or ("forecasts" in fields):
            data_kwargs["forecasts"] = forecast_list
        if "generation_kwh" in r: # Corresponds to "pv_generation_kwh" in fields
            data_kwargs["pv_generation_kwh"] = r.get("generation_kwh")
        if "consumption_kwh" in r: # Corresponds to "load_consumption_kwh" in fields
            data_kwargs["load_consumption_kwh"] = r.get("consumption_kwh")
        if (fields is None) or "raw_price_eur_mwh" in fields:
            data_kwargs["raw_price_eur_mwh"] = r.get("price_eur_mwh")
        
        if (fields is None) or "calculated_price_eur_mwh" in fields:
            # The raw price for calculation is fetched as "price_eur_mwh" from SQL.
            raw_price_for_calc = r.get("price_eur_mwh") 
            if household.enduser_price_formula and raw_price_for_calc is not None:
                calculated_price = calculate_price_with_formula(
                    household.enduser_price_formula,
                    raw_price_for_calc
                )
                data_kwargs["calculated_price_eur_mwh"] = round(calculated_price, 2)
            else:
                data_kwargs["calculated_price_eur_mwh"] = None 
        
        # copy any obs_* keys that were fetched
        for k_obs, v_obs in r.items():
            if k_obs.startswith("obs_"):
                data_kwargs[k_obs] = v_obs

        results.append(RLAgentStateData(**data_kwargs))
    return results
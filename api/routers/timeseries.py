from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, Query, HTTPException
from sqlalchemy import Table, Column, select

import api.db as db
from api.db import database
from api.schemas import PriceIn, PVIn, LoadIn, WeatherObservationIn, WeatherForecastIn
from api.helpers.formula_calculator import calculate_price_with_formula

router = APIRouter(prefix="/timeseries", tags=["timeseries"])


async def fetch_timeseries(table: Table, time_column: Column, filters: Dict[str, Any], start: datetime, end: datetime):
    filter_conditions = [table.c[key] == value for key, value in filters.items()]
    date_conditions = [time_column >= start, time_column <= end]

    query = (table.select().where(*filter_conditions + date_conditions).order_by(time_column))

    return await database.fetch_all(query)


async def _validate_household_exists(household_id: int):
    """Validate that a household exists in the database and return it."""
    household_query = select(db.households_tbl).where(db.households_tbl.c.household_id == household_id)
    household = await database.fetch_one(household_query)
    if not household:
        raise HTTPException(status_code=404, detail=f"Household with id {household_id} not found")
    return household


async def _validate_location_exists(location_id: int):
    """Validate that a location exists in the database."""
    location_query = select(db.locations_tbl).where(db.locations_tbl.c.location_id == location_id)
    location = await database.fetch_one(location_query)
    if not location:
        raise HTTPException(status_code=404, detail=f"Location with id {location_id} not found")


@router.get("/price", response_model=list[PriceIn], response_model_exclude_none=True)
async def get_price(
    price_region_id: int | None = Query(None),
    household_id: int | None = Query(None),
    start: datetime = Query(...),
    end: datetime = Query(...)
):
    if not (price_region_id or household_id) or (price_region_id and household_id):
        raise HTTPException(status_code=400, detail="Provide either price_region_id or household_id, but not both.")

    if price_region_id:
        price_records = await fetch_timeseries(
            db.price_tbl,
            db.price_tbl.c.time,
            {"price_region_id": price_region_id},
            start,
            end
        )
        return [PriceIn(**record._mapping) for record in price_records]

    if household_id:
        # database is used by the helper, so we pass it or ensure it's accessible
        return await _get_calculated_household_prices(household_id, start, end, database)


@router.get("/pv", response_model=list[PVIn])
async def get_pv(household_id: int = Query(...), start: datetime = Query(...), end: datetime = Query(...)):
    await _validate_household_exists(household_id)
    results = await fetch_timeseries(db.pv_tbl, db.pv_tbl.c.time, {"household_id": household_id}, start, end)
    return [PVIn(**row._mapping) for row in results]


@router.get("/load", response_model=list[LoadIn])
async def get_load(household_id: int = Query(...), start: datetime = Query(...), end: datetime = Query(...)):
    await _validate_household_exists(household_id)
    results = await fetch_timeseries(db.load_tbl, db.load_tbl.c.time, {"household_id": household_id}, start, end)
    return [LoadIn(**row._mapping) for row in results]


@router.get("/weather_obs", response_model=list[WeatherObservationIn])
async def get_weather_obs(location_id: int = Query(...), start: datetime = Query(...), end: datetime = Query(...)):
    await _validate_location_exists(location_id)
    results = await fetch_timeseries(db.weather_obs_tbl, db.weather_obs_tbl.c.datetime, {"location_id": location_id},
                                  start, end)
    return [WeatherObservationIn(**row._mapping) for row in results]


@router.get("/weather_fcst", response_model=list[WeatherForecastIn])
async def get_weather_forecast(location_id: int = Query(...), start: datetime = Query(...), end: datetime = Query(...)):
    await _validate_location_exists(location_id)
    results = await fetch_timeseries(db.weather_fc_tbl, db.weather_fc_tbl.c.target_time, {"location_id": location_id},
                                  start, end)
    return [WeatherForecastIn(**row._mapping) for row in results]


### Helper function to calculate household prices

async def _get_calculated_household_prices(household_id: int, start: datetime, end: datetime, database_session: Any) -> list[PriceIn]:
    """
    Fetches and calculates prices for a specific household using its formula.
    """
    # Validate household exists and get household data
    household = await _validate_household_exists(household_id)

    # Get location to find price_region_id
    location_query = select(db.locations_tbl).where(db.locations_tbl.c.location_id == household.location_id)
    location = await database_session.fetch_one(location_query)
    if not location:
        raise HTTPException(status_code=404, detail=f"Location for household id {household_id} not found")

    raw_price_records = await fetch_timeseries(
        db.price_tbl,
        db.price_tbl.c.time,
        {"price_region_id": location.price_region_id},
        start,
        end
    )

    processed_prices = []
    for record in raw_price_records:
        calculated_price_value = calculate_price_with_formula(
            household.enduser_price_formula,
            record.price_eur_mwh
        )
        # Round the calculated price to 2 decimal places
        calculated_price_value = round(calculated_price_value, 2)
        
        calculated_feed_in_value = calculate_price_with_formula(
            household.enduser_feed_in_formula,
            record.price_eur_mwh
        )
        # Round the calculated feed-in price to 2 decimal places
        calculated_feed_in_value = round(calculated_feed_in_value, 2)
        
        processed_prices.append(
            PriceIn(
                time=record.time,
                price_region_id=record.price_region_id,
                price_eur_mwh=record.price_eur_mwh,
                calculated_price_eur_mwh=calculated_price_value,
                calculated_feed_in_eur_mwh=calculated_feed_in_value
            )
        )
    return processed_prices
from fastapi import APIRouter, Query
from datetime import datetime
from typing import Any, Dict
from sqlalchemy import Table
from api.db import engine, metadata, database

# Autoload materialized view tables for timeseries
view_price_1min = Table("price_1min", metadata, autoload_with=engine, schema="public")
view_pv_1min = Table("pv_1min", metadata, autoload_with=engine, schema="public")
view_load_1min = Table("load_1min", metadata, autoload_with=engine, schema="public")
view_weather_obs_1min = Table("weather_obs_1min", metadata, autoload_with=engine, schema="public")
view_weather_fcst_1min = Table("weather_fcst_1min", metadata, autoload_with=engine, schema="public")

router = APIRouter(prefix="/timeseries", tags=["timeseries"])

async def fetch_timeseries(table, filters: Dict[str, Any], start: datetime, end: datetime):
    """
    Fetch time series data from the specified table with date range filtering.
    
    Args:
        table: SQLAlchemy Table object to query
        filters: Dictionary of column names and values to filter by
        start: Start datetime (inclusive)
        end: End datetime (inclusive)
    """
    filter_conditions = [table.c[key] == value for key, value in filters.items()]
    date_conditions = [
        table.c.time >= start,
        table.c.time <= end
    ]
    
    query = (
        table.select()
        .where(*filter_conditions + date_conditions)
        .order_by(table.c.time)
    )
    
    return await database.fetch_all(query)

@router.get("/price")
async def get_price(
    region_id: int = Query(...),
    start: datetime = Query(...),
    end: datetime = Query(...)
):
    return await fetch_timeseries(view_price_1min, {"region_id": region_id}, start, end)

@router.get("/pv")
async def get_pv(
    household_id: int = Query(...),
    start: datetime = Query(...),
    end: datetime = Query(...)
):
    return await fetch_timeseries(view_pv_1min, {"household_id": household_id}, start, end)

@router.get("/load")
async def get_load(
    household_id: int = Query(...),
    start: datetime = Query(...),
    end: datetime = Query(...)
):
    return await fetch_timeseries(view_load_1min, {"household_id": household_id}, start, end)

@router.get("/weather_obs")
async def get_weather_obs(
    location_id: int = Query(...),
    start: datetime = Query(...),
    end: datetime = Query(...)
):
    return await fetch_timeseries(view_weather_obs_1min, {"location_id": location_id}, start, end)

@router.get("/weather_fcst")
async def get_weather_forecast(
    location_id: int = Query(...),
    start: datetime = Query(...),
    end: datetime = Query(...)
):
    return await fetch_timeseries(view_weather_fcst_1min, {"location_id": location_id}, start, end)

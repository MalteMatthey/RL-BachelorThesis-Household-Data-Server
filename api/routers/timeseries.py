from fastapi import APIRouter, Query
from datetime import datetime
from typing import Any, Dict
from sqlalchemy import Table, Column
from api.db import database
import api.db as db

router = APIRouter(prefix="/timeseries", tags=["timeseries"])

async def fetch_timeseries(table: Table, time_column: Column, filters: Dict[str, Any], start: datetime, end: datetime):
    filter_conditions = [table.c[key] == value for key, value in filters.items()]
    date_conditions = [
        time_column >= start,
        time_column <= end
    ]

    query = (
        table.select()
        .where(*filter_conditions + date_conditions)
        .order_by(time_column)
    )

    return await database.fetch_all(query)

@router.get("/price")
async def get_price(
    region_id: int = Query(...),
    start: datetime = Query(...),
    end: datetime = Query(...)
):
    return await fetch_timeseries(db.price_tbl, db.price_tbl.c.time, {"region_id": region_id}, start, end)

@router.get("/pv")
async def get_pv(
    household_id: int = Query(...),
    start: datetime = Query(...),
    end: datetime = Query(...)
):
    return await fetch_timeseries(db.pv_tbl, db.pv_tbl.c.time, {"household_id": household_id}, start, end)

@router.get("/load")
async def get_load(
    household_id: int = Query(...),
    start: datetime = Query(...),
    end: datetime = Query(...)
):
    return await fetch_timeseries(db.load_tbl, db.load_tbl.c.time, {"household_id": household_id}, start, end)

@router.get("/weather_obs")
async def get_weather_obs(
    location_id: int = Query(...),
    start: datetime = Query(...),
    end: datetime = Query(...)
):
    return await fetch_timeseries(db.weather_obs_tbl, db.weather_obs_tbl.c.datetime, {"location_id": location_id}, start, end)

@router.get("/weather_fcst")
async def get_weather_forecast(
    location_id: int = Query(...),
    start: datetime = Query(...),
    end: datetime = Query(...)
):
    return await fetch_timeseries(db.weather_fc_tbl, db.weather_fc_tbl.c.forecast_run, {"location_id": location_id}, start, end)

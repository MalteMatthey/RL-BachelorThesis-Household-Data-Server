from fastapi import APIRouter, HTTPException
from api.db import database
import api.db as db
from api.schemas import BulkWeatherObs, BulkPV, BulkLoad, BulkPrice, BulkWeatherForecast

router = APIRouter(prefix="/ingest", tags=["ingest"])

@router.post("/weather_observations")
async def ingest_weather_observations(payload: BulkWeatherObs):
    records = [item.model_dump() for item in payload.data]
    await database.execute_many(query=db.weather_obs.insert(), values=records)
    return {"inserted": len(records)}

@router.post("/weather_forecasts")
async def ingest_weather_forecasts(payload: BulkWeatherForecast):
    records = [item.model_dump() for item in payload.data]
    await database.execute_many(query=db.weather_fc.insert(), values=records)
    return {"inserted": len(records)}

@router.post("/pv_generation")
async def ingest_pv(payload: BulkPV):
    records = [item.model_dump() for item in payload.data]
    await database.execute_many(query=db.pv_tbl.insert(), values=records)
    return {"inserted": len(records)}

@router.post("/load_data")
async def ingest_load(payload: BulkLoad):
    records = [item.model_dump() for item in payload.data]
    await database.execute_many(query=db.load_tbl.insert(), values=records)
    return {"inserted": len(records)}

@router.post("/electricity_prices")
async def ingest_prices(payload: BulkPrice):
    records = [item.model_dump() for item in payload.data]
    await database.execute_many(query=db.price_tbl.insert(), values=records)
    return {"inserted": len(records)}
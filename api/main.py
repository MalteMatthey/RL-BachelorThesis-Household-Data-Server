import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, Header, HTTPException

from api.db import database, reflect_db_schema
from api.routers.ingest import router as ingest_router
from api.routers.metadata import router as metadata_router
from api.routers.timeseries import router as ts_router

API_KEY = os.getenv("API_KEY")


def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API Key")


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Connecting to database...")
    await database.connect()
    print("Database connected. Reflecting schema...")
    try:
        await reflect_db_schema()
    except Exception as e:
        print(f"Error reflecting database schema: {e}")
        raise  # Re-raise to prevent app from starting incorrectly
    print("Schema reflected. Application startup complete.")
    yield
    print("Disconnecting from database...")
    await database.disconnect()
    print("Database disconnected.")


app = FastAPI(
    title="Household Data API",
    lifespan=lifespan
)

app.include_router(ingest_router, dependencies=[Depends(verify_api_key)])
app.include_router(ts_router, dependencies=[Depends(verify_api_key)])
app.include_router(metadata_router, dependencies=[Depends(verify_api_key)])

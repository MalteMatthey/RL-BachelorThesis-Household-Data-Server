import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, Header, HTTPException

from api.db import database, reflect_db_schema
from api.routers.ingest import router as ingest_router
from api.routers.metadata import router as metadata_router
from api.routers.timeseries import router as ts_router
from api.routers.rl_agent_state import router as rl_agent_state_router
from api.services.b2_backup import b2_handler

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
    print("Schema reflected.")
    
    # Initialize B2 handler
    print("Initializing B2 backup handler...")
    if b2_handler.is_enabled():
        print("B2 backup handler initialized successfully.")
    else:
        print("B2 backup handler disabled (missing credentials or connection failed).")
    
    print("Application startup complete.")
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
app.include_router(rl_agent_state_router, dependencies=[Depends(verify_api_key)])

# Database connection and reflection
import os
import sqlalchemy
from databases import Database

DATABASE_URL = os.getenv("DATABASE_URL")

database = Database(DATABASE_URL)
engine = sqlalchemy.create_engine(DATABASE_URL)
metadata = sqlalchemy.MetaData()

# Define variables, they will be populated after reflection in main.py
weather_obs_tbl = None
weather_fc_tbl = None
pv_tbl = None
load_tbl = None
price_tbl = None

async def reflect_db_schema():
    """Reflects the database schema and assigns table objects."""
    global weather_obs_tbl, weather_fc_tbl, pv_tbl, load_tbl, price_tbl

    # Perform reflection
    try:
        print("Attempting to reflect database schema (all accessible objects)...")
        metadata.reflect(bind=engine)
        print("Reflection successful. Assigning tables...")

        weather_obs_tbl = metadata.tables["weather_observations"]
        weather_fc_tbl = metadata.tables["weather_forecasts"]
        pv_tbl = metadata.tables["pv_generation"]
        load_tbl = metadata.tables["load_data"]
        price_tbl = metadata.tables["electricity_prices"]
        
        print("Database schema reflected and assigned successfully.")
    except Exception as e:
        print(f"Error during database schema reflection: {e}")
        import traceback
        traceback.print_exc()
        raise # Re-raise the exception to signal failure

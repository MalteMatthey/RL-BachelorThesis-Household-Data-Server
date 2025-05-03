# Database connection and reflection
import os
import sqlalchemy
from databases import Database

DATABASE_URL = os.getenv("DATABASE_URL")

database = Database(DATABASE_URL)
engine = sqlalchemy.create_engine(DATABASE_URL)
metadata = sqlalchemy.MetaData()

# Define variables, but they will be populated after reflection in main.py
weather_obs = None
weather_fc = None
pv_tbl = None
load_tbl = None
price_tbl = None
view_price_1min = None
view_pv_1min = None
view_load_1min = None
view_weather_obs_1min = None
view_weather_fcst_1min = None

async def reflect_db_schema():
    """Reflects the database schema and assigns table/view objects."""
    global weather_obs, weather_fc, pv_tbl, load_tbl, price_tbl
    global view_price_1min, view_pv_1min, view_load_1min, view_weather_obs_1min, view_weather_fcst_1min

    # Perform reflection
    # Use a try-except block for better error handling during reflection
    try:
        print("Attempting to reflect database schema (all accessible objects)...")
        # Reflect all accessible tables/views, including views (materialized views)
        metadata.reflect(bind=engine, views=True)
        print("Reflection successful. Assigning tables/views...")

        # Manually ensure materialized views are loaded (autoload) if not reflected
        for view_name in ["price_1min", "pv_1min", "load_1min", "weather_obs_1min", "weather_fcst_1min"]:
            if view_name not in metadata.tables:
                # Autoload the view into metadata
                metadata.tables[view_name] = sqlalchemy.Table(
                    view_name,
                    metadata,
                    autoload_with=engine,
                    schema="public"
                )

        weather_obs = metadata.tables["weather_observations"]
        weather_fc = metadata.tables["weather_forecasts"]
        pv_tbl = metadata.tables["pv_generation"]
        load_tbl = metadata.tables["load_data"]
        price_tbl = metadata.tables["electricity_prices"]
        view_price_1min = metadata.tables["price_1min"]
        view_pv_1min = metadata.tables["pv_1min"]
        view_load_1min = metadata.tables["load_1min"]
        view_weather_obs_1min = metadata.tables["weather_obs_1min"]
        view_weather_fcst_1min = metadata.tables["weather_fcst_1min"]

        print("Database schema reflected and assigned successfully.")
    except Exception as e:
        print(f"!!! Error during database schema reflection: {e}")
        # Consider logging the full traceback here for detailed debugging
        import traceback
        traceback.print_exc()
        raise # Re-raise the exception to signal failure

import pandas as pd
from datetime import datetime
from typing import List, Dict
import os
import pickle

# List of weather parameters to be processed
WEATHER_PARAMETERS = [
    'temperature', 'dew_point', 'humidity', 'wind_speed', 'wind_direction',
    'precipitation', 'radiation_diffuse', 'radiation_direct'
]

async def create_synthetic_forecast(
    loc_id: int,
    start_time: datetime,
    end_time: datetime,
    pre_2020_observations: List[Dict],
    historical_observations: List[Dict],
    historical_forecasts: List[Dict]
) -> List[Dict]:
    """
    Generates synthetic weather forecasts for a period before _MIN_FORECAST_DATE.

    This method learns a simple forecast error (bias) from historical data (2020-2024)
    and applies it to pre-2020 observation data to create synthetic forecasts.
    """
    # --- Debugging: Save inputs to files ---
    debug_dir = "debug_data"
    os.makedirs(debug_dir, exist_ok=True)
    
    run_dir = os.path.join(debug_dir, datetime.now().strftime("%Y%m%d_%H%M%S"))
    os.makedirs(run_dir, exist_ok=True)

    # Save List[Dict] as parquet and pickle files
    for name, data in [("pre_2020_observations", pre_2020_observations), 
                       ("historical_observations", historical_observations), 
                       ("historical_forecasts", historical_forecasts)]:
        if data:
            pd.DataFrame(data).to_parquet(os.path.join(run_dir, f"{name}.parquet"))
            with open(os.path.join(run_dir, f"{name}.pkl"), "wb") as f:
                pickle.dump(data, f)

    # Save other arguments
    with open(os.path.join(run_dir, "params.pkl"), "wb") as f:
        pickle.dump({
            "loc_id": loc_id,
            "start_time": start_time,
            "end_time": end_time
        }, f)
    # --- End Debugging ---

    return []


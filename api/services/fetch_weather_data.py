import random
from datetime import datetime, timedelta
from typing import List


# Placeholder function to simulate fetching weather observations
async def fetch_external_weather_observations(location_id: int, start: datetime, end: datetime) -> List[dict]:
    print(f"Simulating fetch for weather observations: loc={location_id}, start={start}, end={end}")
    data = []
    current_time = start
    while current_time <= end:
        data.append({
            "datetime": current_time,
            "location_id": location_id,
            "temp": random.uniform(5, 25),
            "humidity": random.uniform(40, 90),
            "precip": random.uniform(0, 5) if random.random() > 0.8 else 0,
            "windspeed": random.uniform(0, 30),
            "solarradiation": random.uniform(0, 1000) if 6 <= current_time.hour <= 18 else 0,
            # Add other fields as needed, potentially None or random
        })
        current_time += timedelta(hours=1)  # Assuming hourly data
    print(f"Simulated {len(data)} weather observation records.")
    return data


# Placeholder function to simulate fetching weather forecasts
async def fetch_external_weather_forecasts(location_id: int, start: datetime, end: datetime) -> List[dict]:
    print(f"Simulating fetch for weather forecasts: loc={location_id}, start={start}, end={end}")
    data = []
    forecast_run_time = start - timedelta(hours=6)  # Simulate forecast run few hours before start
    target_time = start
    while target_time <= end:
        data.append({
            "forecast_run": forecast_run_time,
            "target_time": target_time,
            "location_id": location_id,
            "temp": random.uniform(5, 25),
            "humidity": random.uniform(40, 90),
            "precip": random.uniform(0, 5) if random.random() > 0.8 else 0,
            "windspeed": random.uniform(0, 30),
            "solarradiation": random.uniform(0, 1000) if 6 <= target_time.hour <= 18 else 0,
            # Add other fields as needed, potentially None or random
        })
        target_time += timedelta(hours=1)  # Assuming hourly forecast steps
    print(f"Simulated {len(data)} weather forecast records.")
    return data

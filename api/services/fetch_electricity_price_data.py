import random
from datetime import datetime, timedelta
from typing import List


# Placeholder function to simulate fetching electricity prices
async def fetch_external_electricity_prices(region_id: int, start: datetime, end: datetime) -> List[dict]:
    print(f"Simulating fetch for electricity prices: region={region_id}, start={start}, end={end}")
    data = []
    current_time = start
    while current_time <= end:
        data.append({
            "time": current_time,
            "region_id": region_id,
            "price_eur_mwh": random.uniform(20, 150)
        })
        current_time += timedelta(hours=1)  # Assuming hourly prices
    print(f"Simulated {len(data)} electricity price records.")
    return data

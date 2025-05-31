import requests
from typing import Optional


async def get_altitude_from_coordinates(latitude: float, longitude: float) -> float:
    """
    Fetch altitude from latitude and longitude using Open-Elevation API.
    Returns altitude in meters, defaults to 200m if lookup fails.
    """
    try:
        # Use Open-Elevation API (free service)
        url = f"https://api.open-elevation.com/api/v1/lookup?locations={latitude},{longitude}"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data and 'results' in data and len(data['results']) > 0:
                altitude = data['results'][0]['elevation']
                print(f"Fetched altitude: {altitude}m for coordinates {latitude}, {longitude}")
                return float(altitude)
    except Exception as e:
        print(f"Error fetching altitude for coordinates {latitude}, {longitude}: {e}")
    
    # Default altitude if lookup fails
    print(f"Using default altitude 200m for coordinates {latitude}, {longitude}")
    return 200.0
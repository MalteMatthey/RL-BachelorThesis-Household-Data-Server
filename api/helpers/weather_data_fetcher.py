import pandas as pd
from datetime import datetime
from typing import Optional
from api.db import database as app_db


async def fetch_weather_data_from_db(
    location_id: int,
    start_time: datetime,
    end_time: datetime
) -> Optional[pd.DataFrame]:
    if not app_db.is_connected:
        print("Warning: Database not connected. Cannot fetch weather data.")
        return None
    
    try:
        obs_query = """
        SELECT datetime as time, temp as temp_air, windspeed as wind_speed, snowdepth as snow_depth, snow as snowfall
        FROM weather_observations
        WHERE location_id = :location_id 
        AND datetime >= :start_time 
        AND datetime <= :end_time
        ORDER BY datetime
        """
        
        rows = await app_db.fetch_all(
            query=obs_query, 
            values={
                "location_id": location_id,
                "start_time": start_time,
                "end_time": end_time
            }
        )
        
        if rows:
            # Convert to DataFrame and set index
            weather_df = pd.DataFrame([dict(row) for row in rows])
            weather_df['time'] = pd.to_datetime(weather_df['time'])
            weather_df.set_index('time', inplace=True)
            
            # Ensure timezone-aware index
            if weather_df.index.tz is None:
                weather_df.index = weather_df.index.tz_localize('UTC')
            
            print(f"Found {len(weather_df)} weather observation records")
            return weather_df
        
        print(f"No weather data found for location {location_id}")
        return None
        
    except Exception as e:
        print(f"Error fetching weather data: {e}")
        return None


def combine_irradiation_and_weather_data(
    irradiation_data: pd.DataFrame,
    weather_data: Optional[pd.DataFrame]
) -> pd.DataFrame:
    # Start with irradiation data
    combined_data = irradiation_data.copy()
    
    if weather_data is not None and not weather_data.empty:
        # Ensure both DataFrames have timezone-aware indices
        if combined_data.index.tz is None:
            combined_data.index = combined_data.index.tz_localize('UTC')
        if weather_data.index.tz is None:
            weather_data.index = weather_data.index.tz_localize('UTC')
        
        # Align timezones
        combined_data.index = combined_data.index.tz_convert('UTC')
        weather_data.index = weather_data.index.tz_convert('UTC')
        
        # Join weather data with irradiation data (left join to keep all irradiation timestamps)
        combined_data = combined_data.join(weather_data, how='left')

        # Propagate hourly weather values to all timestamps within the hour
        combined_data['temp_air'] = combined_data['temp_air'].ffill()
        combined_data['wind_speed'] = combined_data['wind_speed'].ffill()
        combined_data['snow_depth'] = combined_data['snow_depth'].ffill()
        combined_data['snowfall'] = combined_data['snowfall'].ffill()

        # Count how many values were successfully joined
        temp_count = combined_data['temp_air'].notna().sum()
        wind_count = combined_data['wind_speed'].notna().sum()
        snow_depth_count = combined_data['snow_depth'].notna().sum()
        snowfall_count = combined_data['snowfall'].notna().sum()
        total_count = len(combined_data)
        print(f"Combined data: {temp_count}/{total_count} temperature values, {wind_count}/{total_count} wind speed values, {snow_depth_count}/{total_count} snow depth values, {snowfall_count}/{total_count} snowfall values")
    else:
        print("No weather data available from database")

    return combined_data

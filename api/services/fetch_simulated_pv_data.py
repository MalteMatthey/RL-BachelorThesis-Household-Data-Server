import os
import pandas as pd
import pvlib
import cdsapi
from datetime import datetime, timezone, timedelta
from typing import Set, List, Dict, Any, Optional, Tuple
import tempfile

from .b2_backup import b2_handler
from ..helpers.pv_simulation import calculate_pv_generation, apply_volatility_to_generation_series
from ..helpers.weather_data_fetcher_from_db import fetch_weather_data_from_db, combine_irradiation_and_weather_data
from ..helpers.elevation_helper import get_altitude_from_coordinates
from api.db import database as app_db

# --- Configuration ---
CAMS_DATASET = "cams-solar-radiation-timeseries"

async def fetch_simulated_pv_data_per_household(
    household_time_ranges: Dict[int, Tuple[datetime, datetime]]
) -> List[Dict[str, Any]]:
    """
    Fetch simulated PV data for given households with individual time ranges.
    Each household can have a different start and end time.
    Uses CAMS for irradiation data and pvlib for simulation.
    """
    print(f"Starting PV data simulation for {len(household_time_ranges)} households with individual time ranges")
    
    all_pv_results: List[Dict[str, Any]] = []

    for household_id, (start_time, end_time) in household_time_ranges.items():
        print(f"Simulating PV for household {household_id} from {start_time} to {end_time}")
        
        # Ensure timezone-aware datetimes
        start_utc = start_time.astimezone(timezone.utc) if start_time.tzinfo else start_time.replace(tzinfo=timezone.utc)
        end_utc = end_time.astimezone(timezone.utc) if end_time.tzinfo else end_time.replace(tzinfo=timezone.utc)
        
        try:
            household_data = await _get_household_with_location(household_id)
            
            if not household_data:
                print(f"No data found for household {household_id}")
                continue
                
            # Get altitude for the household's location
            altitude = await get_altitude_from_coordinates(
                household_data['latitude'], 
                household_data['longitude']
            )
                
            # Fetch CAMS irradiation data for this household's location
            irradiation_data = await _fetch_cams_irradiation_data(
                latitude=household_data['latitude'],
                longitude=household_data['longitude'],
                start_time=start_utc,
                end_time=end_utc
            )
            
            if irradiation_data is None or irradiation_data.empty:
                print(f"No irradiation data available for household {household_id}")
                continue
            # Fetch actual weather data (temperature and wind speed) from database
            weather_data = await fetch_weather_data_from_db(
                location_id=household_data['location_id'],
                start_time=start_utc,
                end_time=end_utc
            )
            
            # Combine irradiation data with weather data
            combined_weather_data = combine_irradiation_and_weather_data(irradiation_data, weather_data)
            # Calculate PV generation for this household
            ac_power = calculate_pv_generation(
                latitude=household_data['latitude'],
                longitude=household_data['longitude'],
                altitude=altitude,
                tilt=household_data['pv_tilt'],
                azimuth=household_data['pv_azimuth'],
                capacity_kw=household_data['pv_capacity_kw'],
                performance_ratio=household_data['pv_performance_ratio'],
                temp_model_key=household_data['pv_temp_model_key'],
                module_temp_coeff_power=household_data['pv_module_temp_coeff_power'],
                weather_data=combined_weather_data
            )
            # Convert power (W) to energy (kWh) for 15-minute intervals
            energy_kwh = (ac_power / 1000) * 0.25  # 15 minutes = 0.25 hours
            
            # Apply realistic volatility to the generation data
            volatile_energy_kwh = apply_volatility_to_generation_series(energy_kwh)
            
            # Create result records
            for timestamp, generation in volatile_energy_kwh.items():
                all_pv_results.append({
                    "household_id": household_id,
                    "time": timestamp.astimezone(timezone.utc),
                    "generation_kwh": round(max(0, generation), 5)  # Ensure non-negative and round to 5 decimals
                })
                
        except Exception as e:
            print(f"Error simulating PV for household {household_id}: {e}")
            continue
    
    # Sort results by time and household_id
    all_pv_results.sort(key=lambda x: (x['time'], x['household_id']))
    
    print(f"Finished PV data simulation. Generated {len(all_pv_results)} records for individual households.")
    return all_pv_results


async def _get_household_with_location(household_id: int) -> Optional[Dict[str, Any]]:
    """
    Get household data with location coordinates for a single household.
    """
    if not app_db.is_connected:
        print("Warning: Database not connected. Cannot fetch household data.")
        return None

    try:
        # Query household and location data
        query = """
        SELECT h.household_id, h.location_id, h.pv_tilt, h.pv_azimuth, h.pv_capacity_kw, 
               h.pv_performance_ratio, h.pv_temp_model_key, h.pv_module_temp_coeff_power,
               l.latitude, l.longitude, l.name as location_name
        FROM households h
        JOIN locations l ON h.location_id = l.location_id
        WHERE h.household_id = :household_id
        """
        
        row = await app_db.fetch_one(query=query, values={"household_id": household_id})
        
        if not row:
            return None
        
        return {
            'household_id': row['household_id'],
            'location_id': row['location_id'],
            'pv_tilt': row['pv_tilt'],
            'pv_azimuth': row['pv_azimuth'],
            'pv_capacity_kw': row['pv_capacity_kw'],
            'pv_performance_ratio': row['pv_performance_ratio'],
            'pv_temp_model_key': row['pv_temp_model_key'],
            'pv_module_temp_coeff_power': row['pv_module_temp_coeff_power'],
            'latitude': row['latitude'],
            'longitude': row['longitude'],
            'location_name': row['location_name']
        }
    except Exception as e:
        print(f"Error fetching household data: {e}")
        return None


async def _fetch_cams_irradiation_data(
    latitude: float,
    longitude: float,
    start_time: datetime,
    end_time: datetime
) -> Optional[pd.DataFrame]:
    """
    Fetch irradiation data from CAMS API with B2 caching for raw responses.
    Returns None if data cannot be fetched.
    """
    # CAMS API parameters - use "-999." to let API determine altitude from coordinates
    params = {
        "sky_type": "observed_cloud",
        "location": {"longitude": longitude, "latitude": latitude},
        "altitude": ["-999."],
        "date": [f"{start_time.strftime('%Y-%m-%d')}/{end_time.strftime('%Y-%m-%d')}"],
        "time_step": "15minute",
        "time_reference": "universal_time",
        "format": "csv"
    }

    api_url = f"cams-solar-radiation" # Used for B2 backup filename generation
    backup_filename = await b2_handler.check_backup(api_url, params, file_extension="csv")

    if backup_filename:
        raw_data = await b2_handler.get_backup_bytes(backup_filename)
        if raw_data:
            print(f"Using cached CAMS data: {backup_filename}")
            tmp_file_path = None  # Ensure tmp_file_path is defined for the finally block
            try:
                # Decode the raw bytes to a string
                decoded_csv_content = raw_data.decode('utf-8')

                with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv', encoding='utf-8') as tmp_f:
                    tmp_f.write(decoded_csv_content)
                    tmp_file_path = tmp_f.name
                
                # Now tmp_file_path points to a closed file on disk with the CSV content.
                # pvlib.iotools.read_cams can handle this path.
                irradiation_data, _ = pvlib.iotools.read_cams(tmp_file_path)
                return irradiation_data

            except UnicodeDecodeError as e:
                print(f"Error decoding cached CAMS data (UTF-8) from {backup_filename}: {e}")
                # Consider deleting the corrupted backup from B2 if this happens frequently
                return None
            except Exception as e:
                # This will catch errors from tempfile operations or pvlib.iotools.read_cams
                print(f"Error parsing cached CAMS data from {backup_filename} (using temp file {tmp_file_path}): {e}")
                return None
            finally:
                # Clean up the temporary file
                if tmp_file_path and os.path.exists(tmp_file_path):
                    try:
                        os.remove(tmp_file_path)
                    except Exception as e_remove:
                        # Log if removal fails, but don't let it crash the main flow
                        print(f"Warning: Failed to remove temporary CAMS cache file {tmp_file_path}: {e_remove}")
    
    # Fetch from CAMS API (if no backup or backup processing failed)
    print(f"Fetching CAMS data from CDS API for location {latitude}, {longitude}")
    try:
        # Use CDS API to fetch data
        client = cdsapi.Client()
        result = client.retrieve(CAMS_DATASET, params)

        # Download and read the data
        result_download_path = result.download()
        irradiation_data, cams_metadata = pvlib.iotools.read_cams(result_download_path)
        
        # Save raw CSV to B2 for caching
        raw_csv_bytes_for_cache = None
        try:
            with open(result_download_path, 'rb') as f:
                raw_csv_bytes_for_cache = f.read()
        except FileNotFoundError:
             print(f"Warning: CAMS data file {result_download_path} not found for caching after read by pvlib.")

        if raw_csv_bytes_for_cache:
            await b2_handler.save_backup(api_url, params, raw_csv_bytes_for_cache, file_extension="csv")
            print(f"Saved CAMS data to B2 cache")

        return irradiation_data

    except Exception as e:
        print(f"Error fetching from CAMS API: {e}")
        return None

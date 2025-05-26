"""
PV simulation logic using pvlib.
Adapted from irradiance_test.py for modular use.
"""
import pvlib
from pvlib.location import Location
from pvlib.temperature import TEMPERATURE_MODEL_PARAMETERS
import pandas as pd
from timezonefinder import TimezoneFinder

# Default constants
DEFAULT_TEMP_AIR_CELSIUS = 20
DEFAULT_WIND_SPEED_MPS = 1.0


def calculate_pv_generation(
    latitude: float,
    longitude: float,
    altitude: float,
    tilt: float,
    azimuth: float,
    capacity_kw: float,
    performance_ratio: float,
    temp_model_key: str,
    module_temp_coeff_power: float,
    weather_data: pd.DataFrame
) -> pd.Series:
    """
    Calculate PV generation using pvlib.
    
    Args:
        latitude: Location latitude
        longitude: Location longitude
        altitude: Location altitude in meters
        tilt: PV panel tilt angle in degrees
        azimuth: PV panel azimuth angle in degrees
        capacity_kw: System capacity in kW
        performance_ratio: Overall system performance ratio
        temp_model_key: Temperature model key for pvlib
        module_temp_coeff_power: Module power temperature coefficient (1/°C)
        weather_data: DataFrame with columns 'ghi', 'dni', 'dhi', 'temp_air', 'wind_speed'
    
    Returns:
        Series with AC power output in Watts
    """
    # Determine timezone from coordinates
    tf = TimezoneFinder()
    determined_timezone = tf.timezone_at(lng=longitude, lat=latitude)
    if determined_timezone is None:
        raise ValueError(f"Could not determine timezone for lat={latitude}, lon={longitude}")

    # Set up location
    location = Location(latitude, longitude, tz=determined_timezone, altitude=altitude)
    
    # Ensure weather data has the right timezone
    if weather_data.index.tz is None:
        weather_data.index = weather_data.index.tz_localize('UTC')
    weather_data.index = weather_data.index.tz_convert(location.tz)
    
    # Add default temp_air and wind_speed if not present
    if 'temp_air' not in weather_data.columns:
        weather_data['temp_air'] = DEFAULT_TEMP_AIR_CELSIUS
    if 'wind_speed' not in weather_data.columns:
        weather_data['wind_speed'] = DEFAULT_WIND_SPEED_MPS
    
    # Solar position calculation
    solpos = location.get_solarposition(weather_data.index)
    
    # POA irradiance calculation
    poa = pvlib.irradiance.get_total_irradiance(
        surface_tilt=tilt,
        surface_azimuth=azimuth,
        dni=weather_data["dni"],
        ghi=weather_data["ghi"],
        dhi=weather_data["dhi"],
        solar_zenith=solpos["zenith"],
        solar_azimuth=solpos["azimuth"],
    )
    
    # Temperature model parameters
    temp_params = TEMPERATURE_MODEL_PARAMETERS['sapm'][temp_model_key]
    
    # Cell temperature calculation
    temp_cell = pvlib.temperature.sapm_cell(
        poa_global=poa["poa_global"],
        temp_air=weather_data["temp_air"],
        wind_speed=weather_data["wind_speed"],
        **temp_params
    )
    
    # DC power calculation
    capacity_w = capacity_kw * 1000  # Convert kW to W
    dc_module_output = pvlib.pvsystem.pvwatts_dc(
        g_poa_effective=poa["poa_global"],
        temp_cell=temp_cell,
        pdc0=capacity_w,
        gamma_pdc=module_temp_coeff_power
    )
    
    # Apply performance ratio to get AC power
    ac_power = dc_module_output * performance_ratio
    
    return ac_power

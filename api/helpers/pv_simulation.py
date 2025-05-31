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
DEFAULT_SNOW_DEPTH_CM = 0.0
DEFAULT_SNOWFALL_CM_PER_INTERVAL = 0.0


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
    print(f"Starting PV simulation for location: lat={latitude:.3f}, lon={longitude:.3f}, alt={altitude}m")
    print(f"PV system: {capacity_kw}kW, tilt={tilt}°, azimuth={azimuth}°, PR={performance_ratio:.3f}")
    
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
        print(f"Added default temp_air: {DEFAULT_TEMP_AIR_CELSIUS}°C")
    else:
        temp_stats = weather_data['temp_air']
        print(f"Temperature: min={temp_stats.min():.1f}°C, max={temp_stats.max():.1f}°C, mean={temp_stats.mean():.1f}°C")
        
    if 'wind_speed' not in weather_data.columns:
        weather_data['wind_speed'] = DEFAULT_WIND_SPEED_MPS
        print(f"Added default wind_speed: {DEFAULT_WIND_SPEED_MPS} m/s")
    else:
        wind_stats = weather_data['wind_speed']
        print(f"Wind speed: min={wind_stats.min():.1f} m/s, max={wind_stats.max():.1f} m/s, mean={wind_stats.mean():.1f} m/s")
        
    if 'snow_depth' not in weather_data.columns:
        weather_data['snow_depth'] = DEFAULT_SNOW_DEPTH_CM
        print(f"Snow depth: max={weather_data['snow_depth'].max():.1f} cm, mean={weather_data['snow_depth'].mean():.1f} cm, periods with snow={(weather_data['snow_depth'] > 0).sum()}")
        
    if 'snowfall' not in weather_data.columns:
        weather_data['snowfall'] = DEFAULT_SNOWFALL_CM_PER_INTERVAL
        print(f"Added default snowfall: {DEFAULT_SNOWFALL_CM_PER_INTERVAL} cm/interval")
    else:
        # If snowfall data is provided, assume it's hourly snowfall in cm.
        # Convert to cm per 15-minute interval for a 15-minute simulation.
        original_snowfall_max = weather_data['snowfall'].max()
        weather_data['snowfall'] = weather_data['snowfall'] / 4.0
        snowfall_periods = (weather_data['snowfall'] > 0).sum()
        total_snowfall = weather_data['snowfall'].sum()
        print(f"Snowfall: max hourly={original_snowfall_max:.1f} cm, total={total_snowfall*4:.1f} cm, periods with snowfall={snowfall_periods}")
    
    # Solar position calculation
    print("Calculating solar positions...")
    solpos = location.get_solarposition(weather_data.index)
    max_elevation = (90 - solpos["zenith"]).max()
    print(f"Maximum solar elevation: {max_elevation:.1f}°")
    
    # POA irradiance calculation
    print("Calculating plane-of-array irradiance...")
    poa_irradiance = pvlib.irradiance.get_total_irradiance(
        surface_tilt=tilt,
        surface_azimuth=azimuth,
        dni=weather_data["dni"],
        ghi=weather_data["ghi"],
        dhi=weather_data["dhi"],
        solar_zenith=solpos["zenith"],
        solar_azimuth=solpos["azimuth"],
    )
    
    poa_stats = poa_irradiance["poa_global"]
    print(f"POA Global: max={poa_stats.max():.1f} W/m², mean={poa_stats.mean():.1f} W/m²")

    # Determine interval of weather data (e.g., in minutes)
    # Assuming weather_data.index is a DatetimeIndex
    if len(weather_data.index) > 1:
        interval_seconds = (weather_data.index[1] - weather_data.index[0]).total_seconds()
        interval_minutes = interval_seconds / 60.0
        intervals_per_hour = 60.0 / interval_minutes
        print(f"Detected weather data interval: {interval_minutes:.1f} minutes ({intervals_per_hour:.1f} intervals per hour)")
    else:
        intervals_per_hour = 4.0 # Assuming 15-min if cannot detect
        print(f"Warning: Could not determine weather interval, assuming {15.0} minutes.")

    # --- Parameter Adjustments for Timestep ---
    # Original hourly parameters from documentation/defaults
    original_hourly_slide_amount_coeff = 0.197
    original_hourly_threshold_snowfall = 1.0 # cm/hr

    # Adjusted for the actual timestep of your data
    adjusted_slide_amount_coeff = 1 - (1 - original_hourly_slide_amount_coeff)**(1 / intervals_per_hour)
    adjusted_threshold_snowfall = original_hourly_threshold_snowfall / intervals_per_hour # cm/interval

    print("Calculating snow coverage with adjusted parameters...")
    snow_coverage_fraction = pvlib.snow.coverage_nrel(
        snow_depth=weather_data['snow_depth'],
        surface_tilt=tilt,
        snowfall=weather_data['snowfall'],
        poa_irradiance=poa_irradiance['poa_global'],
        temp_air=weather_data['temp_air'],
        initial_coverage=0, # Default
        threshold_snowfall=adjusted_threshold_snowfall, # Adjusted
        threshold_depth=1.0, # Default, or test with 0.1 or by passing snow_depth=None
        can_slide_coefficient=-80., # Default
        slide_amount_coefficient=adjusted_slide_amount_coeff # Adjusted
    )
    
    # Log snow coverage statistics
    max_coverage = snow_coverage_fraction.max()
    mean_coverage = snow_coverage_fraction.mean()
    periods_with_coverage = (snow_coverage_fraction > 0).sum()
    periods_fully_covered = (snow_coverage_fraction >= 0.99).sum()
    print(f"Snow coverage: max={max_coverage:.3f}, mean={mean_coverage:.3f}")
    print(f"Periods with snow coverage: {periods_with_coverage}, fully covered: {periods_fully_covered}")
    
    # Adjust POA global irradiance for snow coverage
    # (1 - snow_coverage_fraction) is the fraction of the module *not* covered by snow
    effective_poa_global = poa_irradiance["poa_global"] * (1 - snow_coverage_fraction)
    
    # Log effectiveness of snow impact
    total_irradiance_loss = (poa_irradiance["poa_global"] - effective_poa_global).sum()
    total_potential_irradiance = poa_irradiance["poa_global"].sum()
    if total_potential_irradiance > 0:
        snow_loss_percentage = (total_irradiance_loss / total_potential_irradiance) * 100
        print(f"Snow-related irradiance loss: {snow_loss_percentage:.2f}% of total potential")
    
    effective_stats = effective_poa_global
    print(f"Effective POA (after snow): max={effective_stats.max():.1f} W/m², mean={effective_stats.mean():.1f} W/m²")
    
    # Temperature model parameters
    print(f"Using temperature model: {temp_model_key}")
    temp_params = TEMPERATURE_MODEL_PARAMETERS['sapm'][temp_model_key]
    print(f"Temperature model parameters: {temp_params}")
    
    # Cell temperature calculation using effective POA
    temp_cell = pvlib.temperature.sapm_cell(
        poa_global=effective_poa_global,
        temp_air=weather_data["temp_air"],
        wind_speed=weather_data["wind_speed"],
        **temp_params
    )
    
    cell_temp_stats = temp_cell
    print(f"Cell temperature: min={cell_temp_stats.min():.1f}°C, max={cell_temp_stats.max():.1f}°C, mean={cell_temp_stats.mean():.1f}°C")
    
    # DC power calculation using effective POA
    capacity_w = capacity_kw * 1000  # Convert kW to W
    print(f"DC capacity: {capacity_w} W, temp coefficient: {module_temp_coeff_power:.4f} /°C")
    
    dc_module_output = pvlib.pvsystem.pvwatts_dc(
        g_poa_effective=effective_poa_global,
        temp_cell=temp_cell,
        pdc0=capacity_w,
        gamma_pdc=module_temp_coeff_power
    )
    
    dc_stats = dc_module_output
    print(f"DC output: max={dc_stats.max():.1f} W, mean={dc_stats.mean():.1f} W")
    
    # Apply performance ratio to get AC power
    ac_power = dc_module_output * performance_ratio
    
    ac_stats = ac_power
    total_ac_energy_kwh = ac_stats.sum() / 1000 / (len(ac_stats) / (365 * 24))  # Approximate annual kWh
    capacity_factor = (ac_stats.mean() / (capacity_kw * 1000)) * 100
    
    print(f"AC output: max={ac_stats.max():.1f} W, mean={ac_stats.mean():.1f} W")
    print(f"Estimated capacity factor: {capacity_factor:.2f}%")
    print(f"Estimated annual energy: {total_ac_energy_kwh:.1f} kWh")
    print("PV simulation completed successfully")
    
    return ac_power

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# Ingest payload models
class WeatherObservationIn(BaseModel):
    datetime: datetime
    location_id: int
    tempmax: Optional[float] = None
    tempmin: Optional[float] = None
    temp: Optional[float] = None
    humidity: Optional[float] = None
    feelslikemax: Optional[float] = None
    feelslikemin: Optional[float] = None
    feelslike: Optional[float] = None
    dew: Optional[float] = None
    precip: Optional[float] = None
    precipprob: Optional[float] = None
    precipcover: Optional[float] = None
    snow: Optional[float] = None
    snowdepth: Optional[float] = None
    windgust: Optional[float] = None
    windspeed: Optional[float] = None
    winddir: Optional[float] = None
    pressure: Optional[float] = None
    cloudcover: Optional[float] = None
    visibility: Optional[float] = None
    solarradiation: Optional[float] = None
    solarenergy: Optional[float] = None
    uvindex: Optional[float] = None
    severerisk: Optional[float] = None
    windspeedmax: Optional[float] = None
    windspeedmean: Optional[float] = None
    windspeedmin: Optional[float] = None
    sunrise: Optional[str] = None
    sunset: Optional[str] = None
    moonphase: Optional[float] = None
    conditions: Optional[str] = None
    windspeed50: Optional[float] = None
    winddir50: Optional[float] = None
    windspeed80: Optional[float] = None
    winddir80: Optional[float] = None
    windspeed100: Optional[float] = None
    winddir100: Optional[float] = None
    ghiradiation: Optional[float] = None
    dniradiation: Optional[float] = None
    difradiation: Optional[float] = None
    sunelevation: Optional[float] = None


class PVIn(BaseModel):
    time: datetime
    household_id: int
    generation_kwh: float


class BulkPV(BaseModel):
    data: List[PVIn] = Field(...)


class LoadIn(BaseModel):
    time: datetime
    household_id: int
    consumption_kwh: float


class BulkLoad(BaseModel):
    data: List[LoadIn] = Field(...)
    simulate_pv_generation: bool = False    


class PriceIn(BaseModel):
    time: datetime
    price_region_id: int
    price_eur_mwh: float
    calculated_price_eur_mwh: Optional[float] = None
    calculated_feed_in_eur_mwh: Optional[float] = None


class PriceRegionIn(BaseModel):
    price_region_id: Optional[int] = None
    name: str
    bidding_zone_eic_code: str


class LocationIn(BaseModel):
    location_id: Optional[int] = None
    price_region_id: int
    name: str
    latitude: float
    longitude: float


class HouseholdIn(BaseModel):
    household_id: Optional[int] = None
    location_id: int
    name: str
    enduser_price_formula: str
    enduser_feed_in_formula: str
    pv_tilt: float
    pv_azimuth: float
    pv_capacity_kw: float
    pv_performance_ratio: float
    pv_temp_model_key: str
    pv_module_temp_coeff_power: float
    battery_capacity_kwh: float
    battery_efficiency: float
    battery_max_charge_power: float
    battery_max_discharge_power: float


class WeatherForecastBase(BaseModel):
    forecast_run: datetime
    target_time: datetime
    tempmax: Optional[float] = None
    tempmin: Optional[float] = None
    temp: Optional[float] = None
    feelslikemax: Optional[float] = None
    feelslikemin: Optional[float] = None
    feelslike: Optional[float] = None
    dew: Optional[float] = None
    humidity: Optional[float] = None
    precip: Optional[float] = None
    precipprob: Optional[float] = None
    precipcover: Optional[float] = None
    snow: Optional[float] = None
    snowdepth: Optional[float] = None
    windgust: Optional[float] = None
    windspeed: Optional[float] = None
    winddir: Optional[float] = None
    pressure: Optional[float] = None
    cloudcover: Optional[float] = None
    visibility: Optional[float] = None
    solarradiation: Optional[float] = None
    solarenergy: Optional[float] = None
    uvindex: Optional[float] = None
    severerisk: Optional[float] = None
    windspeedmax: Optional[float] = None
    windspeedmean: Optional[float] = None
    windspeedmin: Optional[float] = None
    sunrise: Optional[str] = None
    sunset: Optional[str] = None
    moonphase: Optional[float] = None
    conditions: Optional[str] = None
    windspeed50: Optional[float] = None
    winddir50: Optional[float] = None
    windspeed80: Optional[float] = None
    winddir80: Optional[float] = None
    windspeed100: Optional[float] = None
    winddir100: Optional[float] = None
    ghiradiation: Optional[float] = None
    dniradiation: Optional[float] = None
    difradiation: Optional[float] = None
    sunelevation: Optional[float] = None

class WeatherForecastIn(WeatherForecastBase):
    location_id: int

class ForecastEntry(WeatherForecastBase):
    pass

# Define the response model for the RL Agent State
class RLAgentStateData(BaseModel):
    timestamp: datetime
    forecasts: Optional[List[ForecastEntry]] = None

    # Price related fields
    raw_price_eur_mwh: Optional[float] = None
    calculated_price_eur_mwh: Optional[float] = None
    calculated_feed_in_eur_mwh: Optional[float] = None

    # PV related fields
    pv_generation_kwh: Optional[float] = None

    # Load related fields
    load_consumption_kwh: Optional[float] = None

    # Weather Observation fields
    obs_temp: Optional[float] = None
    obs_tempmin: Optional[float] = None
    obs_tempmax: Optional[float] = None
    obs_feelslike: Optional[float] = None
    obs_feelslikemax: Optional[float] = None
    obs_feelslikemin: Optional[float] = None
    obs_humidity: Optional[float] = None
    obs_dew: Optional[float] = None
    obs_precip: Optional[float] = None
    obs_precipprob: Optional[float] = None
    obs_precipcover: Optional[float] = None
    obs_snow: Optional[float] = None
    obs_snowdepth: Optional[float] = None
    obs_windgust: Optional[float] = None
    obs_windspeed: Optional[float] = None
    obs_winddir: Optional[float] = None
    obs_pressure: Optional[float] = None
    obs_cloudcover: Optional[float] = None
    obs_visibility: Optional[float] = None
    obs_solarradiation: Optional[float] = None
    obs_solarenergy: Optional[float] = None
    obs_uvindex: Optional[float] = None
    obs_severerisk: Optional[float] = None
    obs_windspeedmax: Optional[float] = None
    obs_windspeedmean: Optional[float] = None
    obs_windspeedmin: Optional[float] = None
    obs_sunrise: Optional[str] = None
    obs_sunset: Optional[str] = None
    obs_moonphase: Optional[float] = None
    obs_conditions: Optional[str] = None
    obs_windspeed50: Optional[float] = None
    obs_winddir50: Optional[float] = None
    obs_windspeed80: Optional[float] = None
    obs_winddir80: Optional[float] = None
    obs_windspeed100: Optional[float] = None
    obs_winddir100: Optional[float] = None
    obs_ghiradiation: Optional[float] = None
    obs_dniradiation: Optional[float] = None
    obs_difradiation: Optional[float] = None
    obs_sunelevation: Optional[float] = None
from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional

# Ingest payload models
class WeatherObservationIn(BaseModel):
    datetime:        datetime
    location_id:     int
    tempmax:         Optional[float]    = None
    tempmin:         Optional[float]    = None
    temp:            Optional[float]    = None
    humidity:        Optional[float]    = None
    feelslikemax:    Optional[float]    = None
    feelslikemin:    Optional[float]    = None
    feelslike:       Optional[float]    = None
    dew:             Optional[float]    = None
    precip:          Optional[float]    = None
    precipprob:      Optional[float]    = None
    precipcover:     Optional[float]    = None
    preciptype:      Optional[List[str]] = None
    snow:            Optional[float]    = None
    snowdepth:       Optional[float]    = None
    windgust:        Optional[float]    = None
    windspeed:       Optional[float]    = None
    winddir:         Optional[float]    = None
    pressure:        Optional[float]    = None
    cloudcover:      Optional[float]    = None
    visibility:      Optional[float]    = None
    solarradiation:  Optional[float]    = None
    solarenergy:     Optional[float]    = None
    uvindex:         Optional[float]    = None
    severerisk:      Optional[float]    = None
    windspeedmax:    Optional[float]    = None
    windspeedmean:   Optional[float]    = None
    windspeedmin:    Optional[float]    = None
    sunrise:         Optional[str]      = None
    sunset:          Optional[str]      = None
    moonphase:       Optional[float]    = None
    conditions:      Optional[str]      = None
    description:     Optional[str]      = None
    icon:            Optional[str]      = None
    source:          Optional[str]      = None
    windspeed50:     Optional[float]    = None
    winddir50:       Optional[float]    = None
    windspeed80:     Optional[float]    = None
    winddir80:       Optional[float]    = None
    windspeed100:    Optional[float]    = None
    winddir100:      Optional[float]    = None
    ghiradiation:    Optional[float]    = None
    dniradiation:    Optional[float]    = None
    difradiation:    Optional[float]    = None
    gtiradiation:    Optional[float]    = None
    sunelevation:    Optional[float]    = None

class BulkWeatherObs(BaseModel):
    data: List[WeatherObservationIn] = Field(...)

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

class PriceIn(BaseModel):
    time: datetime
    region_id: int
    price_eur_mwh: float

class BulkPrice(BaseModel):
    data: List[PriceIn] = Field(...)

class RegionIn(BaseModel):
    region_id: Optional[int] = None
    name:      str

class LocationIn(BaseModel):
    location_id: Optional[int] = None
    region_id:   int
    name:        str
    latitude:    float
    longitude:   float

class HouseholdIn(BaseModel):
    household_id: Optional[int] = None
    location_id:  int

class WeatherForecastIn(BaseModel):
    forecast_run:   datetime
    target_time:    datetime
    location_id:    int
    tempmax:        Optional[float]    = None
    tempmin:        Optional[float]    = None
    temp:           Optional[float]    = None
    feelslikemax:   Optional[float]    = None
    feelslikemin:   Optional[float]    = None
    feelslike:      Optional[float]    = None
    dew:            Optional[float]    = None
    humidity:       Optional[float]    = None
    precip:         Optional[float]    = None
    precipprob:     Optional[float]    = None
    precipcover:    Optional[float]    = None
    preciptype:     Optional[List[str]] = None
    snow:           Optional[float]    = None
    snowdepth:      Optional[float]    = None
    windgust:       Optional[float]    = None
    windspeed:      Optional[float]    = None
    winddir:        Optional[float]    = None
    pressure:       Optional[float]    = None
    cloudcover:     Optional[float]    = None
    visibility:     Optional[float]    = None
    solarradiation: Optional[float]    = None
    solarenergy:    Optional[float]    = None
    uvindex:        Optional[float]    = None
    severerisk:     Optional[float]    = None
    windspeedmax:   Optional[float]    = None
    windspeedmean:  Optional[float]    = None
    windspeedmin:   Optional[float]    = None
    sunrise:        Optional[str]      = None
    sunset:         Optional[str]      = None
    moonphase:      Optional[float]    = None
    conditions:     Optional[str]      = None
    description:    Optional[str]      = None
    icon:           Optional[str]      = None
    source:         Optional[str]      = None
    windspeed50:    Optional[float]    = None
    winddir50:      Optional[float]    = None
    windspeed80:    Optional[float]    = None
    winddir80:      Optional[float]    = None
    windspeed100:   Optional[float]    = None
    winddir100:     Optional[float]    = None
    ghiradiation:   Optional[float]    = None
    dniradiation:   Optional[float]    = None
    difradiation:   Optional[float]    = None
    gtiradiation:   Optional[float]    = None
    sunelevation:   Optional[float]    = None

class BulkWeatherForecast(BaseModel):
    data: List[WeatherForecastIn] = Field(...)

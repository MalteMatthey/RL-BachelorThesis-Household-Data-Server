-- 0) enable TimescaleDB
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- 1) Regions (for price assignment)
CREATE TABLE regions (
    region_id   SERIAL           PRIMARY KEY,
    name        TEXT             NOT NULL
);

-- 2) Locations with geographic coordinates
CREATE TABLE locations (
    location_id SERIAL           PRIMARY KEY,
    region_id   INT              NOT NULL REFERENCES regions(region_id),
    name        TEXT             NOT NULL,
    latitude    DOUBLE PRECISION NOT NULL,
    longitude   DOUBLE PRECISION NOT NULL
);

-- 3) Households in a location
CREATE TABLE households (
    household_id SERIAL           PRIMARY KEY,
    location_id  INT              NOT NULL REFERENCES locations(location_id)
);

-- 4) Raw prices per region
CREATE TABLE electricity_prices (
    time           TIMESTAMPTZ      NOT NULL,
    region_id      INT              NOT NULL REFERENCES regions(region_id),
    price_eur_mwh  DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (time, region_id)
);
SELECT create_hypertable(
    'electricity_prices', 'time',
    partitioning_column => 'region_id',
    number_partitions     => 8,
    chunk_time_interval => INTERVAL '1 month'
);

-- 5) Weather observations per location
CREATE TABLE weather_observations (
    datetime         TIMESTAMPTZ      NOT NULL,    
    location_id      INT              NOT NULL REFERENCES locations(location_id),
    tempmax          DOUBLE PRECISION,               
    tempmin          DOUBLE PRECISION,               
    temp             DOUBLE PRECISION,               
    feelslikemax     DOUBLE PRECISION,
    feelslikemin     DOUBLE PRECISION,
    feelslike        DOUBLE PRECISION,
    dew              DOUBLE PRECISION,
    humidity         DOUBLE PRECISION,
    precip           DOUBLE PRECISION,
    precipprob       DOUBLE PRECISION,
    precipcover      DOUBLE PRECISION,
    preciptype       TEXT[],
    snow             DOUBLE PRECISION,
    snowdepth        DOUBLE PRECISION,
    windgust         DOUBLE PRECISION,
    windspeed        DOUBLE PRECISION,
    winddir          DOUBLE PRECISION,
    pressure         DOUBLE PRECISION,
    cloudcover       DOUBLE PRECISION,
    visibility       DOUBLE PRECISION,
    solarradiation   DOUBLE PRECISION,
    solarenergy      DOUBLE PRECISION,
    uvindex          DOUBLE PRECISION,
    severerisk       DOUBLE PRECISION,
    windspeedmax     DOUBLE PRECISION,
    windspeedmean    DOUBLE PRECISION,
    windspeedmin     DOUBLE PRECISION,
    sunrise          TEXT,
    sunset           TEXT,
    moonphase        DOUBLE PRECISION,
    conditions       TEXT,
    description      TEXT,
    icon             TEXT,
    source           TEXT,
    windspeed50      DOUBLE PRECISION,
    winddir50        DOUBLE PRECISION,
    windspeed80      DOUBLE PRECISION,
    winddir80        DOUBLE PRECISION,
    windspeed100     DOUBLE PRECISION,
    winddir100       DOUBLE PRECISION,
    ghiradiation     DOUBLE PRECISION,
    dniradiation     DOUBLE PRECISION,
    difradiation     DOUBLE PRECISION,
    gtiradiation     DOUBLE PRECISION,
    sunelevation     DOUBLE PRECISION,
    PRIMARY KEY (datetime, location_id)
);
SELECT create_hypertable(
    'weather_observations', 'datetime',
    partitioning_column => 'location_id',
    number_partitions     => 8,
    chunk_time_interval => INTERVAL '1 day'
);

-- 6) Weather forecasts per location
CREATE TABLE weather_forecasts (
    forecast_run    TIMESTAMPTZ      NOT NULL,
    target_time     TIMESTAMPTZ      NOT NULL,
    location_id     INT              NOT NULL REFERENCES locations(location_id),
    tempmax          DOUBLE PRECISION,
    tempmin          DOUBLE PRECISION,
    temp             DOUBLE PRECISION,
    feelslikemax     DOUBLE PRECISION,
    feelslikemin     DOUBLE PRECISION,
    feelslike        DOUBLE PRECISION,
    dew              DOUBLE PRECISION,
    humidity         DOUBLE PRECISION,
    precip           DOUBLE PRECISION,
    precipprob       DOUBLE PRECISION,
    precipcover      DOUBLE PRECISION,
    preciptype       TEXT[],
    snow             DOUBLE PRECISION,
    snowdepth        DOUBLE PRECISION,
    windgust         DOUBLE PRECISION,
    windspeed        DOUBLE PRECISION,
    winddir          DOUBLE PRECISION,
    pressure         DOUBLE PRECISION,
    cloudcover       DOUBLE PRECISION,
    visibility       DOUBLE PRECISION,
    solarradiation   DOUBLE PRECISION,
    solarenergy      DOUBLE PRECISION,
    uvindex          DOUBLE PRECISION,
    severerisk       DOUBLE PRECISION,
    windspeedmax     DOUBLE PRECISION,
    windspeedmean    DOUBLE PRECISION,
    windspeedmin     DOUBLE PRECISION,
    sunrise          TEXT,
    sunset           TEXT,
    moonphase        DOUBLE PRECISION,
    conditions       TEXT,
    description      TEXT,
    icon             TEXT,
    source           TEXT,
    windspeed50      DOUBLE PRECISION,
    winddir50        DOUBLE PRECISION,
    windspeed80      DOUBLE PRECISION,
    winddir80        DOUBLE PRECISION,
    windspeed100     DOUBLE PRECISION,
    winddir100       DOUBLE PRECISION,
    ghiradiation     DOUBLE PRECISION,
    dniradiation     DOUBLE PRECISION,
    difradiation     DOUBLE PRECISION,
    gtiradiation     DOUBLE PRECISION,
    sunelevation     DOUBLE PRECISION,
    PRIMARY KEY (forecast_run, target_time, location_id)
);
SELECT create_hypertable(
    'weather_forecasts', 'target_time',
    partitioning_column => 'location_id',
    number_partitions     => 8,
    chunk_time_interval => INTERVAL '1 day'
);

-- 7) PV generation per household
CREATE TABLE pv_generation (
    time             TIMESTAMPTZ      NOT NULL,
    household_id     INT              NOT NULL REFERENCES households(household_id),
    generation_kwh   DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (time, household_id)
);
SELECT create_hypertable(
    'pv_generation', 'time',
    partitioning_column => 'household_id',
    number_partitions     => 8,
    chunk_time_interval => INTERVAL '1 day'
);

-- 8) Load data per household
CREATE TABLE load_data (
    time             TIMESTAMPTZ      NOT NULL,
    household_id     INT              NOT NULL REFERENCES households(household_id),
    consumption_kwh  DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (time, household_id)
);
SELECT create_hypertable(
    'load_data', 'time',
    partitioning_column => 'household_id',
    number_partitions     => 8,
    chunk_time_interval => INTERVAL '1 day'
);

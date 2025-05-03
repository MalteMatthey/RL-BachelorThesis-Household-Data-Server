-- 1) Minute-wise prices per region (gap-filled from hourly prices)
CREATE MATERIALIZED VIEW price_1min
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 minute', time) AS time,
    region_id,
    last(price_eur_mwh, time)            AS price_eur_mwh
FROM electricity_prices
GROUP BY region_id, time_bucket('1 minute', time);

-- 2) PV per household 1‑min (gap-filled)
CREATE MATERIALIZED VIEW pv_1min
WITH (timescaledb.continuous) AS
SELECT
  time_bucket('1 minute', time) AS time,
  household_id,
  last(generation_kwh, time) AS pv_kwh
FROM pv_generation
GROUP BY household_id, time_bucket('1 minute', time);

-- 3) Load per household 1‑min (gap-filled)
CREATE MATERIALIZED VIEW load_1min
WITH (timescaledb.continuous) AS
SELECT
  time_bucket('1 minute', time) AS time,
  household_id,
  last(consumption_kwh, time) AS load_kwh
FROM load_data
GROUP BY household_id, time_bucket('1 minute', time);

-- 4) Minute-wise weather observations per location (gap-filled)
CREATE MATERIALIZED VIEW weather_obs_1min
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 minute', datetime) AS time,
    location_id,
    last(tempmax,          datetime) AS tempmax,
    last(tempmin,          datetime) AS tempmin,
    last(temp,             datetime) AS temp,
    last(feelslikemax,     datetime) AS feelslikemax,
    last(feelslikemin,     datetime) AS feelslikemin,
    last(feelslike,        datetime) AS feelslike,
    last(dew,              datetime) AS dew,
    last(humidity,         datetime) AS humidity,
    last(precip,           datetime) AS precip,
    last(precipprob,       datetime) AS precipprob,
    last(precipcover,      datetime) AS precipcover,
    last(preciptype,       datetime) AS preciptype,
    last(snow,             datetime) AS snow,
    last(snowdepth,        datetime) AS snowdepth,
    last(windgust,         datetime) AS windgust,
    last(windspeed,        datetime) AS windspeed,
    last(winddir,          datetime) AS winddir,
    last(pressure,         datetime) AS pressure,
    last(cloudcover,       datetime) AS cloudcover,
    last(visibility,       datetime) AS visibility,
    last(solarradiation,   datetime) AS solarradiation,
    last(solarenergy,      datetime) AS solarenergy,
    last(uvindex,          datetime) AS uvindex,
    last(severerisk,       datetime) AS severerisk,
    last(windspeedmax,     datetime) AS windspeedmax,
    last(windspeedmean,    datetime) AS windspeedmean,
    last(windspeedmin,     datetime) AS windspeedmin,
    last(sunrise,          datetime) AS sunrise,
    last(sunset,           datetime) AS sunset,
    last(moonphase,        datetime) AS moonphase,
    last(conditions,       datetime) AS conditions,
    last(description,      datetime) AS description,
    last(icon,             datetime) AS icon,
    last(source,           datetime) AS source,
    last(windspeed50,      datetime) AS windspeed50,
    last(winddir50,        datetime) AS winddir50,
    last(windspeed80,      datetime) AS windspeed80,
    last(winddir80,        datetime) AS winddir80,
    last(windspeed100,     datetime) AS windspeed100,
    last(winddir100,       datetime) AS winddir100,
    last(ghiradiation,     datetime) AS ghiradiation,
    last(dniradiation,     datetime) AS dniradiation,
    last(difradiation,     datetime) AS difradiation,
    last(gtiradiation,     datetime) AS gtiradiation,
    last(sunelevation,     datetime) AS sunelevation
FROM weather_observations
GROUP BY location_id, time_bucket('1 minute', datetime);

-- 5) Minute-wise weather forecasts per location (gap-filled)
CREATE MATERIALIZED VIEW weather_fcst_1min
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 minute', target_time)   AS time,
    location_id,
    last(target_time,     target_time)     AS target_time,
    last(forecast_run,    target_time)     AS forecast_run,
    last(tempmax,         target_time)     AS tempmax,
    last(tempmin,         target_time)     AS tempmin,
    last(temp,            target_time)     AS temp,
    last(feelslikemax,    target_time)     AS feelslikemax,
    last(feelslikemin,    target_time)     AS feelslikemin,
    last(feelslike,       target_time)     AS feelslike,
    last(dew,             target_time)     AS dew,
    last(humidity,        target_time)     AS humidity,
    last(precip,          target_time)     AS precip,
    last(precipprob,      target_time)     AS precipprob,
    last(precipcover,     target_time)     AS precipcover,
    last(preciptype,      target_time)     AS preciptype,
    last(snow,            target_time)     AS snow,
    last(snowdepth,       target_time)     AS snowdepth,
    last(windgust,        target_time)     AS windgust,
    last(windspeed,       target_time)     AS windspeed,
    last(winddir,         target_time)     AS winddir,
    last(pressure,        target_time)     AS pressure,
    last(cloudcover,      target_time)     AS cloudcover,
    last(visibility,      target_time)     AS visibility,
    last(solarradiation,  target_time)     AS solarradiation,
    last(solarenergy,     target_time)     AS solarenergy,
    last(uvindex,         target_time)     AS uvindex,
    last(severerisk,      target_time)     AS severerisk,
    last(windspeedmax,    target_time)     AS windspeedmax,
    last(windspeedmean,   target_time)     AS windspeedmean,
    last(windspeedmin,    target_time)     AS windspeedmin,
    last(sunrise,         target_time)     AS sunrise,
    last(sunset,          target_time)     AS sunset,
    last(moonphase,       target_time)     AS moonphase,
    last(conditions,      target_time)     AS conditions,
    last(description,     target_time)     AS description,
    last(icon,            target_time)     AS icon,
    last(source,          target_time)     AS source,
    last(windspeed50,     target_time)     AS windspeed50,
    last(winddir50,       target_time)     AS winddir50,
    last(windspeed80,     target_time)     AS windspeed80,
    last(winddir80,       target_time)     AS winddir80,
    last(windspeed100,    target_time)     AS windspeed100,
    last(winddir100,      target_time)     AS winddir100,
    last(ghiradiation,    target_time)     AS ghiradiation,
    last(dniradiation,    target_time)     AS dniradiation,
    last(difradiation,    target_time)     AS difradiation,
    last(gtiradiation,    target_time)     AS gtiradiation,
    last(sunelevation,    target_time)     AS sunelevation
FROM weather_forecasts
GROUP BY location_id, time_bucket('1 minute', target_time);

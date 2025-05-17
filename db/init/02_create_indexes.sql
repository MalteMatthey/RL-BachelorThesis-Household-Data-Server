-- 1) Foreign key indexes for faster joins and filters
CREATE INDEX idx_locations_price_region_id          ON locations(price_region_id);
CREATE INDEX idx_households_location_id             ON households(location_id);
CREATE INDEX idx_weather_observations_location_id   ON weather_observations(location_id);
CREATE INDEX idx_weather_forecasts_location_id      ON weather_forecasts(location_id);
CREATE INDEX idx_pv_generation_household_id         ON pv_generation(household_id);
CREATE INDEX idx_load_data_household_id             ON load_data(household_id);

-- For electricity_prices LOCF
CREATE INDEX IF NOT EXISTS idx_electricity_prices_region_id_time_desc
ON electricity_prices (price_region_id, time DESC);

-- For pv_generation LOCF
CREATE INDEX IF NOT EXISTS idx_pv_generation_household_id_time_desc
ON pv_generation (household_id, time DESC);

-- For load_data LOCF
CREATE INDEX IF NOT EXISTS idx_load_data_household_id_time_desc
ON load_data (household_id, time DESC);

-- For weather_observations LOCF
CREATE INDEX IF NOT EXISTS idx_weather_observations_location_id_datetime_desc
ON weather_observations (location_id, datetime DESC);

-- For weather_forecasts
CREATE INDEX IF NOT EXISTS idx_weather_forecasts_loc_id_fc_run_desc
ON weather_forecasts (location_id, forecast_run DESC);
CREATE INDEX IF NOT EXISTS idx_weather_forecasts_loc_id_fc_run_target_time
ON weather_forecasts (location_id, forecast_run, target_time ASC);
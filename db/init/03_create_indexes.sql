-- 1) Foreign key indexes for faster joins and filters
CREATE INDEX idx_locations_region_id                 ON locations(region_id);
CREATE INDEX idx_households_location_id              ON households(location_id);
CREATE INDEX idx_weather_observations_location_id    ON weather_observations(location_id);
CREATE INDEX idx_weather_forecasts_location_id       ON weather_forecasts(location_id);
CREATE INDEX idx_pv_generation_household_id     ON pv_generation(household_id);
CREATE INDEX idx_load_data_household_id         ON load_data(household_id);

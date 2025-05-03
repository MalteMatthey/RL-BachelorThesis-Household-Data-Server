-- Grant usage on the schema to the user
GRANT USAGE ON SCHEMA public TO test_user;

-- Grant SELECT privilege on all tables and views in the public schema to the user
GRANT SELECT ON ALL TABLES IN SCHEMA public TO test_user;

-- Grant SELECT privilege on the specific materialized views
GRANT SELECT ON price_1min TO test_user;
GRANT SELECT ON pv_1min TO test_user;
GRANT SELECT ON load_1min TO test_user;
GRANT SELECT ON weather_obs_1min TO test_user;
GRANT SELECT ON weather_fcst_1min TO test_user;

-- Grant SELECT privilege on all sequences (if needed, though likely not for reflection)
-- GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO test_user;

-- IMPORTANT for future tables/views created by postgres user:
-- Alter default privileges so test_user automatically gets SELECT on new tables/views
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO test_user;
-- Also grant execute on future functions/procedures (if any are created)
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT EXECUTE ON ROUTINES TO test_user;
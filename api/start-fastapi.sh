#!/bin/sh
set -e

echo "Starting FastAPI application..."

# Wait until all required materialized views are queryable
#until PGPASSWORD="$POSTGRES_PASSWORD" psql -h db -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "SELECT 1 FROM public.price_1min LIMIT 1;" > /dev/null 2>&1 && \
#      PGPASSWORD="$POSTGRES_PASSWORD" psql -h db -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "SELECT 1 FROM public.pv_1min LIMIT 1;" > /dev/null 2>&1 && \
#      PGPASSWORD="$POSTGRES_PASSWORD" psql -h db -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "SELECT 1 FROM public.load_1min LIMIT 1;" > /dev/null 2>&1 && \
#      PGPASSWORD="$POSTGRES_PASSWORD" psql -h db -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "SELECT 1 FROM public.weather_obs_1min LIMIT 1;" > /dev/null 2>&1 && \
#      PGPASSWORD="$POSTGRES_PASSWORD" psql -h db -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "SELECT 1 FROM public.weather_fcst_1min LIMIT 1;" > /dev/null 2>&1; do
#  echo "Waiting for all materialized views to be queryable..."
#  sleep 2
#done

#echo "All Materialized views are ready. Starting Uvicorn..."

exec uvicorn api.main:app --host 0.0.0.0 --port 8021
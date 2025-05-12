# Household Data API

This project provides a FastAPI-based API for ingesting, processing, and retrieving time series data related to weather, PV generation, load, and electricity prices. It leverages TimescaleDB for efficient storage and querying of time-based data, and Backblaze B2 for data backup.

## Key Features

-   **Data Ingestion:** API endpoints for ingesting bulk data for PV generation, load data, weather observations, weather forecasts, and electricity prices.
-   **Time Series Retrieval:** API endpoints for querying time series data based on various filters (e.g., region ID, household ID, location ID) and date ranges.
-   **Metadata Management:** API endpoints for managing metadata related to price regions, locations, and households.
-   **TimescaleDB:** Utilizes TimescaleDB for optimized storage and querying of time series data.
-   **API Key Authentication:** Protects API endpoints with API key authentication.
-   **Dockerized Deployment:** Includes a `docker-compose.yml` file for easy deployment using Docker.
-   **Automated Data Fetching:** Automatically fetches weather and electricity price data from external APIs (Visual Crossing and ENTSO-E) when relevant time series data is ingested.
-   **Data Backup:** Implements data backup to Backblaze B2 for API responses.

## Project Structure

-   `api/`: Contains the FastAPI application code.
    -   `__init__.py`: Initializes the api package.
    -   `db.py`: Handles database connection, schema reflection, and table definitions.
    -   `main.py`: Main application file with API setup, middleware, and database connection logic.
    -   `schemas.py`: Defines Pydantic models for request and response data validation and serialization.
    -   `routers/`: Contains API route handlers, each in its own file.
        -   `__init__.py`: Initializes the routers package.
        -   `ingest.py`: Defines routes for data ingestion, including PV generation, load data, weather data, and electricity prices.  Handles fetching external data on ingestion.
        -   `metadata.py`: Defines routes for managing metadata related to price regions, locations, and households.
        -   `timeseries.py`: Defines routes for time series data retrieval.
    -   `services/`: Contains service modules for specific tasks.
        -   `__init__.py`: Initializes the services package.
        -   `b2_backup.py`: Handles interaction with Backblaze B2 for data backup.
        -   `fetch_electricity_price_data.py`: Fetches electricity price data from the ENTSO-E API.
        -   `fetch_weather_data.py`: Fetches weather data from the Visual Crossing API.
-   `db/`: Contains Dockerfile and SQL scripts for initializing the database.
    -   `Dockerfile`: Defines the Docker image for the TimescaleDB database.
    -   `init/`: Contains SQL scripts for initializing the database schema.
        -   `01_create_tables.sql`: Creates the database tables and hypertable configurations.
        -   `02_create_indexes.sql`: Creates indexes for faster queries.
-   `.env.example`: Example environment variable file.
-   `.gitignore`: Specifies intentionally untracked files that Git should ignore.
-   `Dockerfile`: Defines the Docker image for the FastAPI application.
-   `docker-compose.yml`: Defines the Docker Compose configuration for deploying the application, including the FastAPI app, TimescaleDB, and Cloudflare Tunnel.
-   `requirements.txt`: Lists the Python dependencies.

## Getting Started

1.  **Clone the repository:**

    ```bash
    git clone <repository_url>
    cd <repository_directory>
    ```

2.  **Configure environment variables:**

    -   Create a `.env` file based on `.env.example` and fill in the required values (API key, database credentials, Visual Crossing API key, ENTSO-E API key, B2 credentials, etc.).
    -   Ensure a `stack.env` file exists with the same content as `.env` (required for local Docker Compose deployment).  This file is used by Docker Compose to set environment variables.

3.  **Run the application using Docker Compose:**

    ```bash
    docker-compose up --build
    ```

    This will build the Docker images and start the application along with the TimescaleDB database and Cloudflare Tunnel.

4.  **Access the API:**

    The API will be accessible through the Cloudflare Tunnel.  If running locally without the tunnel, it will be accessible at `http://localhost:8021`.

## API Endpoints

### Metadata

-   `POST /metadata/price_regions`: Create a new price region.
-   `GET /metadata/price_regions`: Retrieve a list of price regions, optionally filtered by name.
-   `GET /metadata/price_regions/{price_region_id}`: Retrieve a specific price region by ID.
-   `POST /metadata/locations`: Create a new location.
-   `GET /metadata/locations`: Retrieve a list of locations, optionally filtered by price region ID.
-   `GET /metadata/locations/{location_id}`: Retrieve a specific location by ID.
-   `POST /metadata/households`: Create a new household.
-   `GET /metadata/households`: Retrieve a list of households, optionally filtered by location ID.
-   `GET /metadata/households/{household_id}`: Retrieve a specific household by ID.

### Ingestion

-   `POST /ingest/pv_generation`: Ingest PV generation data.
-   `POST /ingest/load_data`: Ingest load data.

### Timeseries

-   `GET /timeseries/price`: Retrieve electricity price data.
-   `GET /timeseries/pv`: Retrieve PV generation data.
-   `GET /timeseries/load`: Retrieve load data.
-   `GET /timeseries/weather_obs`: Retrieve weather observation data.
   -  Requires `location_id`, `start`, and `end` query parameters.
-   `GET /timeseries/weather_fcst`: Retrieve weather forecast data.
    - Requires `location_id`, `start`, and `end` query parameters.

See the `api/routers` directory for more details on request parameters and response formats.

## Authentication

All API endpoints are protected by API key authentication. You must include the `X-API-Key` header in your requests with the correct API key value, which is set via the `API_KEY` environment variable.

## TimescaleDB Initialization

The database schema is automatically created and configured when the TimescaleDB container starts. The SQL scripts in the `db/init` directory are executed to create the tables, configure TimescaleDB, and create indexes.

## Environment Variables

The following environment variables must be configured:

-   `API_KEY`: API key for authentication.
-   `POSTGRES_USER`: PostgreSQL user.
-   `POSTGRES_PASSWORD`: PostgreSQL password.
-   `POSTGRES_DB`: PostgreSQL database name.
-   `DATABASE_URL`: PostgreSQL connection string (e.g., `postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}`).
-   `VISUAL_CROSSING_API_KEY`: API key for the Visual Crossing weather API.
-   `ENTSOE_API_KEY`: API key for the ENTSO-E transparency platform API.
-   `B2_KEY_ID`: Backblaze B2 key ID.
-   `B2_APPLICATION_KEY`: Backblaze B2 application key.
-   `B2_BUCKET_NAME`: Backblaze B2 bucket name.
-   `TUNNEL_TOKEN`: Cloudflare Tunnel Token.

Ensure these variables are set in both `.env` and `stack.env`.
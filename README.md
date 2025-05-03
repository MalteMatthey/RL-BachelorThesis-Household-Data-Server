# Household Database and API

**AI GENERATED PLACEHOLDER, REPLACE WITH COMPLETE README TBD.**

This project provides a FastAPI-based API for ingesting and retrieving time series data related to weather, PV generation, load, and electricity prices. It uses TimescaleDB for efficient storage and querying of time-based data.

## Key Features

-   **Data Ingestion:** API endpoints for ingesting bulk data for weather observations, weather forecasts, PV generation, load data, and electricity prices.
-   **Time Series Retrieval:** API endpoints for querying time series data based on various filters (e.g., region ID, household ID, location ID) and date ranges.
-   **TimescaleDB:** Utilizes TimescaleDB for optimized storage and querying of time series data.
-   **API Key Authentication:** Protects API endpoints with API key authentication.
-   **Dockerized Deployment:** Includes a `docker-compose.yml` file for easy deployment using Docker.

## Project Structure

-   `api/`: Contains the FastAPI application code.
    -   `db.py`: Handles database connection and schema reflection.
    -   `main.py`: Main application file with API setup and middleware.
    -   `schemas.py`: Defines Pydantic models for request and response data.
    -   `routers/`: Contains API route handlers.
        -   `ingest.py`: Defines routes for data ingestion.
        -   `timeseries.py`: Defines routes for time series data retrieval.
-   `db/init/`: Contains SQL scripts for initializing the database schema.
    -   `01_create_tables.sql`: Creates the database tables and hypertable configurations.
    -   `02_create_indexes.sql`: Creates indexes for faster queries.
-   `.env.example`: Example environment variable file.
-   `Dockerfile`: Defines the Docker image for the application.
-   `docker-compose.yml`: Defines the Docker Compose configuration for deploying the application.
-   `requirements.txt`: Lists the Python dependencies.

## Getting Started

1.  **Clone the repository:**

    ```bash
    git clone <repository_url>
    cd <repository_directory>
    ```

2.  **Configure environment variables:**

    -   Create a `.env` file based on `.env.example` and fill in the required values (API key, database credentials, etc.).
    -   Ensure a `stack.env` file exists with the same content as `.env` (required for local Docker Compose deployment).

3.  **Run the application using Docker Compose:**

    ```bash
    docker-compose up --build
    ```

    This will build the Docker image and start the application along with the TimescaleDB database.

4.  **Access the API:**

    The API will be accessible at `http://localhost:8021`.

## API Endpoints

### Ingestion

-   `POST /ingest/weather_observations`: Ingest weather observation data.
-   `POST /ingest/weather_forecasts`: Ingest weather forecast data.
-   `POST /ingest/pv_generation`: Ingest PV generation data.
-   `POST /ingest/load_data`: Ingest load data.
-   `POST /ingest/electricity_prices`: Ingest electricity price data.

### Time Series Retrieval

-   `GET /timeseries/price`: Retrieve electricity price data.
-   `GET /timeseries/pv`: Retrieve PV generation data.
-   `GET /timeseries/load`: Retrieve load data.
-   `GET /timeseries/weather_obs`: Retrieve weather observation data.
-   `GET /timeseries/weather_fcst`: Retrieve weather forecast data.

See the `api/routers` directory for more details on request parameters and response formats.

## Authentication

All API endpoints are protected by API key authentication. You must include the `X-API-Key` header in your requests with the correct API key value.

## TimescaleDB Initialization

The database schema is automatically created and configured when the TimescaleDB container starts. The SQL scripts in the `db/init` directory are executed to create the tables and hypertables.
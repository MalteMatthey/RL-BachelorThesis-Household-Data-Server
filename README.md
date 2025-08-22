# Household Data API

The Household Data API is a FastAPI service designed to ingest, store, and serve time-series data related to household energy consumption and generation. It provides a backend for energy management systems, reinforcement learning agents, and data analysis tasks. The system is containerized using Docker and includes a TimescaleDB database for time-series data, a CI/CD pipeline for automated testing, and features like PV simulation and synthetic weather forecast generation.

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Core Technologies](#core-technologies)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Configuration](#configuration)
  - [Running the Application](#running-the-application)
  - [Resetting the Environment](#resetting-the-environment)
- [API Endpoints](#api-endpoints)
  - [Authentication](#authentication)
  - [API Documentation](#api-documentation)
- [Database Schema](#database-schema)
- [Testing](#testing)
- [CI/CD Pipeline](#cicd-pipeline)

## Features

- **Time-Series Data Management**: Ingest and retrieve household load, PV generation, weather data, and electricity prices.
- **Automated External Data Fetching**: Fetches required data from external services like **ENTSO-E** (for prices), **Visual Crossing** (for weather), and **Copernicus CAMS** (for solar irradiation).
- **PV Simulation**: Simulates PV generation using `pvlib`, accounting for geographic location, panel orientation, system specifications, and weather conditions, including temperature and snow coverage.
- **Synthetic Weather Forecast Generation**: For historical periods where real forecasts are unavailable (pre-2020), the system generates statistically realistic forecasts by learning the error patterns from a known period.
- **Reinforcement Learning Ready**: An endpoint provides a time-aligned state vector suitable for training RL agents for energy optimization tasks.
- **External API Caching**: Caches responses from external APIs to a **Backblaze B2** bucket to reduce costs, improve speed, and handle external service downtime.
- **Containerized & Deployable**: The application is containerized with Docker and Docker Compose for a consistent setup.
- **Automated CI/CD**: Includes a GitLab CI pipeline for automated testing, creation of merge requests, and branch synchronization.

## Architecture

The application uses a service-oriented architecture, containerized for portability.

1.  **FastAPI Application**: The core of the service, providing the RESTful API endpoints. It handles business logic, data validation (via Pydantic), and coordination between the database and external services.
2.  **TimescaleDB Database**: A PostgreSQL database with the TimescaleDB extension for efficient storage and querying of time-series data. All time-series tables are configured as hypertables.
3.  **Uvicorn ASGI Server**: An ASGI server that runs the FastAPI application.
4.  **Cloudflare Tunnel (Optional)**: The `docker-compose.yml` includes a `cloudflared` service to expose the API to the internet without opening firewall ports.
5.  **Docker & Docker Compose**: The entire stack is defined in `Dockerfile` and `docker-compose.yml`, which creates a consistent environment for development, testing, and production.

## Core Technologies

- **Backend**: FastAPI, Uvicorn, SQLAlchemy
- **Database**: PostgreSQL, TimescaleDB
- **Data Science & Simulation**: pandas, pvlib, LightGBM, scikit-learn
- **External APIs**: ENTSO-E, Copernicus CDS, Visual Crossing
- **Caching**: Backblaze B2
- **DevOps**: Docker, Docker Compose, GitLab CI
- **Testing**: Pytest, pytest-asyncio

## Getting Started

### Prerequisites

- Docker
- Docker Compose

### Configuration

1.  **Environment File**: Create a `stack.env` file in the project root. You can copy the structure from `.env.example`:
    ```bash
    cp .env.example stack.env
    ```

2.  **Fill in Credentials**: Edit `stack.env` and provide the necessary API keys and credentials.

    ```env
    # Your internal API key to secure the endpoints
    API_KEY=YOUR_INTERNAL_API_KEY

    # TimescaleDB settings
    POSTGRES_USER=your_db_user
    POSTGRES_PASSWORD=your_db_password
    POSTGRES_DB=your_db_name
    DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}

    # External Service API Keys
    VISUAL_CROSSING_API_KEY=YOUR_VISUAL_CROSSING_KEY
    ENTSOE_API_KEY=YOUR_ENTSOE_KEY
    CDS_API_KEY=YOUR_CDSAPI_UID:YOUR_CDSAPI_KEY

    # Backblaze B2 Backup Bucket Settings
    B2_KEY_ID=YOUR_B2_KEY_ID
    B2_APPLICATION_KEY=YOUR_B2_APPLICATION_KEY
    B2_BUCKET_NAME=your-b2-bucket-name

    # Cloudflare Tunnel (optional)
    TUNNEL_TOKEN=YOUR_CLOUDFLARE_TUNNEL_TOKEN
    ```

### Running the Application

1.  **Build the containers**:
    ```bash
    docker compose build
    ```

2.  **Start the services**:
    ```bash
    docker compose up -d
    ```

The API will be available at `http://localhost:8021`.

### Resetting the Environment

To stop the application and completely remove the database, you can use the `docker compose down` command with the `-v` flag.

```bash
docker compose down -v
```

-   `docker compose down`: This command stops and removes the containers defined in the `docker-compose.yml` file (e.g., `fastapi`, `db`).
-   `-v` (or `--volumes`): This flag instructs Docker Compose to also remove the named volumes associated with the services. In this project, the `db` service uses a named volume called `db_data` to persist the PostgreSQL database files.

> **Warning:** Running this command will **permanently delete all data** in your database, including all price regions, locations, households, and their associated time-series data. This action is irreversible. It is useful when you want to start with a completely fresh, empty database.

## API Endpoints

### Authentication

All API endpoints are protected and require an API key to be passed in the `X-API-Key` header of each request.

### API Documentation

Once the application is running, interactive API documentation (Swagger UI) is available at:

**`http://localhost:8021/docs`**

The available routers are:

-   `/metadata`: `POST`, `GET`, `DELETE` operations for managing `price_regions`, `locations`, and `households`. Deletions cascade to all associated time-series data.
-   `/ingest`: `POST` endpoints for `pv_generation` and `load_data`. This is the primary entry point for new data and triggers the fetching of external data.
-   `/timeseries`: `GET` endpoints for retrieving raw time-series data for `price`, `pv`, `load`, `weather_obs`, and `weather_fcst`.
-   `/rl_agent_state`: A `GET` endpoint for fetching a combined, time-aligned state for an RL agent.

## Database Schema

The database schema is defined in `db/init/`.

-   **Metadata Tables**:
    -   `price_regions`: Defines electricity bidding zones (e.g., DE-LU).
    -   `locations`: Stores geographic coordinates and assigns a location to a price region.
    -   `households`: Contains household-specific parameters, including PV system details and price formulas.
-   **Time-Series Hypertables**:
    -   `electricity_prices`: Stores regional day-ahead prices.
    -   `weather_observations`: Stores historical weather data per location.
    -   `weather_forecasts`: Stores historical weather forecasts per location.
    -   `pv_generation`: Stores PV generation data per household.
    -   `load_data`: Stores energy consumption data per household.

## Testing

The project includes an integration test suite using `pytest`. The tests are located in the `tests/` directory and are designed to run against a live, containerized instance of the application.

-   **Running Tests**: The tests are executed by the GitLab CI pipeline. To run them locally, you can `exec` into the running `fastapi` container and run `pytest`.

The test suite covers:
1.  **Metadata API**: Creation and retrieval of regions, locations, and households.
2.  **Ingest API**: Ingesting load and PV data, including the PV simulation workflow.
3.  **Timeseries API**: Verifying that ingested data can be correctly retrieved.
4.  **RL Agent State API**: Validating the data aggregation endpoint against expected JSON outputs.
5.  **Metadata Deletion API**: Ensuring that deleting a metadata entity correctly cascades and removes all associated time-series data.

## CI/CD Pipeline

The `.gitlab-ci.yml` file defines an automated pipeline with three main stages:

1.  **`test`**: Triggered on pushes to `dev`. It builds the full Docker environment, runs the entire `pytest` suite inside the containers, and archives test logs as artifacts.
2.  **`mr`**: On a successful `test` stage on the `dev` branch, this job automatically creates a Merge Request from `dev` to `main`.
3.  **`sync_main_to_dev`**: After a commit is merged to `main`, this job automatically merges `main` back into `dev` to keep the development branch up-to-date.
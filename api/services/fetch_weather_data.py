import os
import httpx
import json
from datetime import datetime, timedelta, timezone, date
from typing import List, Dict, Any, Tuple, Optional, Type

import pydantic

from ..schemas import WeatherObservationIn, WeatherForecastIn
from .b2_backup import b2_handler

# --- Configuration ---

# Environment variable for API key is best practice
API_KEY = os.getenv("VISUAL_CROSSING_API_KEY")
if not API_KEY:
    # Consider raising an error or providing a default for testing if appropriate
    print("Warning: VISUAL_CROSSING_API_KEY environment variable not set.")

BASE_URL = "https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/"

# Define all elements potentially available from the Visual Crossing API
_ALL_AVAILABLE_ELEMENTS = [
    # Time
    "datetimeEpoch",
    # Temperature
    "tempmax", "tempmin", "temp", "feelslikemax", "feelslikemin", "feelslike", "dew",
    # Precipitation
    "precip", "precipprob", "precipcover", "snow", "snowdepth",
    # Wind
    "windgust", "windspeed", "windspeedmax", "windspeedmean", "windspeedmin", "winddir",
    "windspeed50", "winddir50", "windspeed80", "winddir80", "windspeed100", "winddir100",
    # Atmospheric
    "pressure", "humidity", "cloudcover", "visibility",
    # Solar
    "solarradiation", "solarenergy", "uvindex", "ghiradiation", "dniradiation", "difradiation",
    "sunelevation", "sunrise", "sunset", "moonphase",
    # Conditions
    "severerisk", "conditions",
]

# Dynamically determine required elements based on Pydantic schemas
# Ensure 'datetimeEpoch' is always included as it's crucial for time mapping.
_OBSERVATION_SCHEMA_FIELDS = set(WeatherObservationIn.model_fields.keys())
_FORECAST_SCHEMA_FIELDS = set(WeatherForecastIn.model_fields.keys())
# Combine fields from both schemas and add datetimeEpoch
_REQUIRED_FIELDS = (_OBSERVATION_SCHEMA_FIELDS | _FORECAST_SCHEMA_FIELDS | {"datetimeEpoch"})

# Filter the available elements to only those present in our schemas or datetimeEpoch
# This prevents requesting unnecessary data.
ELEMENTS_TO_REQUEST = sorted([
    elem for elem in _ALL_AVAILABLE_ELEMENTS if elem in _REQUIRED_FIELDS
])

# --- Constants ---
_DEFAULT_TIMEOUT_SECONDS = 30.0
_FORECAST_TIMEOUT_SECONDS = 30.0
_OBSERVATION_TIMEOUT_SECONDS = 300.0  # Allow longer for potentially large historical pulls
_MIN_FORECAST_DATE = datetime(2020, 1, 1, tzinfo=timezone.utc)
_DATE_FORMAT = "%Y-%m-%d"
_API_UNIT_GROUP = "metric"
_API_CONTENT_TYPE = "json"
_API_INCLUDE_HOURS = "hours"


# --- Core API Interaction ---

async def _make_visual_crossing_request(
        url: str,
        params: Dict[str, Any],
        timeout: float = _DEFAULT_TIMEOUT_SECONDS
) -> Optional[Dict[str, Any]]:
    """
    Makes a GET request to the Visual Crossing API, checking B2 backup first.
    Handles common HTTP errors, saves successful responses to B2,
    and returns the parsed JSON response.

    Args:
        url: The API endpoint URL.
        params: Dictionary of query parameters for the request (excluding API key).
        timeout: Request timeout in seconds.

    Returns:
        The parsed JSON response as a dictionary, or None if an error occurs.
    """
    # --- Check B2 Backup First ---
    params_for_backup_check = params.copy()

    backup_filename = await b2_handler.check_backup(url, params_for_backup_check)
    if backup_filename:
        # Backup exists, try to download and parse it
        backup_data = await b2_handler.get_backup(backup_filename)
        if backup_data:
            print(f"Using cached response from B2 backup: {backup_filename}")
            return backup_data  # Return parsed data from backup
        else:
            print(f"Failed to retrieve or parse backup {backup_filename}. Proceeding with live API call.")

    # --- Proceed with Live API Call ---
    request_params = params.copy()
    # Ensure API key is included in the request parameters (not earlier to keep filenames for backup consistent)
    request_params["key"] = API_KEY

    async with httpx.AsyncClient() as client:
        try:
            # print(f"Making live API request to: {url} with params affecting request: {request_params}")
            response = await client.get(url, params=request_params, timeout=timeout)
            response.raise_for_status()  # Raises HTTPStatusError for 4xx/5xx responses

            # --- Save Successful Response to B2 ---
            # Use the original params (without API key) for saving
            await b2_handler.save_backup(url, params_for_backup_check, response.content)

            # Return parsed JSON from the live response
            return response.json()

        except httpx.RequestError as exc:
            print(f"Network error requesting {exc.request.url!r}: {exc}")
            return None
        except httpx.HTTPStatusError as exc:
            print(f"HTTP error {exc.response.status_code} for {exc.request.url!r}: {exc.response.text}")
            return None
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON from live API response for {url}: {e}")
            return None
        except Exception as e:
            print(f"An unexpected error occurred during API request/processing: {e}")
            return None


# --- Data Processing Helpers ---

def _get_schema_keys_to_process(
        schema_cls: Type[pydantic.BaseModel],
        exclude_keys: set[str]
) -> List[str]:
    """
    Gets the list of schema field keys, excluding specified ones.

    Args:
        schema_cls: The Pydantic schema class.
        exclude_keys: A set of keys to exclude from the result.

    Returns:
        A list of schema field keys to process.
    """
    return [
        k for k in schema_cls.model_fields.keys() if k not in exclude_keys
    ]


def _process_api_response_day_hour(
        api_data: Optional[Dict[str, Any]],
        location_id: int,
        base_record: Dict[str, Any],
        time_field_name: str,  # e.g., 'datetime' or 'target_time'
        schema_cls: Type[pydantic.BaseModel],
        exclude_keys: set[str]
) -> List[Dict[str, Any]]:
    """
    Processes the common day/hour structure from the Visual Crossing API response.

    Args:
        api_data: The raw JSON data from the API, or None.
        location_id: The location ID to add to each record.
        base_record: A dictionary with common fields (like location_id, forecast_run).
        time_field_name: The name of the field to store the calculated datetime.
        schema_cls: The Pydantic schema class to determine which fields to extract.
        exclude_keys: Schema keys already handled or not present in API data.

    Returns:
        A list of processed data records (dictionaries).
    """
    processed_records: List[Dict[str, Any]] = []
    if not api_data or 'days' not in api_data:
        print("API response is missing or does not contain 'days' data.")
        return []

    keys_to_extract = _get_schema_keys_to_process(schema_cls, exclude_keys)

    for day_data in api_data.get('days', []):
        day_datetime_str = day_data.get('datetime', 'Unknown Day')
        for hour_data in day_data.get('hours', []):
            # Start with a copy of the base record
            record = base_record.copy()

            # --- Time Handling (Crucial) ---
            epoch_timestamp = hour_data.get('datetimeEpoch')
            if epoch_timestamp is not None:
                try:
                    record[time_field_name] = datetime.fromtimestamp(epoch_timestamp, tz=timezone.utc)
                except (TypeError, ValueError):
                    print(
                        f"Warning: Invalid datetimeEpoch '{epoch_timestamp}' for an hour in day {day_datetime_str}. Skipping record.")
                    continue  # Skip record if timestamp is invalid
            else:
                print(f"Warning: Missing 'datetimeEpoch' for an hour in day {day_datetime_str}. Skipping record.")
                continue  # Skip record if time cannot be determined

            # --- Data Extraction ---
            # Prioritize hourly data, fall back to daily data for missing hourly values
            for key in keys_to_extract:
                value = hour_data.get(key)
                if value is None:
                    # Fallback only if hourly value is explicitly None
                    value = day_data.get(key)
                record[key] = value  # Assign value (even if it's None after fallback)

            processed_records.append(record)

    return processed_records


# --- Weather Observation Specific Logic ---

def _build_observation_request_details(
        lat: float, lon: float, start_dt: datetime, end_dt: datetime
) -> Tuple[str, Dict[str, Any]]:
    """
    Builds the URL and parameters for a historical weather observation request.
    """
    start_date_str = start_dt.strftime(_DATE_FORMAT)
    # Visual Crossing history is inclusive on both start and end dates
    end_date_str = end_dt.strftime(_DATE_FORMAT)
    location_str = f"{lat},{lon}"
    url = f"{BASE_URL}{location_str}/{start_date_str}/{end_date_str}"

    params = {
        "unitGroup": _API_UNIT_GROUP,
        "include": _API_INCLUDE_HOURS,
        "elements": ",".join(ELEMENTS_TO_REQUEST),  # Use the filtered list
        "contentType": _API_CONTENT_TYPE
    }
    # print(f"Building observation request: URL={url}, Params={params}")
    return url, params


async def fetch_external_weather_observations(
        location_id: int, lat: float, lon: float, start: datetime, end: datetime
) -> List[Dict[str, Any]]:
    """
    Fetches hourly historical weather observations for a given location and date range.

    Args:
        location_id: The ID of the location.
        lat: Latitude of the location.
        lon: Longitude of the location.
        start: The starting datetime (inclusive) for observations.
        end: The ending datetime (inclusive) for observations.

    Returns:
        A list of dictionaries, each representing an hourly observation record.
    """
    print(f"Fetching HOURLY weather observations for location {location_id} ({lat},{lon}) from {start} to {end}")

    # 1. Build Request Details
    # Ensure timezone awareness (assume UTC if none provided)
    start_utc = start.astimezone(timezone.utc) if start.tzinfo else start.replace(tzinfo=timezone.utc)
    end_utc = end.astimezone(timezone.utc) if end.tzinfo else end.replace(tzinfo=timezone.utc)
    url, params = _build_observation_request_details(lat, lon, start_utc, end_utc)

    # 2. Make API Request
    api_data = await _make_visual_crossing_request(url, params, timeout=_OBSERVATION_TIMEOUT_SECONDS)

    # 3. Process Response
    base_record = {'location_id': location_id}
    exclude_keys = {'location_id', 'datetime'}  # These are handled specially
    processed_data = _process_api_response_day_hour(
        api_data=api_data,
        location_id=location_id,
        base_record=base_record,
        time_field_name='datetime',  # Field name in WeatherObservationIn
        schema_cls=WeatherObservationIn,
        exclude_keys=exclude_keys
    )

    print(f"Fetched and processed {len(processed_data)} hourly observation records for location {location_id}.")
    return processed_data


# --- Weather Forecast Specific Logic ---

def _build_forecast_request_details(
        lat: float, lon: float, forecast_basis_date: date
) -> Tuple[str, Dict[str, Any]]:
    """
    Builds the URL and parameters for a historical weather forecast request
    based on a specific forecast run date (basis date). Fetches the next 7 days.
    """
    forecast_basis_date_str = forecast_basis_date.strftime(_DATE_FORMAT)
    # API returns forecast for multiple days, fetch next 7 days from basis date
    # The date range in the URL filters the *results* from that specific forecast run.
    api_end_date = forecast_basis_date + timedelta(days=7)
    api_end_date_str = api_end_date.strftime(_DATE_FORMAT)
    location_str = f"{lat},{lon}"

    # URL structure: /location/start_filter_date/end_filter_date
    url = f"{BASE_URL}{location_str}/{forecast_basis_date_str}/{api_end_date_str}"

    params = {
        "unitGroup": _API_UNIT_GROUP,
        "include": _API_INCLUDE_HOURS,
        "elements": ",".join(ELEMENTS_TO_REQUEST),  # Use the filtered list
        "contentType": _API_CONTENT_TYPE,
        "forecastBasisDate": forecast_basis_date_str  # Key parameter for historical forecast
    }
    # print(f"Building forecast request: URL={url}, Params={params}")
    return url, params


async def fetch_external_weather_forecasts(
        location_id: int, lat: float, lon: float, start: datetime, end: datetime
) -> List[Dict[str, Any]]:
    """
    Fetches historical HOURLY weather forecasts for a given location and date range,
    retrieving the forecast run generated *for each day* within the range.

    Args:
        location_id: The ID of the location.
        lat: Latitude of the location.
        lon: Longitude of the location.
        start: The starting date (inclusive) for which forecast runs should be fetched.
            The time component is ignored, only the date is used as the basis date.
        end: The ending date (inclusive) for which forecast runs should be fetched.
            The time component is ignored.

    Returns:
        A list of dictionaries, each representing an hourly forecast record
        aggregated from all the forecast runs within the specified date range.
    """
    # Ensure start/end are timezone-aware (assume UTC if not specified) for date extraction
    start_utc = start.astimezone(timezone.utc) if start.tzinfo else start.replace(tzinfo=timezone.utc)
    end_utc = end.astimezone(timezone.utc) if end.tzinfo else end.replace(tzinfo=timezone.utc)

    start_date = start_utc.date()
    end_date = end_utc.date()  # End date is inclusive

    print(
        f"Starting fetch for forecast runs from {start_date} to {end_date} (inclusive) for location {location_id} ({lat},{lon})")

    all_aggregated_forecasts: List[Dict[str, Any]] = []
    current_date = start_date

    while current_date <= end_date:
        forecast_basis_date = current_date
        # Forecast run time is typically considered the start of the day (00:00 UTC)
        forecast_run_time = datetime.combine(forecast_basis_date, datetime.min.time(), tzinfo=timezone.utc)

        # Check if the basis date is valid (Visual Crossing has data from 2020-01-01)
        if forecast_run_time < _MIN_FORECAST_DATE:
            print(
                f"Skipping forecast run for basis date {forecast_basis_date_str}: Date is before {_MIN_FORECAST_DATE.date()}.")
            current_date += timedelta(days=1)
            continue

        forecast_basis_date_str = forecast_basis_date.strftime(_DATE_FORMAT)
        print(f"\n--- Fetching forecast run based on date: {forecast_basis_date_str} ---")

        # 1. Build Request Details for this specific forecast run
        url, params = _build_forecast_request_details(lat, lon, forecast_basis_date)

        # 2. Make API Request
        api_data = await _make_visual_crossing_request(url, params, timeout=_FORECAST_TIMEOUT_SECONDS)

        # 3. Process Response if data was received
        if api_data:
            base_record = {
                'location_id': location_id,
                'forecast_run': forecast_run_time
            }
            # Keys handled specially or defined in base_record
            exclude_keys = {'location_id', 'forecast_run', 'target_time'}
            processed_run_data = _process_api_response_day_hour(
                api_data=api_data,
                location_id=location_id,
                base_record=base_record,
                time_field_name='target_time',  # Field name in WeatherForecastIn
                schema_cls=WeatherForecastIn,
                exclude_keys=exclude_keys
            )
            all_aggregated_forecasts.extend(processed_run_data)
            print(f"Processed {len(processed_run_data)} hourly records for run {forecast_basis_date_str}.")
        else:
            # Log error already printed by _make_visual_crossing_request
            print(f"No data received or error occurred for forecast run {forecast_basis_date_str}.")

        # Move to the next day's forecast run
        current_date += timedelta(days=1)

    print(f"\n===\nFinished fetching forecasts.")
    print(
        f"Total processed forecast records for location {location_id} across all runs: {len(all_aggregated_forecasts)}")
    return all_aggregated_forecasts

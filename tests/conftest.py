import pytest
import requests
import os
import asyncio

# The tests run inside the 'fastapi' container, where the service is available at localhost:8021.
# The port 8021 is the one FastAPI listens on inside its container.
# The .gitlab-ci.yml maps a host port (e.g., 18021) to this container port (8021),
# but from within the container, it's still localhost:8021.

@pytest.fixture(scope="session")
def base_url():
    """Provides the base URL for the API service."""
    # FastAPI runs on port 8021 inside its container.
    return "http://localhost:8021"

@pytest.fixture(scope="session")
def api_key():
    """Retrieves the API key from environment variables."""
    key = os.getenv("API_KEY")
    if not key:
        # Skip tests if API_KEY is not set, as they would fail.
        pytest.skip("API_KEY environment variable not set. Skipping integration tests.")
    return key

@pytest.fixture(scope="session")
def http_client(api_key):
    """Provides a requests session pre-configured with the API key header."""
    session = requests.Session()
    session.headers.update({"X-API-Key": api_key})
    return session

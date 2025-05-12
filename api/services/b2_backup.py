import os
import hashlib
import json
import io
from typing import Optional, Dict, Any
from urllib.parse import urlencode

from fastapi.concurrency import run_in_threadpool

from b2sdk.v2 import B2Api, InMemoryAccountInfo, DownloadVersion
from b2sdk.v2.exception import FileNotPresent, NonExistentBucket

# --- Configuration ---
B2_KEY_ID = os.getenv("B2_KEY_ID")
B2_APPLICATION_KEY = os.getenv("B2_APPLICATION_KEY")
B2_BUCKET_NAME = os.getenv("B2_BUCKET_NAME")


# --- B2 Handler Class ---

class B2BackupHandler:
    """Handles checking, retrieving, and saving API response backups to Backblaze B2."""

    def __init__(self):
        self.api = None
        self.bucket = None
        self._initialize_b2()

    def _initialize_b2(self):
        """Initializes the B2 API connection and gets the bucket object."""
        if not all([B2_KEY_ID, B2_APPLICATION_KEY, B2_BUCKET_NAME]):
            print(
                "Warning: B2 credentials (B2_KEY_ID, B2_APPLICATION_KEY, B2_BUCKET_NAME) not fully configured. B2 backup disabled.")
            return

        try:
            info = InMemoryAccountInfo()
            self.api = B2Api(info)
            # Authorization is synchronous
            self.api.authorize_account("production", B2_KEY_ID, B2_APPLICATION_KEY)
            # Getting bucket is synchronous
            self.bucket = self.api.get_bucket_by_name(B2_BUCKET_NAME)
            print(f"Successfully connected to B2 bucket: {B2_BUCKET_NAME}")
        except NonExistentBucket:
            print(f"Error: B2 bucket '{B2_BUCKET_NAME}' not found. B2 backup disabled.")
            self.api = None
            self.bucket = None
        except Exception as e:
            print(f"Error initializing B2 connection: {e}. B2 backup disabled.")
            self.api = None
            self.bucket = None

    def is_enabled(self) -> bool:
        """Checks if the B2 handler is properly initialized and enabled."""
        return self.api is not None and self.bucket is not None

    def _generate_filename(self, url: str, params: Dict[str, Any]) -> str:
        """Generates a unique, deterministic filename based on URL and params."""
        # Ensure consistent order of parameters
        sorted_params = sorted(params.items())
        # Create a stable string representation
        query_string = urlencode(sorted_params)
        full_request_string = f"{url}?{query_string}"
        # Hash the string for a unique filename
        hasher = hashlib.sha256()
        hasher.update(full_request_string.encode('utf-8'))
        # Use hexdigest and add .json extension
        return f"{hasher.hexdigest()}.json"

    async def check_backup(self, url: str, params: Dict[str, Any]) -> Optional[str]:
        """
        Checks if a backup exists for the given request using threadpool.

        Returns:
            The filename if the backup exists, None otherwise.
        """
        if not self.is_enabled():
            return None

        filename = self._generate_filename(url, params)
        try:
            # Use run_in_threadpool for the synchronous SDK call
            await run_in_threadpool(self.bucket.get_file_info_by_name, filename)
            print(f"Backup found in B2: {filename}")
            return filename
        except FileNotPresent:
            print(f"Backup not found in B2 for: {filename}")
            return None
        except Exception as e:
            # Check if the error is due to authorization specifically
            if "unauthorized" in str(e).lower():
                print(
                    f"Authorization error checking B2 backup for {filename}: {e}. Check B2 key permissions (needs readFiles).")
            else:
                print(f"Error checking B2 backup for {filename}: {e}")
            return None  # Treat errors as backup not found

    def _download_b2_file_sync(self, filename: str, download_dest: io.BytesIO):
        """Synchronous helper to download a B2 file into a BytesIO object."""
        # This function will be run in the threadpool
        try:
            download_version = self.bucket.download_file_by_name(filename)
            download_version.save(download_dest)
        except FileNotPresent:
            raise
        except Exception as e:
            print(f"Detailed B2 download error for {filename}: {str(e)}")
            # Wrap other exceptions for clarity
            raise RuntimeError(f"Failed during B2 download of {filename}") from e

    async def get_backup(self, filename: str) -> Optional[Dict[str, Any]]:
        """Downloads and parses a backup file from B2 using threadpool."""
        if not self.is_enabled():
            return None

        print(f"Attempting to download backup from B2: {filename}")
        try:
            download_dest = io.BytesIO()
            # Use run_in_threadpool with the synchronous helper function
            await run_in_threadpool(
                self._download_b2_file_sync,
                filename,
                download_dest
            )
            download_dest.seek(0)  # Rewind buffer to read content
            content = download_dest.read()
            print(f"Successfully downloaded {len(content)} bytes for {filename}")
            # Assume content is JSON
            return json.loads(content.decode('utf-8'))
        except FileNotPresent:
            # This can happen if the file is deleted between check and download
            print(f"Error: Backup file {filename} was not found during download attempt.")
            return None
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON from backup file {filename}: {e}")
            # Optionally delete the corrupted backup?
            return None
        except Exception as e:
            # Catch errors from _download_b2_file_sync or json.loads
            print(f"Error processing B2 backup {filename}: {e}")
            return None

    async def save_backup(self, url: str, params: Dict[str, Any], content: bytes):
        """Saves the raw API response content to B2 using threadpool."""
        if not self.is_enabled():
            return

        filename = self._generate_filename(url, params)
        print(f"Attempting to save backup to B2: {filename} ({len(content)} bytes)")
        try:
            # Use run_in_threadpool for the synchronous SDK call
            file_info = await run_in_threadpool(
                self.bucket.upload_bytes,
                data_bytes=content,
                file_name=filename,
                content_type='application/json'  # Set appropriate content type
            )
            print(f"Successfully uploaded backup to B2: {filename} (ID: {file_info.id_})")
        except Exception as e:
            # Check if the error is due to authorization specifically
            if "unauthorized" in str(e).lower():
                print(
                    f"Authorization error saving B2 backup {filename}: {e}. Check B2 key permissions (needs writeFiles).")
            else:
                print(f"Error saving B2 backup {filename}: {e}")


# --- Singleton Instance ---
# Singleton avoids re-initializing the B2 connection repeatedly
b2_handler = B2BackupHandler()

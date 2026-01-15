"""MinerU API client for PDF parsing."""

import time
import zipfile
from pathlib import Path
from typing import Dict, Any, Optional
import requests
from . import config


class MinerUError(Exception):
    """Base exception for MinerU API errors."""
    pass


class MinerUClient:
    """Client for interacting with MinerU cloud API."""

    def __init__(self, api_token: Optional[str] = None, api_base_url: Optional[str] = None):
        """Initialize MinerU client.

        Args:
            api_token: MinerU API token. If not provided, loads from config.
            api_base_url: Base URL for MinerU API. If not provided, loads from config.
        """
        if api_token is None:
            api_token = config.get_api_token()
        self.api_token = api_token

        if api_base_url is None:
            cfg = config.load_config()
            api_base_url = cfg.get("mineru", {}).get(
                "api_base_url", "https://mineru.net/api/v4"
            )
        self.api_base_url = api_base_url.rstrip("/")

        # Load polling configuration
        cfg = config.load_config()
        self.poll_interval = cfg.get("mineru", {}).get("poll_interval", 3)
        self.max_poll_time = cfg.get("mineru", {}).get("max_poll_time", 600)

    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for API requests.

        Returns:
            Dictionary of HTTP headers
        """
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
            "Accept": "*/*",
        }

    def _check_response(self, response: requests.Response) -> Dict[str, Any]:
        """Check API response for errors.

        Args:
            response: HTTP response object

        Returns:
            Parsed JSON response data

        Raises:
            MinerUError: If response indicates an error
        """
        if response.status_code != 200:
            raise MinerUError(
                f"HTTP {response.status_code}: {response.text}"
            )

        try:
            data = response.json()
        except ValueError as e:
            raise MinerUError(f"Invalid JSON response: {e}")

        if data.get("code") != 0:
            error_code = data.get("code")
            error_msg = data.get("msg", "Unknown error")
            raise MinerUError(f"API error {error_code}: {error_msg}")

        return data

    def request_upload_urls(
        self, file_path: Path, model_version: str = "vlm"
    ) -> tuple[str, str]:
        """Request upload URL for a file.

        Args:
            file_path: Path to the file to upload
            model_version: MinerU model version ("pipeline" or "vlm")

        Returns:
            Tuple of (batch_id, upload_url)

        Raises:
            MinerUError: If request fails
        """
        url = f"{self.api_base_url}/file-urls/batch"

        # Check file size (200MB limit)
        file_size = file_path.stat().st_size
        max_size = 200 * 1024 * 1024  # 200MB
        if file_size > max_size:
            raise MinerUError(
                f"File size ({file_size / 1024 / 1024:.1f}MB) exceeds 200MB limit"
            )

        payload = {
            "files": [{"name": file_path.name}],
            "model_version": model_version,
        }

        response = requests.post(
            url, headers=self._get_headers(), json=payload, timeout=30
        )
        data = self._check_response(response)

        batch_id = data["data"]["batch_id"]
        upload_url = data["data"]["file_urls"][0]

        return batch_id, upload_url

    def upload_file(self, file_path: Path, upload_url: str) -> None:
        """Upload file to the provided URL.

        Args:
            file_path: Path to the file to upload
            upload_url: Pre-signed URL for uploading

        Raises:
            MinerUError: If upload fails
        """
        with open(file_path, "rb") as f:
            response = requests.put(upload_url, data=f, timeout=300)

        if response.status_code != 200:
            raise MinerUError(
                f"File upload failed: HTTP {response.status_code}"
            )

    def get_batch_status(self, batch_id: str) -> Dict[str, Any]:
        """Get status of a batch extraction task.

        Args:
            batch_id: Batch ID from request_upload_urls

        Returns:
            Dictionary containing batch status information

        Raises:
            MinerUError: If request fails
        """
        url = f"{self.api_base_url}/extract-results/batch/{batch_id}"
        response = requests.get(url, headers=self._get_headers(), timeout=30)
        data = self._check_response(response)

        return data["data"]

    def wait_for_completion(self, batch_id: str) -> Dict[str, Any]:
        """Poll for batch completion.

        Args:
            batch_id: Batch ID to monitor

        Returns:
            Completed extraction result

        Raises:
            MinerUError: If extraction fails or times out
        """
        start_time = time.time()

        while True:
            elapsed = time.time() - start_time
            if elapsed > self.max_poll_time:
                raise MinerUError(
                    f"Extraction timed out after {self.max_poll_time}s"
                )

            batch_data = self.get_batch_status(batch_id)
            results = batch_data.get("extract_result", [])

            if not results:
                time.sleep(self.poll_interval)
                continue

            result = results[0]  # We only upload one file
            state = result.get("state")

            if state == "done":
                return result
            elif state == "failed":
                err_msg = result.get("err_msg", "Unknown error")
                raise MinerUError(f"Extraction failed: {err_msg}")
            elif state in ["waiting-file", "pending", "running", "converting"]:
                # Show progress if available
                if state == "running" and "extract_progress" in result:
                    progress = result["extract_progress"]
                    extracted = progress.get("extracted_pages", 0)
                    total = progress.get("total_pages", 0)
                    yield {
                        "state": state,
                        "progress": f"{extracted}/{total}",
                    }
                else:
                    yield {"state": state}

                time.sleep(self.poll_interval)
            else:
                raise MinerUError(f"Unknown state: {state}")

    def download_result(self, zip_url: str, output_dir: Path) -> Path:
        """Download and extract result ZIP file.

        Args:
            zip_url: URL of the result ZIP file
            output_dir: Directory to extract files to

        Returns:
            Path to the extracted directory

        Raises:
            MinerUError: If download or extraction fails
        """
        # Download ZIP file
        response = requests.get(zip_url, timeout=300)
        if response.status_code != 200:
            raise MinerUError(
                f"Failed to download result: HTTP {response.status_code}"
            )

        # Save to temporary file
        output_dir.mkdir(parents=True, exist_ok=True)
        zip_path = output_dir / "result.zip"

        with open(zip_path, "wb") as f:
            f.write(response.content)

        # Extract ZIP
        try:
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(output_dir)
        except zipfile.BadZipFile as e:
            raise MinerUError(f"Invalid ZIP file: {e}")
        finally:
            # Clean up ZIP file
            zip_path.unlink(missing_ok=True)

        return output_dir

    def parse_pdf(self, file_path: Path, output_dir: Path) -> Path:
        """Parse a PDF file and download results.

        This is the main high-level method that orchestrates the entire process.

        Args:
            file_path: Path to PDF file
            output_dir: Directory to save results

        Returns:
            Path to the directory containing extracted files

        Raises:
            MinerUError: If any step fails
        """
        # Step 1: Request upload URL
        batch_id, upload_url = self.request_upload_urls(file_path)

        # Step 2: Upload file
        self.upload_file(file_path, upload_url)

        # Step 3: Wait for completion and show progress
        result = None
        for update in self.wait_for_completion(batch_id):
            # These are progress updates
            yield update

        # At this point, we should have the final result
        # Get it one more time to ensure we have the complete data
        batch_data = self.get_batch_status(batch_id)
        result = batch_data.get("extract_result", [{}])[0]

        # Step 4: Download result
        zip_url = result.get("full_zip_url")
        if not zip_url:
            raise MinerUError("No result URL in response")

        extracted_dir = self.download_result(zip_url, output_dir)

        yield {"state": "completed", "output_dir": str(extracted_dir)}

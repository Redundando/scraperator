from typing import Dict, Optional, Tuple
import requests
import time
from requests.exceptions import RequestException

from .base_scraper import BaseScraper
from logorator import Logger


class RequestScraper(BaseScraper):
    def __init__(
            self,
            headers: Optional[Dict[str, str]] = None,
            timeout: int = 30,
            max_retries: int = 3,
            backoff_factor: float = 2.0
    ):
        self.headers: Optional[Dict[str, str]] = headers
        self.timeout: int = timeout
        self.max_retries: int = max_retries
        self.backoff_factor: float = backoff_factor
        self.last_response = None

    def fetch(self, url: str) -> Tuple[str, int]:
        attempts = 0
        while attempts <= self.max_retries:
            try:
                response = requests.get(url, headers=self.headers, timeout=self.timeout)
                self.last_response = response

                if response.status_code < 400:
                    return response.text, response.status_code

                # If we have a 4xx or 5xx status code
                if attempts == self.max_retries:
                    # On the last attempt, return empty string with status code
                    Logger.note(f"RequestScraper: Max retries ({self.max_retries}) reached with status code {response.status_code}. Returning empty response.")
                    return "", response.status_code

                # Wait before retrying (exponential backoff)
                wait_time = self.backoff_factor ** attempts
                Logger.note(f"RequestScraper: Status code {response.status_code} received. Retrying in {wait_time:.2f}s (attempt {attempts + 1}/{self.max_retries})")
                time.sleep(wait_time)
                attempts += 1

            except RequestException as e:
                if attempts == self.max_retries:
                    # If it's the last attempt, return empty string with 500 status code
                    Logger.note(f"RequestScraper: Max retries ({self.max_retries}) reached after request exception. Returning empty response.")
                    return "", 500

                # Wait before retrying
                wait_time = self.backoff_factor ** attempts
                Logger.note(f"RequestScraper: Request exception: {str(e)}. Retrying in {wait_time:.2f}s (attempt {attempts + 1}/{self.max_retries})")
                time.sleep(wait_time)
                attempts += 1

        # This should not be reached, but just in case
        return "", 500

    def close(self) -> None:
        pass
from typing import Optional, Dict, Any, Literal, Tuple, List
from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext, Playwright, TimeoutError as PlaywrightTimeoutError
import time

from base_scraper import BaseScraper
from logorator import Logger


class PlaywrightScraper(BaseScraper):
    def __init__(
            self,
            browser_type: Literal["chromium", "firefox", "webkit"] = "chromium",
            headless: bool = True,
            browser_args: Optional[Dict[str, Any]] = None,
            context_args: Optional[Dict[str, Any]] = None,
            max_retries: int = 3,
            backoff_factor: float = 2.0,
            networkidle_timeout: int = 10000,  # 10 seconds
            load_timeout: int = 30000,  # 30 seconds
            wait_for_selectors: Optional[List[str]] = None  # CSS selectors to wait for
    ):
        self.browser_type: str = browser_type
        self.headless: bool = headless
        self.browser_args: Dict[str, Any] = browser_args or {}
        self.context_args: Dict[str, Any] = context_args or {}
        self.max_retries: int = max_retries
        self.backoff_factor: float = backoff_factor
        self.networkidle_timeout: int = networkidle_timeout
        self.load_timeout: int = load_timeout
        self.wait_for_selectors: List[str] = wait_for_selectors or []

        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self.last_status_code: int = 200

    def _ensure_browser(self) -> None:
        if self._playwright is None:
            self._playwright = sync_playwright().start()

            if self.browser_type == "chromium":
                browser_launcher = self._playwright.chromium
            elif self.browser_type == "firefox":
                browser_launcher = self._playwright.firefox
            elif self.browser_type == "webkit":
                browser_launcher = self._playwright.webkit
            else:
                raise ValueError(f"Unknown browser type: {self.browser_type}")

            self._browser = browser_launcher.launch(
                    headless=self.headless,
                    **self.browser_args
            )

            self._context = self._browser.new_context(**self.context_args)

    def _try_progressive_load(self, page: Page, url: str) -> Tuple[bool, int]:
        """
        Attempts to load the page using progressively less strict waiting conditions.

        Returns:
            Tuple[bool, int]: (success, status_code)
        """
        # Strategy 1: Try with networkidle first (strictest, but most reliable)
        try:
            Logger.note(f"PlaywrightScraper: Attempting to load with 'networkidle' (timeout: {self.networkidle_timeout}ms)")
            response = page.goto(url, wait_until="networkidle", timeout=self.networkidle_timeout)
            status_code = response.status if response else 200
            return True, status_code
        except PlaywrightTimeoutError:
            Logger.note("PlaywrightScraper: 'networkidle' timed out, falling back to 'load'")
            pass

        # Strategy 2: Fallback to load event (less strict)
        try:
            Logger.note(f"PlaywrightScraper: Attempting to load with 'load' (timeout: {self.load_timeout}ms)")
            response = page.goto(url, wait_until="load", timeout=self.load_timeout)
            status_code = response.status if response else 200
            return True, status_code
        except PlaywrightTimeoutError:
            Logger.note("PlaywrightScraper: 'load' timed out, falling back to 'domcontentloaded'")
            pass

        # Strategy 3: Fallback to domcontentloaded (least strict)
        try:
            Logger.note("PlaywrightScraper: Attempting to load with 'domcontentloaded'")
            response = page.goto(url, wait_until="domcontentloaded", timeout=self.load_timeout)
            status_code = response.status if response else 200
            return True, status_code
        except PlaywrightTimeoutError:
            Logger.note("PlaywrightScraper: All loading strategies failed")
            return False, 408  # Request Timeout

    def _wait_for_selectors(self, page: Page) -> bool:
        """
        Attempts to wait for specific CSS selectors if provided.

        Returns:
            bool: True if all selectors were found or none were specified, False otherwise
        """
        if not self.wait_for_selectors:
            return True

        try:
            for selector in self.wait_for_selectors:
                try:
                    Logger.note(f"PlaywrightScraper: Waiting for selector '{selector}'")
                    page.wait_for_selector(selector, timeout=5000)
                    Logger.note(f"PlaywrightScraper: Found selector '{selector}'")
                except PlaywrightTimeoutError:
                    Logger.note(f"PlaywrightScraper: Selector '{selector}' not found, continuing anyway")
            return True
        except Exception as e:
            Logger.note(f"PlaywrightScraper: Error waiting for selectors: {str(e)}")
            return False

    def fetch(self, url: str) -> Tuple[str, int]:
        self._ensure_browser()
        attempts = 0

        while attempts <= self.max_retries:
            page: Page = self._context.new_page()
            try:
                # Set a default navigation timeout
                page.set_default_navigation_timeout(self.load_timeout)

                # Try progressive loading strategies
                load_success, status_code = self._try_progressive_load(page, url)
                self.last_status_code = status_code

                if not load_success:
                    if attempts == self.max_retries:
                        Logger.note(f"PlaywrightScraper: Max retries reached. All loading strategies failed.")
                        return "", 408
                    wait_time = self.backoff_factor ** attempts
                    Logger.note(f"PlaywrightScraper: All loading strategies failed. Retrying in {wait_time:.2f}s (attempt {attempts + 1}/{self.max_retries})")
                    time.sleep(wait_time)
                    attempts += 1
                    continue

                if status_code >= 400:
                    if attempts == self.max_retries:
                        Logger.note(f"PlaywrightScraper: Max retries reached with status code {status_code}. Returning empty response.")
                        return "", status_code

                    wait_time = self.backoff_factor ** attempts
                    Logger.note(f"PlaywrightScraper: Status code {status_code} received. Retrying in {wait_time:.2f}s (attempt {attempts + 1}/{self.max_retries})")
                    time.sleep(wait_time)
                    attempts += 1
                    continue

                # Try to wait for specified selectors (if any)
                self._wait_for_selectors(page)

                # If we reached here, we consider it a success. Grab the content and return.
                html: str = page.content()
                return html, status_code

            except PlaywrightTimeoutError as e:
                if attempts == self.max_retries:
                    Logger.note(f"PlaywrightScraper: Max retries reached after timeout. Returning empty response with 408 status.")
                    return "", 408

                wait_time = self.backoff_factor ** attempts
                Logger.note(f"PlaywrightScraper: Timeout error occurred: {str(e)}. Retrying in {wait_time:.2f}s (attempt {attempts + 1}/{self.max_retries})")
                time.sleep(wait_time)
                attempts += 1

            except Exception as e:
                if attempts == self.max_retries:
                    Logger.note(f"PlaywrightScraper: Max retries reached after exception: {str(e)}. Returning empty response with 500 status.")
                    return "", 500

                wait_time = self.backoff_factor ** attempts
                Logger.note(f"PlaywrightScraper: Exception occurred: {str(e)}. Retrying in {wait_time:.2f}s (attempt {attempts + 1}/{self.max_retries})")
                time.sleep(wait_time)
                attempts += 1

            finally:
                page.close()

        # This should not be reached, but just in case
        return "", 500

    def close(self) -> None:
        if self._context:
            self._context.close()
            self._context = None

        if self._browser:
            self._browser.close()
            self._browser = None

        if self._playwright:
            self._playwright.stop()
            self._playwright = None

    def __del__(self) -> None:
        self.close()
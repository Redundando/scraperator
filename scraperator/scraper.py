from typing import Optional, Any, Dict, Literal, Tuple, List
import hashlib
from concurrent.futures import ThreadPoolExecutor, Future
import time
from functools import cached_property
from bs4 import BeautifulSoup

from .base_scraper import BaseScraper
from .request_scraper import RequestScraper
from .playwright_scraper import PlaywrightScraper
from cacherator import JSONCache, Cached
from logorator import Logger
from .markdown_converter import MarkdownConverter


class Scraper(JSONCache):
    def __init__(self,
                 url: str,
                 method: str = "requests",
                 cache_ttl: int = 7,
                 clear_cache: bool = False,
                 cache_directory: Optional[str] = None,
                 cache_id: Optional[str] = None,
                 browser_type: Literal["chromium", "firefox", "webkit"] = "chromium",
                 headless: bool = True,
                 max_retries: int = 3,
                 backoff_factor: float = 2.0,
                 markdown_options: Optional[Dict[str, Any]] = None,
                 **kwargs: Any):

        self.url: str = url
        self.cache_directory = cache_directory if cache_directory else f"cache/scraper/{method}"
        self._executor: Optional[ThreadPoolExecutor] = None
        self._future: Optional[Future] = None
        self._soup_instance: Optional[BeautifulSoup] = None
        self._markdown_options = markdown_options or {}
        self._markdown_converter = MarkdownConverter(**self._markdown_options)

        # Clean dictionary structure for caching
        self._cache = {
                'html'       : None,
                'status_code': None
        }

        if method == "requests":
            self.scraper: BaseScraper = RequestScraper(
                    max_retries=max_retries,
                    backoff_factor=backoff_factor,
                    **kwargs
            )
        elif method == "playwright":
            self.scraper: BaseScraper = PlaywrightScraper(
                    browser_type=browser_type,
                    headless=headless,
                    max_retries=max_retries,
                    backoff_factor=backoff_factor,
                    **kwargs
            )
        else:
            raise ValueError(f"Unknown scraping method: {method}")

        if cache_id is None:
            url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
            cache_id = f"{self.url[:150]}_{url_hash}"

        JSONCache.__init__(
                self,
                data_id=cache_id,
                directory=self.cache_directory,
                ttl=cache_ttl,
                clear_cache=clear_cache,
                logging=True
        )

    @property
    def _excluded_cache_vars(self) -> List[str]:
        return ["_cache"]

    def _initialize_executor(self) -> None:
        if self._executor is None:
            self._executor = ThreadPoolExecutor(max_workers=1)

    @Logger()
    def _fetch(self) -> Tuple[str, int]:
        try:
            return self.scraper.fetch(self.url)
        finally:
            self.scraper.close()

    @Logger()
    @Cached()
    def get_content(self) -> Tuple[str, int]:
        html, status_code = self._fetch()
        self._cache['html'] = html
        self._cache['status_code'] = status_code
        self._soup_instance = None
        self.json_cache_save()
        return html, status_code

    @Logger()
    def get_content_force_refresh(self) -> Tuple[str, int]:
        html, status_code = self._fetch()
        self._cache['html'] = html
        self._cache['status_code'] = status_code
        self._soup_instance = None
        result = self.get_content.__wrapped__(self)
        self.json_cache_save()
        return html, status_code

    def scrape(self, async_mode: bool = False, force_refresh: bool = False) -> Optional[str]:
        if self._future is not None and not self._future.done():
            if not async_mode:
                html, _ = self.get_result()
                return html
            return None

        if not async_mode:
            if force_refresh:
                html, status_code = self.get_content_force_refresh()
            else:
                html, status_code = self.get_content()
            return html

        self._initialize_executor()
        if force_refresh:
            self._future = self._executor.submit(self.get_content_force_refresh)
        else:
            self._future = self._executor.submit(self.get_content)
        return None

    def is_complete(self) -> bool:
        if self._future is None:
            return True
        return self._future.done()

    def wait(self, timeout: Optional[float] = None) -> bool:
        if self._future is None:
            return True

        if timeout is None:
            html, status_code = self._future.result()
            self._cache['html'] = html
            self._cache['status_code'] = status_code
            self._soup_instance = None
            self.json_cache_save()
            return True

        try:
            end_time = time.time() + timeout
            while time.time() < end_time:
                if self._future.done():
                    html, status_code = self._future.result()
                    self._cache['html'] = html
                    self._cache['status_code'] = status_code
                    self._soup_instance = None
                    self.json_cache_save()
                    return True
                time.sleep(0.1)
            return False
        except:
            return False

    @Logger()
    def get_result(self, timeout: Optional[float] = None) -> Tuple[str, int]:
        if self._future is None:
            raise ValueError("Scraping hasn't been started. Call scrape() first.")

        html, status_code = self._future.result(timeout=timeout)
        self._cache['html'] = html
        self._cache['status_code'] = status_code
        self._soup_instance = None
        self.json_cache_save()
        return html, status_code

    def get_html(self, force_refresh: bool = False) -> str:
        if force_refresh:
            html, _ = self.get_content_force_refresh()
        else:
            if self._cache['html'] is None:
                html, _ = self.get_content()
            else:
                html = self._cache['html']
        return html

    def get_status_code(self) -> Optional[int]:
        return self._cache['status_code']

    @cached_property
    def soup(self) -> BeautifulSoup:
        if self._soup_instance is None:
            html = self.get_html()
            self._soup_instance = BeautifulSoup(html, "html.parser")
        return self._soup_instance

    @property
    def markdown(self) -> str:
        html = self.get_html()
        return self._markdown_converter.convert(html)

    @Logger()
    @Cached()
    def get_markdown(self) -> str:
        return self.markdown

    def cancel(self) -> bool:
        if self._future is None:
            return False
        return self._future.cancel()

    def shutdown(self, wait: bool = True) -> None:
        if self._executor is not None:
            self._executor.shutdown(wait=wait)
            self._executor = None
        self._future = None
        self.json_cache_save()

    def __str__(self) -> str:
        return f"Scraper ({self.url})"

    def __repr__(self) -> str:
        return f"Scraper ({self.url})"

    def __enter__(self) -> "Scraper":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.shutdown()
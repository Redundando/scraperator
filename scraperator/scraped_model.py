import asyncio as _asyncio
import datetime
import json
import logging
import time
from abc import abstractmethod
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass, field
from pathlib import Path

from logorator import Logger

_logger = logging.getLogger(__name__)


@dataclass
class ScrapedModelConfig:
    # Cache for parsed/structured data (scraperator)
    cache: str = "local"  # "local", "dynamodb", or "none"
    cache_table: str | None = None
    cache_ttl_days: int = 30
    cache_directory: str = "cache"

    # Cache for raw HTML (ghostscraper)
    scrape_cache: str = "local"  # "local", "dynamodb", or "none"
    scrape_cache_table: str | None = None

    # AWS
    aws_region: str | None = None

    # Scraping behaviour
    load_timeout_ms: int = 30000
    max_concurrent: int = 5
    max_scrape_attempts: int = 3
    max_retries: int = 3
    backoff_factor: float = 2.0
    load_strategies: list[str] = field(default_factory=lambda: ["domcontentloaded"])
    wait_for_selectors: list[str] = field(default_factory=list)
    browser_restart_every: int | None = None
    subprocess_batch_size: int | None = None
    stream_max_concurrent: int | None = None
    proxy: str | None = None


_s3_client_cache = None


def _s3_client():
    global _s3_client_cache
    if _s3_client_cache is None:
        import boto3
        _s3_client_cache = boto3.client("s3")
    return _s3_client_cache


class ScrapedModel:
    config: ScrapedModelConfig = ScrapedModelConfig()

    def __init__(self, on_progress: Callable | None = None):
        self.data = {}
        self.on_progress = on_progress
        self.cache_hit = False
        if self.config.cache != "none":
            self.cache_hit = self.load_cache()

    def __str__(self) -> str:
        return self.cache_key

    def _emit(self, event: str, **extra) -> None:
        if not self.on_progress:
            return
        try:
            self.on_progress({"event": event, "ts": time.time(), "url": self.url, **extra})
        except Exception:
            _logger.warning("on_progress callback failed for %s", self.cache_key, exc_info=True)

    @staticmethod
    def _emit_static(on_progress: Callable | None, event: str, **extra) -> None:
        if not on_progress:
            return
        try:
            on_progress({"event": event, "ts": time.time(), **extra})
        except Exception:
            _logger.warning("on_progress callback failed", exc_info=True)

    @property
    @abstractmethod
    def cache_key(self) -> str: ...

    @property
    @abstractmethod
    def url(self) -> str: ...

    @property
    def _scrape_url(self) -> str:
        return self.url

    # === Cache ===

    @staticmethod
    def _is_cache_valid(data: dict) -> bool:
        return bool(
            data.get("all_scrapes_unsuccessful")
            or data.get("not_found")
            or (data.get("response_code") or 0) < 500
        )

    @classmethod
    def _batch_load_cache(cls, objs: list["ScrapedModel"]) -> dict[str, dict]:
        from dynamorator import DynamoDBStore

        store = DynamoDBStore(table_name=cls.config.cache_table, silent=True, region_name=cls.config.aws_region)
        keys = [obj.cache_key for obj in objs]
        return store.batch_get(keys)

    @Logger(exclude_args=["self"])
    def load_cache(self) -> bool:
        if self.config.cache == "dynamodb":
            from dynamorator import DynamoDBStore

            data = DynamoDBStore(table_name=self.config.cache_table, region_name=self.config.aws_region).get(self.cache_key)
        elif self.config.cache == "local":
            path = Path(self.config.cache_directory) / f"{self.cache_key}.json"
            data = json.loads(path.read_text()) if path.exists() else None
        else:
            return False
        if not data:
            return False
        if self._is_cache_valid(data):
            self.data = data
            return True
        return False

    @Logger(exclude_args=["self"])
    def save_cache(self) -> None:
        if self.config.cache == "none":
            return
        self.data["cached_at"] = datetime.datetime.now(datetime.UTC).isoformat()
        if self.config.cache == "dynamodb":
            from dynamorator import DynamoDBStore

            DynamoDBStore(table_name=self.config.cache_table, region_name=self.config.aws_region).put(self.cache_key, self.data, ttl_days=self.config.cache_ttl_days)
        else:
            path = Path(self.config.cache_directory) / f"{self.cache_key}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(self.data, indent=2))

    @Logger(exclude_args=["self"])
    def clear_cache(self) -> None:
        self.data = {}
        if self.config.cache == "dynamodb":
            from dynamorator import DynamoDBStore

            DynamoDBStore(table_name=self.config.cache_table, region_name=self.config.aws_region).delete(self.cache_key)
        elif self.config.cache == "local":
            path = Path(self.config.cache_directory) / f"{self.cache_key}.json"
            if path.exists():
                path.unlink()

    # === Properties ===

    @property
    def response_code(self) -> int | None:
        return self.data.get("response_code")

    @property
    def not_found(self) -> bool:
        return self.data.get("not_found", False)

    @property
    def all_scrapes_unsuccessful(self) -> bool:
        return self.data.get("all_scrapes_unsuccessful", False)

    @property
    def scrape_attempts(self) -> int:
        return self.data.get("scrape_attempts", 0)

    # === JSON Script Helpers ===

    def _get_json_scripts(self, soup) -> list:
        scripts = []
        for script in soup.find_all("script", type="application/json"):
            if script.string:
                try:
                    scripts.append(json.loads(script.string))
                except json.JSONDecodeError:
                    _logger.debug("Malformed JSON in <script> tag", exc_info=True)
        return scripts

    def _get_ld_json_scripts(self, soup) -> list:
        scripts = []
        for script in soup.find_all("script", type="application/ld+json"):
            if script.string:
                try:
                    scripts.append(json.loads(script.string))
                except json.JSONDecodeError:
                    _logger.debug("Malformed LD+JSON in <script> tag", exc_info=True)
        return scripts

    def _flatten_ld_json(self, scripts: list) -> list[dict]:
        result = []
        for item in scripts:
            if isinstance(item, list):
                result.extend(self._flatten_ld_json(item))
            elif isinstance(item, dict):
                result.append(item)
        return result

    async def _apply_scrape_result(self, html: str | None, code: int | None, scraper) -> None:
        if html and (not code or code < 400):
            self.data = await self._parse_html(html, scraper)
            self.data["response_code"] = code
            self._emit("parse_complete", response_code=code)
        elif code and 400 <= code < 500:
            self.data["response_code"] = code
            self.data["not_found"] = True
            self._emit("not_found", response_code=code)
        else:
            self.data["response_code"] = code
            attempts = self.data.get("scrape_attempts", 0) + 1
            self.data["scrape_attempts"] = attempts
            self._emit("scrape_failed", response_code=code, attempt=attempts, max_attempts=self.config.max_scrape_attempts)
            if attempts >= self.config.max_scrape_attempts:
                self.data["all_scrapes_unsuccessful"] = True
                self._emit("all_scrapes_unsuccessful", attempt=attempts)

    # === Scraping ===

    @classmethod
    def _ghostscraper_kwargs(cls) -> dict:
        gs = {
            "load_timeout": cls.config.load_timeout_ms,
            "load_strategies": cls.config.load_strategies,
            "wait_for_selectors": cls.config.wait_for_selectors or None,
            "max_retries": cls.config.max_retries,
            "backoff_factor": cls.config.backoff_factor,
        }
        if cls.config.scrape_cache == "none":
            gs["cache"] = False
        elif cls.config.scrape_cache == "dynamodb":
            gs["dynamodb_table"] = cls.config.scrape_cache_table
        if cls.config.proxy:
            gs["proxy"] = cls.config.proxy
        return gs

    @Logger(exclude_args=["self"])
    async def scrape(self, clear_cache: bool = False, upload_images: bool = True) -> "ScrapedModel":
        if self.data and not clear_cache:
            self._emit("cache_hit")
            return self
        if self.data.get("all_scrapes_unsuccessful"):
            self._emit("scrape_skipped", reason="all_scrapes_unsuccessful")
            return self
        from ghostscraper import GhostScraper

        scraper = GhostScraper(
            url=self._scrape_url,
            on_progress=self.on_progress,
            clear_cache=clear_cache,
            **self._ghostscraper_kwargs(),
        )
        html = await scraper.html()
        code = await scraper.response_code()
        await self._apply_scrape_result(html, code, scraper)
        await self._upload_image_to_s3(upload_images)
        await _asyncio.to_thread(self.save_cache)
        self._emit("cache_saved")
        return self

    @Logger(exclude_args=["self"])
    async def _upload_image_to_s3(self, upload_images: bool) -> None:
        s3_bucket = getattr(self.config, "s3_bucket", None)
        if not (upload_images and s3_bucket and self.data.get("image_url") and not self.data.get("image_s3_key")):
            return
        try:
            import httpx

            image_url = self.data["image_url"]
            response = await _asyncio.to_thread(httpx.get, image_url, follow_redirects=True)
            response.raise_for_status()
            ext = image_url.split("?")[0].rsplit(".", 1)[-1] or "jpg"
            key = f"{self.config.s3_prefix}{self.cache_key}.{ext}"
            await _asyncio.to_thread(
                _s3_client().put_object,
                Bucket=s3_bucket,
                Key=key,
                Body=response.content,
                ContentType=response.headers.get("content-type", "image/jpeg"),
            )
            self.data["image_s3_key"] = key
            self._emit("image_uploaded", key=key)
        except Exception as exc:
            _logger.warning("S3 image upload failed for %s", self.cache_key, exc_info=True)
            self._emit("image_upload_failed", message=str(exc))

    @classmethod
    @abstractmethod
    def _from_input(cls, item) -> "ScrapedModel": ...

    @abstractmethod
    async def _parse_html(self, html: str, scraper=None) -> dict: ...

    @classmethod
    @Logger(exclude_args=["cls"])
    async def scrape_many(
        cls,
        items: list,
        max_concurrent: int | None = None,
        on_progress: Callable | None = None,
        clear_cache: bool = False,
        upload_images: bool = True,
    ) -> list["ScrapedModel"]:
        from ghostscraper import GhostScraper

        if max_concurrent is None:
            max_concurrent = cls.config.max_concurrent

        items = list(dict.fromkeys(items))
        objs = [cls._from_input(item) for item in items]
        to_scrape = [(o, o._scrape_url) for o in objs if not o.data or clear_cache]

        cls._emit_static(on_progress, "batch_started", total=len(objs), to_scrape=len(to_scrape), cached=len(objs) - len(to_scrape))

        if to_scrape:
            obj_by_url = {url: obj for obj, url in to_scrape}
            save_tasks: list[_asyncio.Task] = []

            async def _on_scraped(scraper: GhostScraper) -> None:
                obj = obj_by_url.get(scraper.url)
                if obj is None:
                    return
                html = await scraper.html()
                code = await scraper.response_code()
                await obj._apply_scrape_result(html, code, scraper)
                await obj._upload_image_to_s3(upload_images)
                obj._emit("cache_saved")
                scraper._html = None
                save_tasks.append(_asyncio.create_task(_asyncio.to_thread(obj.save_cache)))

            gs_kwargs = cls._ghostscraper_kwargs()
            await GhostScraper.scrape_many(
                urls=[url for _, url in to_scrape],
                max_concurrent=max_concurrent,
                browser_restart_every=cls.config.browser_restart_every,
                on_progress=on_progress,
                on_scraped=_on_scraped,
                clear_cache=clear_cache,
                **gs_kwargs,
            )
            if save_tasks:
                await _asyncio.gather(*save_tasks)

        cls._emit_static(on_progress, "batch_done", total=len(objs))
        return objs

    @classmethod
    @Logger(exclude_args=["cls"])
    async def scrape_stream(
        cls,
        items: list,
        subprocess_batch_size: int | None = None,
        max_concurrent: int | None = None,
        on_progress: Callable | None = None,
        stream_id: str | None = None,
        upload_images: bool = True,
    ) -> AsyncGenerator["ScrapedModel", None]:
        """Memory-safe streaming alternative to scrape_many. Each chunk runs in a
        disposable subprocess so Chromium memory is reclaimed by the OS.

        Yields cached items first (in input order), then uncached items as the
        stream produces them.
        """
        from ghostscraper import GhostScraper

        items = list(dict.fromkeys(items))
        objs = [cls._from_input(item) for item in items]

        # For stream, we skip per-instance cache loading and do a batch load instead
        if cls.config.cache == "dynamodb":
            for obj in objs:
                obj.cache_hit = False
                obj.data = {}
            cached_data = await _asyncio.to_thread(cls._batch_load_cache, objs)
            for obj in objs:
                data = cached_data.get(obj.cache_key)
                if data and cls._is_cache_valid(data):
                    obj.data = data
                    obj.cache_hit = True

        uncached: list["ScrapedModel"] = []
        for obj in objs:
            if obj.data:
                yield obj
            else:
                uncached.append(obj)

        cls._emit_static(on_progress, "stream_cache_loaded", total=len(objs), cached=len(objs) - len(uncached), to_scrape=len(uncached))

        if not uncached:
            return

        obj_by_url = {obj._scrape_url: obj for obj in uncached}
        gs_kwargs = cls._ghostscraper_kwargs()

        stream = GhostScraper.create_stream(
            urls=list(obj_by_url.keys()),
            stream_id=stream_id,
            subprocess_batch_size=subprocess_batch_size or cls.config.subprocess_batch_size,
            max_concurrent=max_concurrent or cls.config.stream_max_concurrent or cls.config.max_concurrent,
            on_progress=on_progress,
            **gs_kwargs,
        )

        async for scraper in stream:
            obj = obj_by_url.get(scraper.url)
            if obj is None:
                continue
            if scraper.error:
                await obj._apply_scrape_result(None, None, scraper)
            else:
                html = await scraper.html()
                code = await scraper.response_code()
                await obj._apply_scrape_result(html, code, scraper)
            await obj._upload_image_to_s3(upload_images)
            await _asyncio.to_thread(obj.save_cache)
            obj._emit("cache_saved")
            yield obj

    # === Export ===

    @abstractmethod
    def _identity_dict(self) -> dict: ...

    def to_dict(self) -> dict:
        return {**self._identity_dict(), "url": self.url, "cache_hit": self.cache_hit, **self.data}

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def pprint(self):
        print(json.dumps(self.to_dict(), indent=2))

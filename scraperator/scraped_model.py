import asyncio as _asyncio
import datetime
import json
from abc import abstractmethod
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ScrapedModelConfig:
    load_timeout_ms: int = 30000
    max_concurrent: int = 5
    max_scrape_attempts: int = 3
    max_retries: int = 3
    backoff_factor: float = 2.0
    cache_ttl_days: int = 30
    cache_directory: str = "cache"
    load_strategies: list[str] = field(default_factory=lambda: ["domcontentloaded"])
    wait_for_selectors: list[str] = field(default_factory=list)
    browser_restart_every: int | None = None
    subprocess_batch_size: int | None = None
    stream_max_concurrent: int | None = None
    scrape_dynamodb_table: str | None = None
    aws_region: str | None = None


class ScrapedModel:
    config: ScrapedModelConfig = ScrapedModelConfig()

    def __init__(self, dynamodb_table: str | None = None, on_progress: Callable | None = None, use_cache: bool = True):
        self.data = {}
        self._dynamodb_table = dynamodb_table
        self.on_progress = on_progress
        self.cache_hit = False
        if use_cache:
            self.cache_hit = self.load_cache()

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
    def _batch_load_cache(cls, dynamodb_table: str, objs: list["ScrapedModel"]) -> dict[str, dict]:
        from dynamorator import DynamoDBStore

        store = DynamoDBStore(table_name=dynamodb_table, silent=True, region_name=cls.config.aws_region)
        keys = [obj.cache_key for obj in objs]
        return store.batch_get(keys)

    def load_cache(self) -> bool:
        if self._dynamodb_table:
            from dynamorator import DynamoDBStore

            data = DynamoDBStore(table_name=self._dynamodb_table, region_name=self.config.aws_region).get(self.cache_key)
        else:
            path = Path(self.config.cache_directory) / f"{self.cache_key}.json"
            data = json.loads(path.read_text()) if path.exists() else None
        if not data:
            return False
        if self._is_cache_valid(data):
            self.data = data
            return True
        return False

    def save_cache(self) -> None:
        self.data["cached_at"] = datetime.datetime.now(datetime.UTC).isoformat()
        if self._dynamodb_table:
            from dynamorator import DynamoDBStore

            DynamoDBStore(table_name=self._dynamodb_table, region_name=self.config.aws_region).put(self.cache_key, self.data, ttl_days=self.config.cache_ttl_days)
        else:
            path = Path(self.config.cache_directory) / f"{self.cache_key}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(self.data, indent=2))

    def clear_cache(self) -> None:
        self.data = {}
        if self._dynamodb_table:
            from dynamorator import DynamoDBStore

            DynamoDBStore(table_name=self._dynamodb_table, region_name=self.config.aws_region).delete(self.cache_key)
        else:
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
                except Exception:
                    pass
        return scripts

    def _get_ld_json_scripts(self, soup) -> list:
        scripts = []
        for script in soup.find_all("script", type="application/ld+json"):
            if script.string:
                try:
                    scripts.append(json.loads(script.string))
                except Exception:
                    pass
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
        elif code and 400 <= code < 500:
            self.data["response_code"] = code
            self.data["not_found"] = True
        else:
            self.data["response_code"] = code
            attempts = self.data.get("scrape_attempts", 0) + 1
            self.data["scrape_attempts"] = attempts
            if attempts >= self.config.max_scrape_attempts:
                self.data["all_scrapes_unsuccessful"] = True

    # === Scraping ===

    async def scrape(self, clear_cache: bool = False, save_cache: bool = True, upload_images: bool = True) -> "ScrapedModel":
        if self.data and not clear_cache:
            return self
        if self.data.get("all_scrapes_unsuccessful"):
            return self
        from ghostscraper import GhostScraper

        scraper = GhostScraper(
            url=self._scrape_url,
            load_timeout=self.config.load_timeout_ms,
            load_strategies=self.config.load_strategies,
            wait_for_selectors=self.config.wait_for_selectors or None,
            max_retries=self.config.max_retries,
            backoff_factor=self.config.backoff_factor,
            on_progress=self.on_progress,
            clear_cache=clear_cache,
            dynamodb_table=self.config.scrape_dynamodb_table,
        )
        html = await scraper.html()
        code = await scraper.response_code()
        await self._apply_scrape_result(html, code, scraper)
        await self._maybe_upload_images(upload_images)
        if save_cache:
            await _asyncio.to_thread(self.save_cache)
        return self

    async def _maybe_upload_images(self, upload_images: bool) -> None:
        """Override in subclasses that support image uploading."""
        pass

    @classmethod
    @abstractmethod
    def _from_input(cls, item, dynamodb_table: str | None = None, use_cache: bool = True) -> "ScrapedModel": ...

    @abstractmethod
    async def _parse_html(self, html: str, scraper=None) -> dict: ...

    @classmethod
    async def scrape_many(
        cls,
        items: list,
        max_concurrent: int | None = None,
        dynamodb_table: str | None = None,
        scrape_dynamodb_table: str | None = None,
        on_progress: Callable | None = None,
        clear_cache: bool = False,
        save_cache: bool = True,
        upload_images: bool = True,
    ) -> list["ScrapedModel"]:
        from ghostscraper import GhostScraper

        if max_concurrent is None:
            max_concurrent = cls.config.max_concurrent

        items = list(dict.fromkeys(items))
        objs = [cls._from_input(item, dynamodb_table=dynamodb_table) for item in items]
        to_scrape = [(o, o._scrape_url) for o in objs if not o.data or clear_cache]

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
                await obj._maybe_upload_images(upload_images)
                scraper._html = None
                if save_cache:
                    save_tasks.append(_asyncio.create_task(_asyncio.to_thread(obj.save_cache)))

            await GhostScraper.scrape_many(
                urls=[url for _, url in to_scrape],
                max_concurrent=max_concurrent,
                load_timeout=cls.config.load_timeout_ms,
                load_strategies=cls.config.load_strategies,
                wait_for_selectors=cls.config.wait_for_selectors or None,
                max_retries=cls.config.max_retries,
                backoff_factor=cls.config.backoff_factor,
                browser_restart_every=cls.config.browser_restart_every,
                dynamodb_table=scrape_dynamodb_table or cls.config.scrape_dynamodb_table,
                on_progress=on_progress,
                on_scraped=_on_scraped,
                clear_cache=clear_cache,
            )
            if save_tasks:
                await _asyncio.gather(*save_tasks)

        return objs

    @classmethod
    async def scrape_stream(
        cls,
        items: list,
        dynamodb_table: str | None = None,
        scrape_dynamodb_table: str | None = None,
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
        objs = [cls._from_input(item, dynamodb_table=dynamodb_table, use_cache=False) for item in items]

        if dynamodb_table:
            cached_data = await _asyncio.to_thread(cls._batch_load_cache, dynamodb_table, objs)
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

        if not uncached:
            return

        obj_by_url = {obj._scrape_url: obj for obj in uncached}

        stream = GhostScraper.create_stream(
            urls=list(obj_by_url.keys()),
            dynamodb_table=scrape_dynamodb_table or cls.config.scrape_dynamodb_table,
            stream_id=stream_id,
            subprocess_batch_size=subprocess_batch_size or cls.config.subprocess_batch_size,
            max_concurrent=max_concurrent or cls.config.stream_max_concurrent or cls.config.max_concurrent,
            on_progress=on_progress,
            load_timeout=cls.config.load_timeout_ms,
            load_strategies=cls.config.load_strategies,
            wait_for_selectors=cls.config.wait_for_selectors or None,
            max_retries=cls.config.max_retries,
            backoff_factor=cls.config.backoff_factor,
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
            await obj._maybe_upload_images(upload_images)
            await _asyncio.to_thread(obj.save_cache)
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

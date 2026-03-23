import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Optional

from bs4 import BeautifulSoup

from .scraped_model import ScrapedModel, ScrapedModelConfig
from .types import AuthorIdentity, LinkedEntity

AuthorInput = tuple[str, str]  # (tld, author_id)


@dataclass
class AudibleAuthorConfig(ScrapedModelConfig):
    audible_params: str = "overrideBaseCountry=true&ipRedirectOverride=true"
    s3_bucket: str | None = None
    s3_prefix: str = "audible-authors/"


class AudibleAuthor(ScrapedModel):
    config: AudibleAuthorConfig = AudibleAuthorConfig()
    _URL_RE = re.compile(r"audible\.([a-z.]+)/author/(?:[^/]+/)?([A-Z0-9]{10})(?:[?#/]|$)", re.IGNORECASE)

    @staticmethod
    def is_audible_author_url(url: str) -> bool:
        return bool(AudibleAuthor._URL_RE.search(url))

    @staticmethod
    def parse_url(url: str) -> AuthorInput | None:
        m = AudibleAuthor._URL_RE.search(url)
        return (m.group(1), m.group(2)) if m else None

    def __init__(
        self,
        tld: str | None = None,
        author_id: str | None = None,
        url: str | None = None,
        dynamodb_table: str | None = None,
        on_progress: Callable | None = None,
        use_cache: bool = True,
    ):
        if url:
            parsed = AudibleAuthor.parse_url(url)
            if not parsed:
                raise ValueError(f"Could not parse Audible author URL: {url}")
            tld, author_id = parsed
        self.tld = tld
        self.author_id = author_id
        self._url = f"https://www.audible.{tld}/author/{author_id}"
        super().__init__(dynamodb_table=dynamodb_table, on_progress=on_progress, use_cache=use_cache)

    @property
    def cache_key(self) -> str:
        return f"{self.tld}_{self.author_id}"

    @property
    def url(self) -> str:
        return self._url

    @property
    def _scrape_url(self) -> str:
        params = self.config.audible_params
        return f"{self._url}?{params}" if params else self._url

    @classmethod
    def _from_input(cls, item: AuthorInput, dynamodb_table: str = None, use_cache: bool = True) -> "AudibleAuthor":
        tld, author_id = item
        return cls(tld, author_id, dynamodb_table=dynamodb_table, use_cache=use_cache)

    # === Properties ===

    @property
    def name(self) -> Optional[str]:
        return self.data.get("name")

    @property
    def image_url(self) -> Optional[str]:
        return self.data.get("image_url")

    @property
    def image_s3_key(self) -> Optional[str]:
        return self.data.get("image_s3_key")

    @property
    def description(self) -> Optional[str]:
        return self.data.get("description")

    @property
    def audiobooks(self) -> Optional[list[LinkedEntity]]:
        return self.data.get("audiobooks")

    # === Export ===

    def _identity_dict(self) -> AuthorIdentity:
        return {"author_id": self.author_id, "tld": self.tld}

    # === Image Upload ===

    async def _maybe_upload_images(self, upload_images: bool) -> None:
        if upload_images and self.config.s3_bucket and self.data.get("image_url") and not self.data.get("image_s3_key"):
            self.data["image_s3_key"] = await self._upload_image_to_s3(self.data["image_url"])

    async def _upload_image_to_s3(self, image_url: str) -> Optional[str]:
        try:
            import asyncio
            import boto3
            import httpx

            response = await asyncio.to_thread(httpx.get, image_url, follow_redirects=True)
            response.raise_for_status()
            ext = image_url.split("?")[0].rsplit(".", 1)[-1] or "jpg"
            key = f"{self.config.s3_prefix}{self.cache_key}.{ext}"
            s3 = boto3.client("s3")
            await asyncio.to_thread(
                s3.put_object,
                Bucket=self.config.s3_bucket,
                Key=key,
                Body=response.content,
                ContentType=response.headers.get("content-type", "image/jpeg"),
            )
            return key
        except Exception:
            return None

    # === Parsing ===

    async def _parse_html(self, html: str, scraper=None) -> dict:
        soup = BeautifulSoup(html, "html.parser")
        ld_json_scripts = self._get_ld_json_scripts(soup)
        flat = self._flatten_ld_json(ld_json_scripts)
        person = next((s for s in flat if s.get("@type") == "Person"), {})
        return {
            "name": self._extract_name(soup),
            "image_url": person.get("image") or None,
            "description": self._extract_description(soup),
            "audiobooks": [
                {"name": b["name"], "url": b.get("url")}
                for b in flat
                if b.get("@type") == "Audiobook" and b.get("name")
            ] or None,
        }

    def _extract_description(self, soup) -> Optional[str]:
        container = soup.find("div", class_="bc-expander-content")
        if not container:
            return None
        el = container.find("span", class_="bc-color-secondary")
        return el.get_text(" ", strip=True) or None if el else None

    def _extract_name(self, soup) -> Optional[str]:
        el = soup.find("h1")
        return el.text.strip() if el else None

    @classmethod
    async def scrape_many(
        cls,
        authors: list[AuthorInput],
        max_concurrent: int | None = None,
        dynamodb_table: str | None = None,
        scrape_dynamodb_table: str | None = None,
        on_progress: Callable | None = None,
        clear_cache: bool = False,
        save_cache: bool = True,
        upload_images: bool = True,
    ) -> list["AudibleAuthor"]:
        return await super().scrape_many(
            items=authors,
            max_concurrent=max_concurrent,
            dynamodb_table=dynamodb_table,
            scrape_dynamodb_table=scrape_dynamodb_table,
            on_progress=on_progress,
            clear_cache=clear_cache,
            save_cache=save_cache,
            upload_images=upload_images,
        )

import asyncio
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Optional

from bs4 import BeautifulSoup

from .scraped_model import ScrapedModel, ScrapedModelConfig
from .types import AuthorIdentity

AuthorInput = tuple[str, str]  # (tld, author_id)


@dataclass
class AmazonAuthorConfig(ScrapedModelConfig):
    s3_bucket: str | None = None
    s3_prefix: str = "amazon-authors/"
    placeholder_s3_key: str | None = None


class AmazonAuthor(ScrapedModel):
    config: AmazonAuthorConfig = AmazonAuthorConfig()
    _URL_RE = re.compile(r"amazon\.([a-z.]+)/.*?/author/.*?([A-Z0-9]{10})", re.IGNORECASE)

    @staticmethod
    def is_amazon_author_url(url: str) -> bool:
        return bool(AmazonAuthor._URL_RE.search(url))

    @staticmethod
    def parse_url(url: str) -> AuthorInput | None:
        m = AmazonAuthor._URL_RE.search(url)
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
            parsed = AmazonAuthor.parse_url(url)
            if not parsed:
                raise ValueError(f"Could not parse Amazon author URL: {url}")
            tld, author_id = parsed
        self.tld = tld
        self.author_id = author_id
        self._url = url or f"https://www.amazon.{tld}/stores/author/{author_id}"
        super().__init__(dynamodb_table=dynamodb_table, on_progress=on_progress, use_cache=use_cache)

    @property
    def cache_key(self) -> str:
        return f"{self.tld}_{self.author_id}"

    @property
    def url(self) -> str:
        return self._url

    @classmethod
    def _from_input(cls, item: AuthorInput, dynamodb_table: str = None, use_cache: bool = True) -> "AmazonAuthor":
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

    async def is_placeholder_image(self) -> bool:
        if not self.image_s3_key or not self.config.placeholder_s3_key:
            return False
        return await asyncio.to_thread(self._compare_to_placeholder)

    def _compare_to_placeholder(self) -> bool:
        import boto3
        from PIL import Image
        import io
        import statistics

        s3 = boto3.client("s3")

        def _fetch(key: str) -> Image.Image:
            buf = io.BytesIO()
            s3.download_fileobj(self.config.s3_bucket, key, buf)
            buf.seek(0)
            return Image.open(buf).convert("L").resize((16, 16))

        img = _fetch(self.image_s3_key)
        ref = _fetch(self.config.placeholder_s3_key)
        diff = statistics.mean(abs(a - b) for a, b in zip(img.getdata(), ref.getdata()))
        return diff < 10

    # === Export ===

    def _identity_dict(self) -> AuthorIdentity:
        return {"author_id": self.author_id, "tld": self.tld}

    # === Image Upload ===

    async def _maybe_upload_images(self, upload_images: bool) -> None:
        if upload_images and self.config.s3_bucket and self.data.get("image_url") and not self.data.get("image_s3_key"):
            self.data["image_s3_key"] = await self._upload_image_to_s3(self.data["image_url"])

    async def _upload_image_to_s3(self, image_url: str) -> Optional[str]:
        try:
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
        return {
            "name": self._extract_name(soup),
            "image_url": self._extract_image_url(soup),
        }

    def _extract_name(self, soup) -> Optional[str]:
        el = soup.find("h1")
        return el.text.strip() if el else None

    def _extract_image_url(self, soup) -> Optional[str]:
        og = soup.find("meta", property="og:image")
        if og and og.get("content"):
            return og["content"]
        name = self._extract_name(soup)
        el = soup.find("img", alt=lambda a: a and name and name.lower() in a.lower())
        return el.get("src") if el else None

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
    ) -> list["AmazonAuthor"]:
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

import asyncio
import re
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass
from bs4 import BeautifulSoup
from logorator import Logger

from .scraped_model import ScrapedModel, ScrapedModelConfig
from .types import AuthorIdentity, AuthorInput


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
        on_progress: Callable | None = None,
    ):
        if url:
            parsed = AmazonAuthor.parse_url(url)
            if not parsed:
                raise ValueError(f"Could not parse Amazon author URL: {url}")
            tld, author_id = parsed
        self.tld = tld
        self.author_id = author_id
        self._url = url or f"https://www.amazon.{tld}/stores/author/{author_id}"
        super().__init__(on_progress=on_progress)

    def __str__(self) -> str:
        return f"AmazonAuthor({self.tld}, {self.author_id})"

    @property
    def cache_key(self) -> str:
        return f"amazon_author_{self.tld}_{self.author_id}"

    @property
    def url(self) -> str:
        return self._url

    @classmethod
    def _from_input(cls, item: AuthorInput) -> "AmazonAuthor":
        tld, author_id = item
        return cls(tld, author_id)

    # === Properties ===

    @property
    def name(self) -> str | None:
        return self.data.get("name")

    @property
    def image_url(self) -> str | None:
        return self.data.get("image_url")

    @property
    def image_s3_key(self) -> str | None:
        return self.data.get("image_s3_key")

    async def is_placeholder_image(self) -> bool:
        if not self.image_s3_key or not self.config.placeholder_s3_key:
            return False
        return await asyncio.to_thread(self._compare_to_placeholder)

    @Logger(exclude_args=["self"])
    def _compare_to_placeholder(self) -> bool:
        from PIL import Image
        import io
        import statistics
        from .scraped_model import _s3_client

        s3 = _s3_client()

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

    # === Parsing ===

    @Logger(exclude_args=["self", "html"])
    async def _parse_html(self, html: str, scraper=None) -> dict:
        soup = BeautifulSoup(html, "html.parser")
        return {
            "name": self._extract_name(soup),
            "image_url": self._extract_image_url(soup),
        }

    def _extract_name(self, soup) -> str | None:
        el = soup.find("h1")
        return el.text.strip() if el else None

    def _extract_image_url(self, soup) -> str | None:
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
        on_progress: Callable | None = None,
        clear_cache: bool = False,
        upload_images: bool = True,
    ) -> list["AmazonAuthor"]:
        return await super().scrape_many(
            items=authors,
            max_concurrent=max_concurrent,
            on_progress=on_progress,
            clear_cache=clear_cache,
            upload_images=upload_images,
        )

    @classmethod
    def scrape_stream(
        cls,
        authors: list[AuthorInput],
        subprocess_batch_size: int | None = None,
        max_concurrent: int | None = None,
        on_progress: Callable | None = None,
        stream_id: str | None = None,
        upload_images: bool = True,
    ) -> AsyncGenerator["AmazonAuthor", None]:
        return super().scrape_stream(
            items=authors,
            subprocess_batch_size=subprocess_batch_size,
            max_concurrent=max_concurrent,
            on_progress=on_progress,
            stream_id=stream_id,
            upload_images=upload_images,
        )

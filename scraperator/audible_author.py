import re
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass
from bs4 import BeautifulSoup
from logorator import Logger

from .scraped_model import ScrapedModel, ScrapedModelConfig
from .types import AuthorIdentity, AuthorInput, LinkedEntity


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
        on_progress: Callable | None = None,
    ):
        if url:
            parsed = AudibleAuthor.parse_url(url)
            if not parsed:
                raise ValueError(f"Could not parse Audible author URL: {url}")
            tld, author_id = parsed
        self.tld = tld
        self.author_id = author_id
        self._url = f"https://www.audible.{tld}/author/{author_id}"
        super().__init__(on_progress=on_progress)

    def __str__(self) -> str:
        return f"AudibleAuthor({self.tld}, {self.author_id})"

    @property
    def cache_key(self) -> str:
        return f"audible_author_{self.tld}_{self.author_id}"

    @property
    def url(self) -> str:
        return self._url

    @property
    def _scrape_url(self) -> str:
        params = self.config.audible_params
        return f"{self._url}?{params}" if params else self._url

    @classmethod
    def _from_input(cls, item: AuthorInput) -> "AudibleAuthor":
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

    @property
    def description(self) -> str | None:
        return self.data.get("description")

    @property
    def audiobooks(self) -> list[LinkedEntity] | None:
        return self.data.get("audiobooks")

    # === Export ===

    def _identity_dict(self) -> AuthorIdentity:
        return {"author_id": self.author_id, "tld": self.tld}

    # === Parsing ===

    @Logger(exclude_args=["self", "html"])
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

    def _extract_description(self, soup) -> str | None:
        container = soup.find("div", class_="bc-expander-content")
        if not container:
            return None
        el = container.find("span", class_="bc-color-secondary")
        return el.get_text(" ", strip=True) or None if el else None

    def _extract_name(self, soup) -> str | None:
        el = soup.find("h1")
        return el.text.strip() if el else None

    @classmethod
    async def scrape_many(
        cls,
        authors: list[AuthorInput],
        max_concurrent: int | None = None,
        on_progress: Callable | None = None,
        clear_cache: bool = False,
        upload_images: bool = True,
    ) -> list["AudibleAuthor"]:
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
        clear_cache: bool = False,
    ) -> AsyncGenerator["AudibleAuthor", None]:
        return super().scrape_stream(
            items=authors,
            subprocess_batch_size=subprocess_batch_size,
            max_concurrent=max_concurrent,
            on_progress=on_progress,
            stream_id=stream_id,
            upload_images=upload_images,
            clear_cache=clear_cache,
        )

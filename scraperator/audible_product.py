import re
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass
from typing import TypedDict

from bs4 import BeautifulSoup

from .scraped_model import ScrapedModel, ScrapedModelConfig
from .types import LinkedEntity, ProductIdentity

ProductInput = tuple[str, str]  # (tld, asin)


@dataclass
class AudibleProductConfig(ScrapedModelConfig):
    audible_params: str = "overrideBaseCountry=true&ipRedirectOverride=true"


class _SeoRobots(TypedDict, total=False):
    noindex: bool
    nofollow: bool


class _SeoOg(TypedDict, total=False):
    title: str
    description: str
    image: str
    url: str


class _SeoData(TypedDict, total=False):
    title: str
    description: str
    canonical: str
    robots: _SeoRobots
    googlebot: _SeoRobots
    og: _SeoOg
    twitter: dict
    hreflang: dict[str, list[str]]


class AudibleProductData(TypedDict, total=False):
    title: str | None
    authors: list[LinkedEntity] | None
    narrators: list[LinkedEntity] | None
    series: LinkedEntity | None
    tags: list[LinkedEntity] | None
    release_date: str | None
    rating: float | None
    num_ratings: int | None
    length_minutes: int | None
    publisher: LinkedEntity | None
    publisher_summary: str | None
    language: str | None
    format: str | None
    is_audiobook: bool
    is_audible_original: bool
    image_url: str | None
    available_regions: dict[str, str] | None
    seo: _SeoData | None
    response_code: int | None
    cached_at: str


class AudibleProduct(ScrapedModel):
    config: AudibleProductConfig = AudibleProductConfig()
    _URL_RE = re.compile(r"audible\.([a-z.]+)/(?:pd|podcast)/[^/]*/?(B0[A-Z0-9]{8}|\d{10})(?:[?#]|$)", re.IGNORECASE)

    @staticmethod
    def is_audible_url(url: str) -> bool:
        return bool(AudibleProduct._URL_RE.search(url))

    @staticmethod
    def parse_url(url: str) -> ProductInput | None:
        m = AudibleProduct._URL_RE.search(url)
        return (m.group(1), m.group(2)) if m else None

    def __init__(
        self,
        tld: str | None = None,
        asin: str | None = None,
        url: str | None = None,
        dynamodb_table: str | None = None,
        on_progress: Callable | None = None,
        use_cache: bool = True,
    ):
        if url:
            parsed = AudibleProduct.parse_url(url)
            if not parsed:
                raise ValueError(f"Could not parse Audible product URL: {url}")
            tld, asin = parsed
        self.tld = tld
        self.asin = asin.upper()
        self._url = f"https://www.audible.{tld}/pd/{asin}"
        super().__init__(dynamodb_table=dynamodb_table, on_progress=on_progress, use_cache=use_cache)

    @property
    def cache_key(self) -> str:
        return f"{self.tld}_{self.asin}"

    @property
    def url(self) -> str:
        return self._url

    @property
    def _scrape_url(self) -> str:
        params = self.config.audible_params
        return f"{self._url}?{params}" if params else self._url

    @classmethod
    def _from_input(cls, item: ProductInput, dynamodb_table: str = None, use_cache: bool = True) -> "AudibleProduct":
        tld, asin = item
        return cls(tld, asin, dynamodb_table=dynamodb_table, use_cache=use_cache)

    # === Properties ===

    @property
    def title(self) -> str | None:
        return self.data.get("title")

    @property
    def authors(self) -> list[LinkedEntity] | None:
        return self.data.get("authors")

    @property
    def author(self) -> LinkedEntity | None:
        authors = self.data.get("authors")
        return authors[0] if authors else None

    @property
    def narrators(self) -> list[LinkedEntity] | None:
        return self.data.get("narrators")

    @property
    def narrator(self) -> LinkedEntity | None:
        narrators = self.data.get("narrators")
        return narrators[0] if narrators else None

    @property
    def series(self) -> LinkedEntity | None:
        return self.data.get("series")

    @property
    def tags(self) -> list[LinkedEntity] | None:
        return self.data.get("tags")

    @property
    def release_date(self) -> str | None:
        return self.data.get("release_date")

    @property
    def rating(self) -> float | None:
        return self.data.get("rating")

    @property
    def num_ratings(self) -> int | None:
        return self.data.get("num_ratings")

    @property
    def length_minutes(self) -> int | None:
        return self.data.get("length_minutes")

    @property
    def publisher(self) -> LinkedEntity | None:
        return self.data.get("publisher")

    @property
    def publisher_summary(self) -> str | None:
        return self.data.get("publisher_summary")

    @property
    def language(self) -> str | None:
        return self.data.get("language")

    @property
    def format(self) -> str | None:
        return self.data.get("format")

    @property
    def image_url(self) -> str | None:
        return self.data.get("image_url")

    @property
    def available_regions(self) -> dict[str, str] | None:
        return self.data.get("available_regions")

    @property
    def is_audiobook(self) -> bool:
        return self.data.get("is_audiobook", False)

    @property
    def is_audible_original(self) -> bool:
        return self.data.get("is_audible_original", False)

    # === Export ===

    def _identity_dict(self) -> ProductIdentity:
        return {"asin": self.asin, "tld": self.tld}

    # === Parsing ===

    def _clean_url(self, url: str) -> str:
        if not url:
            return url
        from urllib.parse import parse_qs, urlencode, urlparse

        if url.startswith("/"):
            url = f"https://www.audible.{self.tld}{url}"
        if "?" not in url:
            return url
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        search_params = {k: v for k, v in params.items() if k.startswith("search")}
        base = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        return f"{base}?{urlencode(search_params, doseq=True)}" if search_params else base

    def _extract_is_audiobook(self, soup) -> bool:
        return any(s.get("@type") == "Audiobook" for s in self._flatten_ld_json(self._get_ld_json_scripts(soup)))

    def _extract_title(self, soup) -> str | None:
        el = soup.find("h1", slot="title")
        return el.text.strip() if el else None

    def _extract_authors(self, json_scripts: list) -> list[LinkedEntity] | None:
        for m in json_scripts:
            if m.get("authors"):
                return [{"name": a["name"], "url": self._clean_url(a.get("url"))} for a in m["authors"]]
        return None

    def _extract_narrators(self, json_scripts: list) -> list[LinkedEntity] | None:
        for m in json_scripts:
            if m.get("narrators"):
                return [{"name": n["name"], "url": self._clean_url(n.get("url"))} for n in m["narrators"]]
        return None

    def _extract_rating(self, json_scripts: list) -> tuple[float | None, int | None]:
        for m in json_scripts:
            if "rating" in m:
                return m["rating"].get("value"), m["rating"].get("count")
        return None, None

    def _extract_release_date(self, json_scripts: list) -> str | None:
        for m in json_scripts:
            if "releaseDate" in m:
                return m["releaseDate"]
        return None

    def _extract_length(self, json_scripts: list) -> int | None:
        for m in json_scripts:
            if "duration" in m:
                numbers = re.findall(r"\d+", m["duration"])
                if len(numbers) >= 2:
                    return int(numbers[0]) * 60 + int(numbers[1])
                elif len(numbers) == 1:
                    return int(numbers[0]) * 60 if "hr" in m["duration"].lower() else int(numbers[0])
        return None

    def _extract_publisher(self, json_scripts: list) -> LinkedEntity | None:
        for m in json_scripts:
            if m.get("publisher"):
                return {"name": m["publisher"]["name"], "url": self._clean_url(m["publisher"]["url"])}
        return None

    def _extract_language(self, json_scripts: list) -> str | None:
        for m in json_scripts:
            if "language" in m:
                return m["language"]
        return None

    def _extract_format(self, json_scripts: list) -> str | None:
        for m in json_scripts:
            if "format" in m:
                return m["format"]
        return None

    def _extract_publisher_summary(self, soup) -> str | None:
        summary = soup.find("adbl-text-block", slot="summary")
        if not summary:
            return None
        for p in summary.find_all("p"):
            p.replace_with(p.get_text() + "\n\n")
        return summary.get_text().strip()

    def _extract_available_regions(self, soup) -> dict[str, str] | None:
        regions = {
            l.get("hreflang"): l.get("href")
            for l in soup.find_all("link", rel="alternate", hreflang=True)
            if l.get("hreflang") and l.get("href")
        }
        return regions or None

    def _extract_image_url(self, soup) -> str | None:
        el = soup.find("adbl-product-image")
        if el:
            img = el.find("img")
            if img and img.get("src"):
                return img["src"]
        return None

    def _extract_categories(self, json_scripts: list) -> list[LinkedEntity]:
        for m in json_scripts:
            if "categories" in m:
                return [{"name": c["name"], "url": self._clean_url(c["url"])} for c in m["categories"]]
        return []

    def _extract_series(self, soup) -> LinkedEntity | None:
        link = soup.find("a", href=lambda h: h and "/series/" in h)
        return {"name": link.text.strip(), "url": self._clean_url(link.get("href"))} if link else None

    def _extract_is_audible_original(self, soup, json_scripts: list) -> bool:
        if soup.find(attrs={"name": "logo-audible-original"}):
            return True
        for m in json_scripts:
            if (m.get("publisher") or {}).get("name", "").lower() == "audible original":
                return True
            if "original recording audiobook" in (m.get("format") or "").lower():
                return True
        return False

    def _extract_chip_tags(self, soup) -> list[dict]:
        container = soup.find(class_="product-topictag-impression")
        if not container:
            return []
        return [
            {"name": c.text.strip(), "url": self._clean_url(c.get("href"))} for c in container.find_all("adbl-chip")
        ]

    async def _parse_html(self, html: str, scraper=None) -> AudibleProductData:
        soup = BeautifulSoup(html, "html.parser")
        json_scripts = self._get_json_scripts(soup)
        rating, num_ratings = self._extract_rating(json_scripts)
        categories = self._extract_categories(json_scripts)
        chip_tags = self._extract_chip_tags(soup)
        return {
            "title": self._extract_title(soup),
            "authors": self._extract_authors(json_scripts),
            "narrators": self._extract_narrators(json_scripts),
            "series": self._extract_series(soup),
            "tags": (categories + chip_tags) or None,
            "release_date": self._extract_release_date(json_scripts),
            "rating": rating,
            "num_ratings": num_ratings,
            "length_minutes": self._extract_length(json_scripts),
            "publisher": self._extract_publisher(json_scripts),
            "publisher_summary": self._extract_publisher_summary(soup),
            "language": self._extract_language(json_scripts),
            "format": self._extract_format(json_scripts),
            "is_audiobook": self._extract_is_audiobook(soup),
            "is_audible_original": self._extract_is_audible_original(soup, json_scripts),
            "image_url": self._extract_image_url(soup),
            "available_regions": self._extract_available_regions(soup),
            "seo": await scraper.seo() if scraper else None,
        }

    @classmethod
    async def scrape_many(
        cls,
        products: list[ProductInput],
        max_concurrent: int | None = None,
        dynamodb_table: str | None = None,
        scrape_dynamodb_table: str | None = None,
        on_progress: Callable | None = None,
        clear_cache: bool = False,
        save_cache: bool = True,
        upload_images: bool = True,
    ) -> list["AudibleProduct"]:
        return await super().scrape_many(
            items=products,
            max_concurrent=max_concurrent,
            dynamodb_table=dynamodb_table,
            scrape_dynamodb_table=scrape_dynamodb_table,
            on_progress=on_progress,
            clear_cache=clear_cache,
            save_cache=save_cache,
            upload_images=upload_images,
        )

    @classmethod
    def scrape_stream(
        cls,
        products: list[ProductInput],
        dynamodb_table: str | None = None,
        scrape_dynamodb_table: str | None = None,
        subprocess_batch_size: int | None = None,
        max_concurrent: int | None = None,
        on_progress: Callable | None = None,
        stream_id: str | None = None,
        upload_images: bool = True,
    ) -> AsyncGenerator["AudibleProduct", None]:
        return super().scrape_stream(
            items=products,
            dynamodb_table=dynamodb_table,
            scrape_dynamodb_table=scrape_dynamodb_table,
            subprocess_batch_size=subprocess_batch_size,
            max_concurrent=max_concurrent,
            on_progress=on_progress,
            stream_id=stream_id,
            upload_images=upload_images,
        )

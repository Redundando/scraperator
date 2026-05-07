from .scraped_model import ScrapedModel, ScrapedModelConfig
from .types import AuthorIdentity, AuthorInput, LinkedEntity, ProductIdentity, ProductInput, SearchInput, SearchResult

import logging
_logger = logging.getLogger(__name__)

# Default API-based Audible product — requires httpx
try:
    from .audible_product import AudibleProduct, AudibleProductConfig
except ImportError:
    _logger.debug("AudibleProduct (API) not available", exc_info=True)

# Audible search — requires httpx + AudibleProduct
try:
    from .audible_search import AudibleSearch, AudibleSearchConfig
except ImportError:
    _logger.debug("AudibleSearch not available", exc_info=True)

# Scraper fallback — requires beautifulsoup4, ghostscraper
try:
    from .audible_product_scraper import AudibleProductScraper, AudibleProductScraperConfig
except ImportError:
    _logger.debug("AudibleProductScraper not available", exc_info=True)

# Audible author scraper — requires beautifulsoup4, ghostscraper
try:
    from .audible_author import AudibleAuthor, AudibleAuthorConfig
except ImportError:
    _logger.debug("Audible author extras not available", exc_info=True)

# Amazon author scraper — requires beautifulsoup4, boto3, httpx, Pillow
try:
    from .amazon_author import AmazonAuthor, AmazonAuthorConfig
except ImportError:
    _logger.debug("Amazon extras not available", exc_info=True)

__all__ = [
    "ScrapedModel",
    "ScrapedModelConfig",
    "LinkedEntity",
    "ProductIdentity",
    "AuthorIdentity",
    "ProductInput",
    "AuthorInput",
    "SearchInput",
    "SearchResult",
    "AudibleProduct",
    "AudibleProductConfig",
    "AudibleSearch",
    "AudibleSearchConfig",
    "AudibleProductScraper",
    "AudibleProductScraperConfig",
    "AudibleAuthor",
    "AudibleAuthorConfig",
    "AmazonAuthor",
    "AmazonAuthorConfig",
]

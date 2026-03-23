from .scraped_model import ScrapedModel, ScrapedModelConfig
from .types import AuthorIdentity, AuthorInput, LinkedEntity, ProductIdentity, ProductInput

import logging
_logger = logging.getLogger(__name__)

# audible extra — requires beautifulsoup4
try:
    from .audible_product import AudibleProduct, AudibleProductConfig
    from .audible_author import AudibleAuthor, AudibleAuthorConfig
except ImportError:
    _logger.debug("Audible extras not available", exc_info=True)

# amazon extra — requires beautifulsoup4, boto3, httpx, Pillow
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
    "AudibleProduct",
    "AudibleProductConfig",
    "ProductInput",
    "AudibleAuthor",
    "AudibleAuthorConfig",
    "AuthorInput",
    "AmazonAuthor",
    "AmazonAuthorConfig",
]

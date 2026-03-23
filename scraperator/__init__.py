from .scraped_model import ScrapedModel, ScrapedModelConfig
from .types import AuthorIdentity, LinkedEntity, ProductIdentity

from .audible_product import AudibleProduct, AudibleProductConfig, ProductInput
from .audible_author import AudibleAuthor, AudibleAuthorConfig, AuthorInput

# amazon extra — requires boto3, httpx, Pillow
try:
    from .amazon_author import AmazonAuthor, AmazonAuthorConfig
except ImportError:
    pass

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

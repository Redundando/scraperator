from typing import NamedTuple, TypedDict


# --- Dict shapes (serialized into JSON / DynamoDB) ---


class LinkedEntity(TypedDict):
    name: str
    url: str | None


class ProductIdentity(TypedDict):
    asin: str
    tld: str


class AuthorIdentity(TypedDict):
    author_id: str
    tld: str


class SearchResult(TypedDict):
    asin: str
    title: str | None
    authors: list[LinkedEntity] | None
    narrators: list[LinkedEntity] | None
    language: str | None
    release_date: str | None
    runtime_length_min: int | None
    content_delivery_type: str | None
    image_url: str | None


# --- Immutable inputs (construction & destructuring) ---


class ProductInput(NamedTuple):
    tld: str
    asin: str


class AuthorInput(NamedTuple):
    tld: str
    author_id: str


class SearchInput(NamedTuple):
    tld: str
    keywords: str

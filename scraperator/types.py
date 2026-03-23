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


# --- Immutable inputs (construction & destructuring) ---


class ProductInput(NamedTuple):
    tld: str
    asin: str


class AuthorInput(NamedTuple):
    tld: str
    author_id: str

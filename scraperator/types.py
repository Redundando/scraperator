from typing import TypedDict


class LinkedEntity(TypedDict):
    name: str
    url: str | None


class ProductIdentity(TypedDict):
    asin: str
    tld: str


class AuthorIdentity(TypedDict):
    author_id: str
    tld: str

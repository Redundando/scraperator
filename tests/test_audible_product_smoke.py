"""Smoke test for AudibleProduct using a known German audiobook."""

import asyncio
import sys
from pathlib import Path

import httpx

# Ensure local source is used over installed package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scraperator.audible_product import AudibleProduct


def test_kaenguru_rebellion():
    url = "https://www.audible.de/pd/Die-Kaenguru-Rebellion-Hoerbuch/B0FZVDL7K2"
    product = AudibleProduct(url=url)
    asyncio.run(product.scrape(clear_cache=True))

    assert product.response_code == 200, f"Expected 200, got {product.response_code}"
    assert product.title is not None, "Title should not be None"
    assert "Känguru" in product.title or "Rebellion" in product.title, (
        f"Unexpected title: {product.title}"
    )
    assert product.authors is not None and len(product.authors) > 0, "Should have at least one author"
    assert product.narrators is not None and len(product.narrators) > 0, "Should have at least one narrator"
    assert product.language is not None, "Language should not be None"
    assert product.length_minutes is not None and product.length_minutes > 0, "Should have a positive runtime"
    assert product.rating is not None, "Rating should not be None"
    assert product.is_audiobook is True, "Should be an audiobook"
    assert product.image_url is not None, "Should have a cover image"
    assert product.series is not None, "Should have series info"

    print(f"✓ Title: {product.title}")
    print(f"✓ Author: {product.author['name']}")
    print(f"✓ Narrator: {product.narrator['name']}")
    print(f"✓ Language: {product.language}")
    print(f"✓ Length: {product.length_minutes} min")
    print(f"✓ Rating: {product.rating}")
    print(f"✓ Series: {product.series}")
    print(f"✓ Image: {product.image_url[:60]}...")


def test_kaenguru_sims():
    """Test the /sims endpoint for similar products."""
    asin = "B0FZVDL7K2"
    base_url = "https://api.audible.de"
    sims_url = f"{base_url}/1.0/catalog/products/{asin}/sims"
    params = {
        "response_groups": "product_desc,contributors,rating,media",
        "image_sizes": "500",
    }

    async def _fetch_sims():
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(sims_url, params=params)
            return r.status_code, r.json()

    code, data = asyncio.run(_fetch_sims())

    assert code == 200, f"Sims API returned {code}"

    similar = data.get("similar_products") or data.get("products") or []
    print(f"\n--- Similar products for B0FZVDL7K2 (Die Känguru-Rebellion) ---")
    print(f"Response keys: {list(data.keys())}")
    print(f"Similar books returned: {len(similar)}")

    for i, p in enumerate(similar[:10], 1):
        title = p.get("title", "?")
        authors = ", ".join(a.get("name", "?") for a in (p.get("authors") or []))
        print(f"  {i}. {title} — {authors}")

    assert len(similar) > 0, "Expected at least one similar product"


if __name__ == "__main__":
    test_kaenguru_rebellion()
    print("\n✅ Product smoke test passed!")

    print("\n" + "=" * 60)
    test_kaenguru_sims()
    print("\n✅ Sims smoke test passed!")

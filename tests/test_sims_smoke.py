"""Smoke test: Search for well-known books across markets, then fetch similar products."""

import asyncio
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Test cases: (market TLD, search keywords, expected author substring)
TEST_BOOKS = [
    ("com", "Project Hail Mary Andy Weir", "Weir"),
    ("co.uk", "Harry Potter Philosopher's Stone", "Rowling"),
    ("de", "Der Herr der Ringe Tolkien", "Tolkien"),
    ("fr", "Le Petit Prince Saint-Exupéry", "Saint-Exup"),
    ("com.au", "Atomic Habits James Clear", "Clear"),
]

API_BASES = {
    "com": "https://api.audible.com",
    "co.uk": "https://api.audible.co.uk",
    "de": "https://api.audible.de",
    "fr": "https://api.audible.fr",
    "com.au": "https://api.audible.com.au",
}


async def search_and_get_sims(client: httpx.AsyncClient, tld: str, keywords: str, expected_author: str):
    base = API_BASES[tld]

    # Step 1: Search
    search_url = f"{base}/1.0/catalog/search"
    search_params = {
        "keywords": keywords,
        "content_type": "Audiobook",
        "num_results": 1,
        "response_groups": "contributors,product_desc",
    }
    r = await client.get(search_url, params=search_params)
    assert r.status_code == 200, f"[{tld}] Search failed with {r.status_code}"

    products = r.json().get("products", [])
    assert len(products) > 0, f"[{tld}] No search results for '{keywords}'"

    product = products[0]
    asin = product["asin"]
    title = product.get("title", "?")
    authors = ", ".join(a.get("name", "") for a in (product.get("authors") or []))

    print(f"\n{'='*60}")
    print(f"[{tld}] Search: '{keywords}'")
    print(f"  Found: {title} — {authors} ({asin})")

    # Verify we got the right book
    assert expected_author.lower() in authors.lower(), (
        f"[{tld}] Expected author containing '{expected_author}', got '{authors}'"
    )

    # Step 2: Fetch similar products
    sims_url = f"{base}/1.0/catalog/products/{asin}/sims"
    sims_params = {
        "response_groups": "contributors,product_desc,rating",
        "num_results": 25,
    }
    r = await client.get(sims_url, params=sims_params)
    assert r.status_code == 200, f"[{tld}] Sims failed with {r.status_code}"

    sims_data = r.json()
    similar = sims_data.get("similar_products", [])
    print(f"  Similar products: {len(similar)}")

    if not similar:
        print(f"  ⚠️  No similar products returned!")
        return tld, title, asin, 0, []

    # Print top 5
    sims_summary = []
    for i, s in enumerate(similar[:5], 1):
        s_title = s.get("title", "?")
        s_authors = ", ".join(a.get("name", "") for a in (s.get("authors") or []))
        s_rating = (s.get("rating") or {}).get("overall_distribution", {}).get("average_rating")
        rating_str = f" ★{s_rating:.1f}" if s_rating else ""
        print(f"    {i}. {s_title} — {s_authors}{rating_str}")
        sims_summary.append({"title": s_title, "authors": s_authors})

    if len(similar) > 5:
        print(f"    ... and {len(similar) - 5} more")

    return tld, title, asin, len(similar), sims_summary


async def main():
    print("Smoke Test: Search → Similar Products across markets")
    print("=" * 60)

    results = []
    async with httpx.AsyncClient(timeout=30) as client:
        for tld, keywords, expected_author in TEST_BOOKS:
            try:
                result = await search_and_get_sims(client, tld, keywords, expected_author)
                results.append(result)
            except AssertionError as e:
                print(f"\n❌ FAILED: {e}")
                results.append((tld, keywords, None, -1, []))
            except Exception as e:
                print(f"\n❌ ERROR [{tld}]: {e}")
                results.append((tld, keywords, None, -1, []))

    # Summary
    print(f"\n\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    all_passed = True
    for tld, title, asin, count, _ in results:
        status = "✓" if count > 0 else "⚠️" if count == 0 else "❌"
        print(f"  {status} [{tld:6}] {title[:40]:40} → {count} similar")
        if count <= 0:
            all_passed = False

    print(f"\n{'✅ All markets returned similar products!' if all_passed else '⚠️  Some markets had issues.'}")
    return all_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    if not success:
        sys.exit(1)

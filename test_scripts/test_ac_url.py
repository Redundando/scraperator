"""Smoke test: AudibleProduct supports /ac/ URLs."""

from scraperator import AudibleProduct, AudibleProductConfig

AudibleProduct.config = AudibleProductConfig(cache="none")

URL = "https://www.audible.de/ac/Heated-Rivalry-Hoerbuch/B0GT9BLMLF"

# is_audible_url recognises /ac/
assert AudibleProduct.is_audible_url(URL), "is_audible_url should return True for /ac/ URLs"

# parse_url extracts tld and asin
parsed = AudibleProduct.parse_url(URL)
assert parsed is not None, "parse_url should not return None for /ac/ URLs"
assert parsed[0] == "de", f"Expected tld 'de', got '{parsed[0]}'"
assert parsed[1] == "B0GT9BLMLF", f"Expected asin 'B0GT9BLMLF', got '{parsed[1]}'"

# Constructor works and normalises to /pd/
product = AudibleProduct(url=URL)
assert product.tld == "de"
assert product.asin == "B0GT9BLMLF"
assert "/pd/" in product.url, f"Canonical URL should use /pd/, got '{product.url}'"

print("All /ac/ URL smoke tests passed.")

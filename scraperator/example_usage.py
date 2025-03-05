from scraper import Scraper
import time


def example_basic_usage():
    print("Creating scraper for example.com...")
    scraper = Scraper(url="https://www.kicker.de", method="playwright")

    # First fetch - will get fresh content
    print("First fetch (should scrape from source):")
    html = scraper.scrape()
    print(f"HTML length: {len(html)}")

    # Get the markdown version
    markdown = scraper.get_markdown()
    print(f"Markdown length: {len(markdown)}")
    print(f"Markdown preview: {markdown}...")

if __name__ == "__main__":
    print("=== Basic Usage Example ===")
    example_basic_usage()

import asyncio
from scraperator import AudibleProduct, AudibleProductConfig

AudibleProduct.config = AudibleProductConfig(aws_region="us-east-1")


async def main():
    product = AudibleProduct(
        url="https://www.audible.fr/pd/La-maison-vide-Prix-Goncourt-2025-Livre-Audio/B0FW58J539",
        dynamodb_table="scraperator-test-cache",
    )
    await product.scrape()
    product.pprint()


asyncio.run(main())

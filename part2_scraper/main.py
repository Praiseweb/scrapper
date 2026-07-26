import asyncio
import argparse
import os
from .cleaner import clean_all
from .storage import export_all
from .utils import logger

async def async_main():
    parser = argparse.ArgumentParser(description="Real Estate Scraper")
    parser.add_argument("--locations", nargs='+', default=["milwaukee", "columbus"])
    parser.add_argument("--min-price", type=int, default=50000)
    parser.add_argument("--max-price", type=int, default=250000)
    parser.add_argument("--output-dir", type=str, default="output")
    parser.add_argument("--delay-min", type=float, default=2.0)
    parser.add_argument("--delay-max", type=float, default=5.0)
    parser.add_argument("--max-listings", type=int, default=100)

    source = parser.add_mutually_exclusive_group()
    source.add_argument("--redfin", action="store_true", help="Scrape from Redfin (recommended)")
    source.add_argument("--live", action="store_true", help="Scrape Craigslist via Playwright headed browser")
    source.add_argument("--demo", action="store_true", help="Generate realistic demo data")

    args = parser.parse_args()

    os.makedirs("logs", exist_ok=True)
    os.makedirs(args.output_dir, exist_ok=True)

    if args.redfin:
        from .redfin_scraper import RedfinScraper
        logger.info("Source: REDFIN (live API)")
        scraper = RedfinScraper(
            min_price=args.min_price,
            max_price=args.max_price,
            delay_min=args.delay_min,
            delay_max=args.delay_max,
        )
    elif args.live:
        from .playwright_scraper import PlaywrightScraper
        logger.info("Source: CRAIGSLIST (Playwright headed browser)")
        scraper = PlaywrightScraper(
            min_price=args.min_price,
            max_price=args.max_price,
            delay_min=args.delay_min,
            delay_max=args.delay_max,
        )
    else:
        from .scraper import CraigslistScraper
        from .proxy_manager import ProxyManager
        mode = "DEMO" if args.demo else "CRAIGSLIST (auto with demo fallback)"
        logger.info("Source: %s", mode)
        scraper = CraigslistScraper(
            min_price=args.min_price,
            max_price=args.max_price,
            delay_min=args.delay_min,
            delay_max=args.delay_max,
            proxy_manager=ProxyManager(),
            demo_mode=args.demo,
        )

    logger.info("Starting scraper...")
    raw_listings = await scraper.run(locations=args.locations, max_listings=args.max_listings)
    logger.info(f"Scraped {len(raw_listings)} raw listings.")

    logger.info("Cleaning and deduplicating...")
    cleaned_listings = clean_all(raw_listings)
    logger.info(f"Final count: {len(cleaned_listings)}")

    export_all(cleaned_listings, args.output_dir)
    logger.info("Done.")

def main():
    asyncio.run(async_main())

if __name__ == "__main__":
    main()

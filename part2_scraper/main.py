import asyncio
import argparse
import os
from .scraper import CraigslistScraper
from .proxy_manager import ProxyManager
from .cleaner import clean_all
from .storage import export_csv, export_json, export_all
from .utils import logger

async def async_main():
    parser = argparse.ArgumentParser(description="Part 2 - Real Estate Scraper")
    parser.add_argument("--locations", nargs='+', default=["milwaukee", "columbus"], help="Locations to scrape")
    parser.add_argument("--min-price", type=int, default=50000, help="Minimum price")
    parser.add_argument("--max-price", type=int, default=250000, help="Maximum price")
    parser.add_argument("--output-dir", type=str, default="output", help="Output directory")
    parser.add_argument("--format", type=str, choices=["csv", "json", "both"], default="both", help="Export format")
    parser.add_argument("--proxy-file", type=str, default=None, help="File containing proxies")
    parser.add_argument("--delay-min", type=float, default=2.0, help="Min delay between requests")
    parser.add_argument("--delay-max", type=float, default=5.0, help="Max delay between requests")
    parser.add_argument("--max-listings", type=int, default=100, help="Max listings per location")
    
    args = parser.parse_args()
    
    os.makedirs("logs", exist_ok=True)
    os.makedirs(args.output_dir, exist_ok=True)
    
    proxy_manager = ProxyManager(proxy_file=args.proxy_file) if args.proxy_file else ProxyManager()
    
    scraper = CraigslistScraper(
        min_price=args.min_price,
        max_price=args.max_price,
        delay_min=args.delay_min,
        delay_max=args.delay_max,
        proxy_manager=proxy_manager
    )
    
    logger.info("Starting scraper...")
    raw_listings = await scraper.run(locations=args.locations, max_listings=args.max_listings)
    
    logger.info(f"Scraped {len(raw_listings)} raw listings across all locations.")
    
    logger.info("Cleaning and deduplicating listings...")
    cleaned_listings = clean_all(raw_listings)
    
    logger.info(f"Final valid listings count: {len(cleaned_listings)}")
    
    if args.format == "csv":
        export_csv(cleaned_listings, os.path.join(args.output_dir, "listings.csv"))
    elif args.format == "json":
        export_json(cleaned_listings, os.path.join(args.output_dir, "listings.json"))
    else:
        export_all(cleaned_listings, args.output_dir)
        
    logger.info("Scraping job completed.")

def main():
    asyncio.run(async_main())

if __name__ == "__main__":
    main()

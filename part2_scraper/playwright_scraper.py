import asyncio
import random
import sys
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlencode

from playwright.async_api import async_playwright, Page, BrowserContext

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from part3_facebook.stealth import apply_stealth, get_random_user_agent, get_random_viewport
from .parser import parse_search_results, parse_listing_detail
from .utils import logger


class PlaywrightScraper:

    LOCATIONS = {
        "milwaukee": "https://milwaukee.craigslist.org",
        "columbus": "https://columbus.craigslist.org",
    }

    KEYWORDS = ["single family", "duplex", "investment", "rental"]

    def __init__(
        self,
        min_price: int = 50000,
        max_price: int = 250000,
        delay_min: float = 3.0,
        delay_max: float = 6.0,
    ):
        self.min_price = min_price
        self.max_price = max_price
        self.delay_min = delay_min
        self.delay_max = delay_max
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    async def _delay(self) -> None:
        wait = random.uniform(self.delay_min, self.delay_max)
        await asyncio.sleep(wait)

    async def _wait_for_cloudflare(self, page: Page, timeout: int = 30) -> bool:
        logger.info("Waiting for Cloudflare challenge to resolve...")
        try:
            for _ in range(timeout):
                title = await page.title()
                content = await page.content()

                if "just a moment" in title.lower() or "checking your browser" in content.lower():
                    await asyncio.sleep(1)
                    continue

                if "craigslist" in title.lower() or "cl-search-result" in content or "result-row" in content:
                    logger.info("Cloudflare challenge passed")
                    return True

                if page.url and "craigslist.org" in page.url:
                    await asyncio.sleep(1)
                    continue

                await asyncio.sleep(1)

            logger.warning("Cloudflare wait timed out after %ds", timeout)
            return False

        except Exception as e:
            logger.warning("Error during Cloudflare wait: %s", e)
            return False

    async def _fetch_page(self, url: str) -> Optional[str]:
        if not self._page:
            return None

        await self._delay()
        logger.info("Navigating to %s", url)

        try:
            await self._page.goto(url, wait_until="domcontentloaded", timeout=30000)

            title = await self._page.title()
            if "just a moment" in title.lower():
                passed = await self._wait_for_cloudflare(self._page)
                if not passed:
                    return None

            await self._page.wait_for_timeout(random.randint(1000, 2000))
            html = await self._page.content()

            if len(html) < 500:
                logger.warning("Page content suspiciously short (%d bytes)", len(html))
                return None

            return html

        except Exception as e:
            logger.warning("Failed to fetch %s: %s", url, e)
            return None

    async def scrape_location(self, location_key: str, max_listings: int = 50) -> List[Dict]:
        base_url = self.LOCATIONS.get(location_key)
        if not base_url:
            logger.error("Unknown location: %s", location_key)
            return []

        search_url = f"{base_url}/search/rea"
        all_listings: List[Dict] = []
        seen_urls: set = set()

        for kw in self.KEYWORDS:
            if len(all_listings) >= max_listings:
                break

            offset = 0
            while len(all_listings) < max_listings:
                params = {
                    "min_price": self.min_price,
                    "max_price": self.max_price,
                    "query": kw,
                    "s": offset,
                }
                url = f"{search_url}?{urlencode(params)}"
                html = await self._fetch_page(url)

                if not html:
                    logger.warning("No HTML returned for '%s' offset %d", kw, offset)
                    break

                results = parse_search_results(html)
                if not results:
                    logger.info("No results for '%s' at offset %d", kw, offset)
                    break

                new_count = 0
                for r in results:
                    listing_url = r.get("url", "")
                    if listing_url and not listing_url.startswith("http"):
                        listing_url = f"{base_url}{listing_url}"
                    r["url"] = listing_url

                    if not listing_url or listing_url in seen_urls:
                        continue
                    seen_urls.add(listing_url)

                    state = "wi" if location_key == "milwaukee" else "oh"
                    r["location"] = f"{location_key}_{state}"
                    all_listings.append(r)
                    new_count += 1

                logger.info(
                    "Keyword '%s' offset %d: %d results, %d new, %d total",
                    kw, offset, len(results), new_count, len(all_listings),
                )

                if len(results) < 120:
                    break
                offset += 120

        logger.info("Fetching detail pages for %d listings...", min(len(all_listings), max_listings))
        detailed: List[Dict] = []

        for i, listing in enumerate(all_listings[:max_listings]):
            url = listing.get("url", "")
            if not url:
                continue

            html = await self._fetch_page(url)
            if html:
                details = parse_listing_detail(html)
                if details:
                    details.update(listing)
                    detailed.append(details)
                else:
                    detailed.append(listing)

                logger.info(
                    "  [%d/%d] %s",
                    i + 1, min(len(all_listings), max_listings),
                    details.get("title", listing.get("title", ""))[:50] if details else listing.get("title", "")[:50],
                )
            else:
                detailed.append(listing)

        return detailed

    async def run(self, locations: List[str], max_listings: int = 50) -> List[Dict]:
        all_results: List[Dict] = []
        viewport = get_random_viewport()
        ua = get_random_user_agent()

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=False,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--disable-infobars",
                ],
            )

            self._context = await browser.new_context(
                viewport=viewport,
                user_agent=ua,
                locale="en-US",
                timezone_id="America/Chicago",
                permissions=["geolocation"],
                geolocation={"latitude": 43.0389, "longitude": -87.9065},
            )

            self._page = await self._context.new_page()
            await apply_stealth(self._page)

            for loc in locations:
                logger.info("=" * 60)
                logger.info("SCRAPING: %s", loc.upper())
                logger.info("=" * 60)
                results = await self.scrape_location(loc, max_listings)
                all_results.extend(results)
                logger.info("Completed %s: %d listings", loc, len(results))

            logger.info("Total: %d listings across %d locations", len(all_results), len(locations))

            await browser.close()

        return all_results

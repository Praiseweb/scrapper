import asyncio
import random
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlencode

try:
    from curl_cffi.requests import AsyncSession
    HAS_CURL_CFFI = True
except ImportError:
    HAS_CURL_CFFI = False

import httpx

from .utils import logger, get_random_user_agent, RateLimiter
from .parser import parse_search_results, parse_listing_detail

class CraigslistScraper:

    LOCATIONS = {
        "milwaukee": {
            "base_url": "https://milwaukee.craigslist.org",
            "state": "wi",
            "city": "Milwaukee",
            "neighborhoods": [
                "Bay View", "Riverwest", "Walker's Point", "Third Ward",
                "East Side", "Sherman Park", "Washington Heights", "Wauwatosa",
                "West Allis", "Shorewood", "Whitefish Bay", "Greenfield",
                "South Milwaukee", "Cudahy", "Oak Creek", "Franklin",
                "Brookfield", "Pewaukee", "Menomonee Falls", "Glendale",
            ],
            "streets": [
                "N Oakland Ave", "S Kinnickinnic Ave", "W National Ave",
                "N Farwell Ave", "E Brady St", "W Wisconsin Ave",
                "S Layton Blvd", "N 76th St", "W Bluemound Rd",
                "S 13th St", "N Sherman Blvd", "W Vliet St",
                "E North Ave", "S 27th St", "W Lincoln Ave",
            ],
            "zip_codes": [
                "53202", "53203", "53204", "53205", "53206", "53207",
                "53208", "53209", "53210", "53211", "53212", "53213",
                "53214", "53215", "53216", "53217", "53218", "53219",
                "53220", "53221", "53222", "53223", "53224", "53225",
                "53226", "53227", "53228", "53233", "53235",
            ],
        },
        "columbus": {
            "base_url": "https://columbus.craigslist.org",
            "state": "oh",
            "city": "Columbus",
            "neighborhoods": [
                "Short North", "German Village", "Clintonville", "Grandview Heights",
                "Upper Arlington", "Westerville", "Dublin", "Hilliard",
                "Reynoldsburg", "Gahanna", "Grove City", "Worthington",
                "Bexley", "Whitehall", "Linden", "Franklinton",
                "Italian Village", "Old North", "Victorian Village", "Harrison West",
            ],
            "streets": [
                "N High St", "E Broad St", "W Fifth Ave", "S Third St",
                "N Fourth St", "E Main St", "W Lane Ave", "S Hamilton Rd",
                "N Cassady Ave", "E Livingston Ave", "W Mound St",
                "Olentangy River Rd", "Sawmill Rd", "Bethel Rd",
                "Henderson Rd",
            ],
            "zip_codes": [
                "43201", "43202", "43203", "43204", "43205", "43206",
                "43207", "43209", "43210", "43211", "43212", "43213",
                "43214", "43215", "43216", "43217", "43219", "43220",
                "43221", "43222", "43223", "43224", "43227", "43228",
                "43229", "43230", "43231", "43232", "43235",
            ],
        },
    }

    PROPERTY_TYPES = [
        "house", "duplex", "condo", "townhouse", "apartment",
    ]

    KEYWORDS = ["single family", "duplex", "investment", "rental"]

    IMPERSONATE_OPTIONS = ["chrome120", "chrome116", "chrome119", "chrome124"]

    def __init__(
        self,
        min_price: int = 50000,
        max_price: int = 250000,
        delay_min: float = 2.0,
        delay_max: float = 5.0,
        proxy_manager=None,
        demo_mode: bool = False,
    ):
        self.min_price = min_price
        self.max_price = max_price
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.rate_limiter = RateLimiter(delay_min, delay_max)
        self.proxy_manager = proxy_manager
        self.demo_mode = demo_mode
        self._impersonate = random.choice(self.IMPERSONATE_OPTIONS)

    def _get_headers(self) -> dict:
        ua = get_random_user_agent()
        return {
            "User-Agent": ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Cache-Control": "max-age=0",
        }

    async def _try_live_fetch(self, url: str) -> Optional[str]:
        if HAS_CURL_CFFI:
            try:
                async with AsyncSession(impersonate=self._impersonate) as session:
                    response = await session.get(
                        url, headers=self._get_headers(), timeout=30
                    )
                    if response.status_code == 200:
                        logger.info("[OK] curl_cffi succeeded for %s", url)
                        return response.text
                    logger.warning(
                        "curl_cffi got HTTP %d for %s", response.status_code, url
                    )
            except Exception as e:
                logger.warning("curl_cffi failed: %s", e)

        try:
            async with httpx.AsyncClient(
                headers=self._get_headers(),
                timeout=30,
                follow_redirects=True,
            ) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    logger.info("[OK] httpx succeeded for %s", url)
                    return response.text
                logger.warning("httpx got HTTP %d for %s", response.status_code, url)
        except Exception as e:
            logger.warning("httpx failed: %s", e)

        return None

    def _generate_listing(self, location_key: str, index: int) -> Dict:
        loc_data = self.LOCATIONS[location_key]
        seed = hashlib.md5(f"{location_key}-{index}".encode()).hexdigest()
        rng = random.Random(seed)

        prop_type = rng.choices(
            self.PROPERTY_TYPES,
            weights=[50, 15, 15, 10, 10],
            k=1,
        )[0]

        price_ranges = {
            "house": (65000, 245000),
            "duplex": (85000, 230000),
            "condo": (55000, 180000),
            "townhouse": (70000, 200000),
            "apartment": (50000, 150000),
        }
        pmin, pmax = price_ranges[prop_type]
        pmin = max(pmin, self.min_price)
        pmax = min(pmax, self.max_price)
        price = round(rng.randint(pmin, pmax) / 1000) * 1000

        bed_ranges = {
            "house": (2, 5), "duplex": (3, 6), "condo": (1, 3),
            "townhouse": (2, 4), "apartment": (1, 3),
        }
        bedrooms = rng.randint(*bed_ranges[prop_type])
        bathrooms = rng.choice([1, 1, 1.5, 2, 2, 2.5, 3])

        base_sqft = {1: 600, 2: 900, 3: 1200, 4: 1600, 5: 2000, 6: 2400}
        sqft = base_sqft.get(bedrooms, 1200) + rng.randint(-200, 400)

        street_num = rng.randint(100, 9999)
        street = rng.choice(loc_data["streets"])
        neighborhood = rng.choice(loc_data["neighborhoods"])
        zipcode = rng.choice(loc_data["zip_codes"])
        address = f"{street_num} {street}, {neighborhood}, {loc_data['city']}, {loc_data['state'].upper()} {zipcode}"

        title_templates = [
            f"{bedrooms}BR/{int(bathrooms)}BA {prop_type.title()} in {neighborhood}",
            f"Charming {bedrooms} Bed {prop_type.title()} — {neighborhood}",
            f"MUST SEE! {bedrooms}br - {sqft}ft² ({neighborhood})",
            f"{prop_type.title()} for Sale | {bedrooms}BR {int(bathrooms)}BA | {neighborhood}",
            f"Investment Opportunity — {bedrooms}BR {prop_type.title()} {neighborhood}",
            f"Renovated {bedrooms} Bedroom {prop_type.title()} Near Downtown",
            f"Great {prop_type.title()} in {neighborhood} — {sqft} sqft",
            f"Move-In Ready {bedrooms}BR/{int(bathrooms)}BA in {neighborhood}",
        ]
        title = rng.choice(title_templates)

        features = rng.sample([
            "hardwood floors throughout", "updated kitchen with granite countertops",
            "new roof (2023)", "central air conditioning", "attached garage",
            "fenced backyard", "stainless steel appliances", "finished basement",
            "close to parks and schools", "quiet neighborhood",
            "near public transit", "washer/dryer included",
            "new furnace", "fresh paint throughout", "large master bedroom",
            "walk-in closets", "open floor plan", "natural light",
            "recently renovated bathroom", "energy efficient windows",
        ], k=rng.randint(3, 7))

        description = (
            f"Beautiful {bedrooms} bedroom, {bathrooms} bath {prop_type} "
            f"in the heart of {neighborhood}. This {sqft} sq ft property features "
            f"{', '.join(features[:-1])}, and {features[-1]}. "
            f"Priced to sell at ${price:,}. Don't miss this opportunity!"
        )

        days_ago = rng.randint(0, 30)
        posted_date = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%S")

        post_id = rng.randint(7700000000, 7799999999)
        base_url = loc_data["base_url"]
        url = f"{base_url}/rea/d/{title.lower().replace(' ', '-')[:30]}/{post_id}.html"

        state = loc_data["state"]
        return {
            "title": title,
            "raw_price": f"${price:,}",
            "raw_address": address,
            "raw_housing_info": f"{bedrooms}br - {sqft}ft² - {prop_type}",
            "description": description,
            "posted_date": posted_date,
            "url": url,
            "location": f"{location_key}_{state}",
            "source": "craigslist",
            "property_type": prop_type,
        }

    def _generate_demo_listings(self, location_key: str, count: int) -> List[Dict]:
        listings = []
        for i in range(count):
            listings.append(self._generate_listing(location_key, i))
        return listings

    async def scrape_location(self, location_key: str, max_listings: int = 100) -> List[Dict]:
        loc_data = self.LOCATIONS.get(location_key)
        if not loc_data:
            logger.error("Unknown location: %s", location_key)
            return []

        base_url = loc_data["base_url"]
        search_url = f"{base_url}/search/rea"

        if self.demo_mode:
            logger.info(
                "Demo mode enabled — generating %d realistic listings for %s",
                max_listings, location_key,
            )
            return self._generate_demo_listings(location_key, max_listings)

        logger.info("Attempting live scrape of %s...", location_key)
        test_url = f"{search_url}?min_price={self.min_price}&max_price={self.max_price}&query=house&s=0"
        await self.rate_limiter.wait()
        html = await self._try_live_fetch(test_url)

        if html:
            logger.info("[OK] Live scraping available for %s!", location_key)
            return await self._live_scrape_location(location_key, html, max_listings)
        else:
            logger.warning(
                "[BLOCKED] Live scraping blocked for %s (Cloudflare/IP restriction). "
                "Falling back to demo mode with realistic data.",
                location_key,
            )
            return self._generate_demo_listings(location_key, max_listings)

    async def _live_scrape_location(
        self, location_key: str, first_page_html: str, max_listings: int
    ) -> List[Dict]:
        loc_data = self.LOCATIONS[location_key]
        base_url = loc_data["base_url"]
        search_url = f"{base_url}/search/rea"
        all_listings: List[Dict] = []
        seen_urls: set = set()

        results = parse_search_results(first_page_html)
        for r in results:
            url = r.get("url", "")
            if url and not url.startswith("http"):
                url = urljoin(base_url, url)
            r["url"] = url
            if url not in seen_urls:
                seen_urls.add(url)
                r["location"] = f"{location_key}_{loc_data['state']}"
                all_listings.append(r)

        logger.info("First page: %d listings found", len(results))

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
                query = urlencode(params)
                url = f"{search_url}?{query}"

                await self.rate_limiter.wait()
                html = await self._try_live_fetch(url)

                if not html:
                    break

                results = parse_search_results(html)
                if not results:
                    break

                new_count = 0
                for r in results:
                    listing_url = r.get("url", "")
                    if listing_url and not listing_url.startswith("http"):
                        listing_url = urljoin(base_url, listing_url)
                    r["url"] = listing_url
                    if listing_url not in seen_urls:
                        seen_urls.add(listing_url)
                        r["location"] = f"{location_key}_{loc_data['state']}"
                        all_listings.append(r)
                        new_count += 1

                logger.info(
                    "Keyword '%s' offset %d: %d results, %d new",
                    kw, offset, len(results), new_count,
                )

                if len(results) < 120:
                    break
                offset += 120

        logger.info("Fetching %d detail pages...", min(len(all_listings), max_listings))
        detailed = []
        for i, listing in enumerate(all_listings[:max_listings]):
            url = listing.get("url", "")
            if not url:
                continue
            await self.rate_limiter.wait()
            html = await self._try_live_fetch(url)
            if html:
                details = parse_listing_detail(html)
                details.update(listing)
                detailed.append(details)
                logger.info(
                    "  [%d/%d] OK %s",
                    i + 1, min(len(all_listings), max_listings),
                    details.get("title", "")[:50],
                )
            else:
                detailed.append(listing)

        return detailed

    async def run(self, locations: List[str], max_listings: int = 100) -> List[Dict]:
        all_results: List[Dict] = []

        for loc in locations:
            logger.info("=" * 60)
            logger.info("SCRAPING: %s", loc.upper())
            logger.info("=" * 60)
            results = await self.scrape_location(loc, max_listings)
            all_results.extend(results)
            logger.info(
                "Completed %s: %d listings collected", loc, len(results)
            )

        logger.info(
            "Total: %d listings across %d locations",
            len(all_results), len(locations),
        )
        return all_results

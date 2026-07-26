import re
import json
import asyncio
import random
from typing import Dict, List, Optional

import httpx

from .utils import logger, get_random_user_agent, RateLimiter


class RedfinScraper:

    LOCATIONS = {
        "milwaukee": {
            "city": "Milwaukee",
            "state": "WI",
            "poly": "-88.07 42.84,-87.82 42.84,-87.82 43.19,-88.07 43.19,-88.07 42.84",
        },
        "columbus": {
            "city": "Columbus",
            "state": "OH",
            "poly": "-83.20 39.87,-82.77 39.87,-82.77 40.16,-83.20 40.16,-83.20 39.87",
        },
    }

    API_BASE = "https://www.redfin.com/stingray/api/gis"

    def __init__(
        self,
        min_price: int = 50000,
        max_price: int = 250000,
        delay_min: float = 2.0,
        delay_max: float = 5.0,
    ):
        self.min_price = min_price
        self.max_price = max_price
        self.rate_limiter = RateLimiter(delay_min, delay_max)

    def _get_headers(self) -> dict:
        return {
            "User-Agent": get_random_user_agent(),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.redfin.com/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        }

    @staticmethod
    def _parse_response(text: str) -> dict:
        cleaned = re.sub(r'^.*?&&', '', text, count=1)
        return json.loads(cleaned)

    def _normalize_home(self, home: dict, location_key: str) -> Dict:
        loc = self.LOCATIONS[location_key]
        price_val = home.get("price", {}).get("value")
        sqft_val = home.get("sqFt", {}).get("value")
        street = home.get("streetLine", {}).get("value", "")
        city = home.get("city", loc["city"])
        state = home.get("state", loc["state"])
        zipcode = home.get("zip", "")
        address = f"{street}, {city}, {state} {zipcode}".strip(", ")

        url_path = home.get("url", "")
        url = f"https://www.redfin.com{url_path}" if url_path else ""

        listing_id = home.get("listingId", "")
        mls_val = home.get("mlsId", {}).get("value", "")
        dom = home.get("dom", {}).get("value")
        lot_size = home.get("lotSize", {}).get("value")
        year_built = home.get("yearBuilt", {}).get("value")
        hoa = home.get("hoa", {}).get("value")
        status = home.get("mlsStatus", "")

        prop_type_map = {
            1: "house", 2: "condo", 3: "townhouse",
            4: "multi-family", 5: "land", 6: "other",
        }
        raw_type = home.get("propertyType")
        prop_type = prop_type_map.get(raw_type, str(raw_type) if raw_type else None)

        return {
            "title": f"{home.get('beds', '?')}BR/{home.get('baths', '?')}BA {prop_type or 'Property'} in {city}",
            "raw_price": f"${price_val:,}" if price_val else None,
            "raw_address": address,
            "raw_housing_info": f"{home.get('beds', '')}br - {sqft_val or ''}ft2 - {prop_type or ''}",
            "description": (
                f"{home.get('beds', '?')} bed, {home.get('baths', '?')} bath {prop_type or 'property'} "
                f"at {street}, {city}, {state}. "
                f"{f'{sqft_val:,} sqft. ' if sqft_val else ''}"
                f"{f'Built {year_built}. ' if year_built else ''}"
                f"{f'Lot: {lot_size:,} sqft. ' if lot_size else ''}"
                f"{f'HOA: ${hoa}/mo. ' if hoa else ''}"
                f"{f'{dom} days on market. ' if dom else ''}"
                f"MLS# {mls_val}. Status: {status}."
            ),
            "url": url,
            "posted_date": None,
            "location": f"{location_key}_{loc['state'].lower()}",
            "source": "redfin",
            "property_type": prop_type,
            "mls_id": mls_val,
            "listing_id": str(listing_id) if listing_id else None,
            "year_built": year_built,
            "lot_size": lot_size,
            "hoa": hoa,
            "days_on_market": dom,
            "mls_status": status,
        }

    async def scrape_location(self, location_key: str, max_listings: int = 100) -> List[Dict]:
        loc = self.LOCATIONS.get(location_key)
        if not loc:
            logger.error("Unknown location: %s", location_key)
            return []

        await self.rate_limiter.wait()

        params = {
            "al": "1",
            "include_nearby_homes": "true",
            "min_price": str(self.min_price),
            "max_price": str(self.max_price),
            "num_homes": str(min(max_listings, 350)),
            "status": "9",
            "uipt": "1,2,3,4,5,6",
            "v": "8",
            "poly": loc["poly"],
        }

        logger.info("Fetching Redfin listings for %s...", location_key)

        async with httpx.AsyncClient(
            headers=self._get_headers(),
            timeout=30,
            follow_redirects=True,
        ) as client:
            try:
                response = await client.get(self.API_BASE, params=params)

                if response.status_code != 200:
                    logger.error("Redfin returned HTTP %d for %s", response.status_code, location_key)
                    return []

                data = self._parse_response(response.text)
                homes = data.get("payload", {}).get("homes", [])
                logger.info("Redfin returned %d homes for %s", len(homes), location_key)

                listings = []
                for home in homes[:max_listings]:
                    try:
                        normalized = self._normalize_home(home, location_key)
                        listings.append(normalized)
                    except Exception as e:
                        logger.warning("Failed to normalize home: %s", e)

                return listings

            except Exception as e:
                logger.error("Failed to fetch Redfin data for %s: %s", location_key, e)
                return []

    async def run(self, locations: List[str], max_listings: int = 100) -> List[Dict]:
        all_results: List[Dict] = []

        for loc in locations:
            logger.info("=" * 60)
            logger.info("SCRAPING: %s (Redfin)", loc.upper())
            logger.info("=" * 60)
            results = await self.scrape_location(loc, max_listings)
            all_results.extend(results)
            logger.info("Completed %s: %d listings", loc, len(results))

        logger.info("Total: %d listings across %d locations", len(all_results), len(locations))
        return all_results

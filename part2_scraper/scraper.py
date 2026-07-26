import asyncio
import httpx
from typing import List, Dict, Optional
from urllib.parse import urlencode, urljoin
import os
import random

from .utils import logger, get_random_user_agent, retry_async, RateLimiter
from .proxy_manager import ProxyManager
from .parser import parse_search_results, parse_listing_detail
from .models import PropertyListing

class CraigslistScraper:
    LOCATIONS = {
        "milwaukee": "https://milwaukee.craigslist.org",
        "columbus": "https://columbus.craigslist.org"
    }

    def __init__(self, min_price: int, max_price: int, delay_min: float, delay_max: float, proxy_manager: Optional[ProxyManager] = None):
        self.min_price = min_price
        self.max_price = max_price
        self.rate_limiter = RateLimiter(delay_min, delay_max)
        self.proxy_manager = proxy_manager or ProxyManager()
        self.client_timeout = httpx.Timeout(30.0)
    
    def _get_client_kwargs(self) -> dict:
        proxy_url = self.proxy_manager.get_proxy()
        kwargs = {
            "timeout": self.client_timeout,
            "headers": {"User-Agent": get_random_user_agent()},
            "follow_redirects": True
        }
        if proxy_url:
            kwargs["proxies"] = proxy_url
        return kwargs

    @retry_async(retries=3, base_delay=2.0)
    async def fetch_page(self, client: httpx.AsyncClient, url: str, params: Optional[dict] = None) -> str:
        await self.rate_limiter.wait()
        proxy = client._proxies if hasattr(client, '_proxies') else None
        
        logger.info(f"Fetching {url}")
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.text
        except Exception as e:
            if proxy:
                proxy_str = str(proxy.get('http://') or proxy.get('https://', ''))
                self.proxy_manager.mark_failure(proxy_str)
            raise e

    async def scrape_location(self, location_key: str, max_listings: int = 100) -> List[Dict]:
        base_url = self.LOCATIONS.get(location_key)
        if not base_url:
            logger.error(f"Unknown location {location_key}")
            return []

        search_url = f"{base_url}/search/rea"
        keywords = ['single family', 'duplex', 'investment', 'rental']
        all_listings_raw = []

        async with httpx.AsyncClient(**self._get_client_kwargs()) as client:
            for kw in keywords:
                s = 0
                while True:
                    if len(all_listings_raw) >= max_listings:
                        break
                        
                    params = {
                        "min_price": self.min_price,
                        "max_price": self.max_price,
                        "query": kw,
                        "s": s
                    }
                    try:
                        html = await self.fetch_page(client, search_url, params)
                        results = parse_search_results(html)
                        
                        if not results:
                            break
                            
                        # Extract basic info, add location
                        for r in results:
                            r["location"] = f"{location_key}_" + ("wi" if location_key == "milwaukee" else "oh")
                            r["url"] = urljoin(base_url, r["url"])
                            all_listings_raw.append(r)
                            
                        if len(results) < 120:
                            break
                        s += 120
                        
                    except Exception as e:
                        logger.error(f"Failed to scrape search results for {kw} at offset {s}: {e}")
                        break
        
        # Now fetch details
        detailed_listings = []
        async with httpx.AsyncClient(**self._get_client_kwargs()) as client:
            for listing in all_listings_raw[:max_listings]:
                try:
                    html = await self.fetch_page(client, listing["url"])
                    details = parse_listing_detail(html)
                    details.update(listing)  # Merge with basic info
                    detailed_listings.append(details)
                except Exception as e:
                    logger.error(f"Failed to fetch detail for {listing['url']}: {e}")
        
        return detailed_listings

    async def run(self, locations: List[str], max_listings: int = 100) -> List[Dict]:
        all_results = []
        for loc in locations:
            logger.info(f"Starting scrape for {loc}")
            res = await self.scrape_location(loc, max_listings)
            all_results.extend(res)
        return all_results

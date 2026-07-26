import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from playwright.async_api import Page

from .utils import human_delay, random_scroll_amount, random_mouse_movement, setup_logger

logger = setup_logger("facebook.scraper")

class FacebookScraper:

    def __init__(
        self,
        page: Page,
        max_posts: int = 20,
        scroll_pause_min: float = 2.0,
        scroll_pause_max: float = 5.0,
    ) -> None:
        self.page = page
        self.max_posts = max_posts
        self.scroll_pause_min = scroll_pause_min
        self.scroll_pause_max = scroll_pause_max
        self._scraped_posts: list[dict[str, Any]] = []
        self._seen_ids: set[str] = set()

        logger.info(
            "FacebookScraper initialized | max_posts=%d | scroll_pause=%.1f-%.1fs",
            max_posts,
            scroll_pause_min,
            scroll_pause_max,
        )

    async def scrape_feed_posts(self) -> list[dict[str, Any]]:
        logger.info("Starting feed scrape — navigating to Facebook feed...")

        await self.page.goto(
            "https://www.facebook.com/?sk=h_nor",
            wait_until="domcontentloaded",
        )
        await human_delay(3.0, 5.0)

        return await self._scroll_and_extract()

    async def scrape_page_posts(self, page_url: str) -> list[dict[str, Any]]:
        logger.info("Starting page scrape — navigating to %s", page_url)

        await self.page.goto(page_url, wait_until="domcontentloaded")
        await human_delay(3.0, 5.0)

        await self._dismiss_popups()

        return await self._scroll_and_extract()

    async def _scroll_and_extract(self) -> list[dict[str, Any]]:
        stale_scrolls = 0
        max_stale_scrolls = 5
        scroll_count = 0

        while len(self._scraped_posts) < self.max_posts:
            scroll_count += 1
            prev_count = len(self._scraped_posts)

            await self._extract_visible_posts()

            new_count = len(self._scraped_posts) - prev_count
            logger.info(
                "Scroll #%d | Found %d new posts | Total: %d/%d",
                scroll_count,
                new_count,
                len(self._scraped_posts),
                self.max_posts,
            )

            if new_count == 0:
                stale_scrolls += 1
                if stale_scrolls >= max_stale_scrolls:
                    logger.info(
                        "No new posts after %d scrolls — stopping.",
                        max_stale_scrolls,
                    )
                    break
            else:
                stale_scrolls = 0

            scroll_px = random_scroll_amount()
            await self.page.mouse.wheel(0, scroll_px)
            await human_delay(self.scroll_pause_min, self.scroll_pause_max)

            if scroll_count % 3 == 0:
                await random_mouse_movement(self.page)

            if scroll_count % 5 == 0:
                logger.debug("Taking a reading break...")
                await human_delay(4.0, 8.0)

        logger.info(
            "Scraping complete — collected %d posts.",
            len(self._scraped_posts),
        )
        return self._scraped_posts

    async def _extract_visible_posts(self) -> None:
        try:
            post_elements = self.page.locator(
                'div[role="article"][aria-posinset], '
                'div[data-pagelet^="FeedUnit"], '
                'div[role="article"]'
            )

            count = await post_elements.count()

            for i in range(count):
                if len(self._scraped_posts) >= self.max_posts:
                    break

                try:
                    element = post_elements.nth(i)
                    post_data = await self._extract_post_data(element)

                    if post_data and post_data.get("id") not in self._seen_ids:
                        self._seen_ids.add(post_data["id"])
                        self._scraped_posts.append(post_data)

                except Exception as e:
                    logger.debug("Failed to extract post %d: %s", i, e)
                    continue

        except Exception as e:
            logger.warning("Error during post extraction: %s", e)

    async def _extract_post_data(self, element) -> Optional[dict[str, Any]]:
        try:
            post = {
                "id": "",
                "author": "",
                "text": "",
                "timestamp": "",
                "likes": 0,
                "comments_count": 0,
                "shares": 0,
                "url": "",
                "scraped_at": datetime.now().isoformat(),
            }

            author_el = element.locator(
                'h2 a, h3 a, h4 a, '
                'a[role="link"] strong, '
                'span.x1lliihq a'
            )
            if await author_el.count() > 0:
                post["author"] = (await author_el.first.inner_text()).strip()

            text_el = element.locator(
                'div[data-ad-preview="message"], '
                'div[dir="auto"][style*="text-align"], '
                'div.xdj266r, '
                'div[data-ad-comet-preview="message"]'
            )
            if await text_el.count() > 0:
                post["text"] = (await text_el.first.inner_text()).strip()

            if not post["text"]:
                try:
                    all_text = await element.inner_text()
                    lines = [
                        l.strip()
                        for l in all_text.split("\n")
                        if l.strip() and len(l.strip()) > 10
                    ]
                    post["text"] = "\n".join(lines[:5])
                except Exception:
                    pass

            time_el = element.locator(
                'a[href*="/posts/"] span, '
                'a[role="link"] span[id]'
            )
            if await time_el.count() > 0:
                post["timestamp"] = (await time_el.first.inner_text()).strip()

            link_el = element.locator(
                'a[href*="/posts/"], '
                'a[href*="/permalink/"], '
                'a[href*="story_fbid"]'
            )
            if await link_el.count() > 0:
                href = await link_el.first.get_attribute("href")
                if href:
                    post["url"] = (
                        f"https://www.facebook.com{href}"
                        if href.startswith("/")
                        else href
                    )

            reactions_el = element.locator(
                'span[aria-label*="reaction"], '
                'span[aria-label*="like"], '
                'span[aria-label*="people reacted"]'
            )
            if await reactions_el.count() > 0:
                reactions_text = (
                    await reactions_el.first.get_attribute("aria-label") or ""
                )
                numbers = re.findall(r"[\d,]+", reactions_text)
                if numbers:
                    post["likes"] = int(numbers[0].replace(",", ""))

            comments_el = element.locator(
                'span:has-text("comment"), '
                'span:has-text("Comment")'
            )
            if await comments_el.count() > 0:
                comments_text = await comments_el.first.inner_text()
                numbers = re.findall(r"(\d+)", comments_text)
                if numbers:
                    post["comments_count"] = int(numbers[0])

            if post["url"]:
                post["id"] = post["url"]
            elif post["author"] and post["text"]:
                post["id"] = f"{post['author']}_{hash(post['text'][:100])}"
            else:
                post["id"] = f"post_{hash(str(post))}"

            if post["text"] or post["author"]:
                return post
            return None

        except Exception as e:
            logger.debug("Post data extraction failed: %s", e)
            return None

    async def _dismiss_popups(self) -> None:
        popup_selectors = [
            'div[role="dialog"] button[aria-label="Close"]',
            'div[role="dialog"] div[aria-label="Close"]',
            'button:has-text("Not Now")',
            'a:has-text("Not Now")',
        ]
        for selector in popup_selectors:
            try:
                popup = self.page.locator(selector)
                if await popup.count() > 0:
                    await popup.first.click()
                    await human_delay(0.5, 1.0)
                    logger.info("Dismissed popup: %s", selector)
            except Exception:
                pass

    def export_json(self, output_path: str = "output/facebook_posts.json") -> str:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "metadata": {
                        "scraped_at": datetime.now().isoformat(),
                        "total_posts": len(self._scraped_posts),
                        "source": "facebook_feed",
                    },
                    "posts": self._scraped_posts,
                },
                f,
                indent=2,
                ensure_ascii=False,
            )

        logger.info("Exported %d posts to %s", len(self._scraped_posts), path)
        return str(path.resolve())

    @property
    def posts(self) -> list[dict[str, Any]]:
        return self._scraped_posts

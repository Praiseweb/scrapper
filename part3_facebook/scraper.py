"""
Facebook Automation — Post Scraper
===================================

Scrapes posts from Facebook feed or specific pages with
human-like scrolling and interaction patterns.
"""

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
    """
    Scrapes posts from Facebook with human-like browsing behavior.

    Handles infinite scroll, extracts structured post data, and
    exports results to JSON. Designed to look like normal browsing
    activity with natural timing and scroll patterns.

    Attributes:
        page: Playwright Page object (must be authenticated).
        max_posts: Maximum number of posts to collect.
        scroll_pause: Base pause between scroll actions (seconds).
    """

    def __init__(
        self,
        page: Page,
        max_posts: int = 20,
        scroll_pause_min: float = 2.0,
        scroll_pause_max: float = 5.0,
    ) -> None:
        """
        Initialize the Facebook scraper.

        Args:
            page: Authenticated Playwright Page object.
            max_posts: Maximum posts to scrape before stopping.
            scroll_pause_min: Minimum pause between scrolls (seconds).
            scroll_pause_max: Maximum pause between scrolls (seconds).
        """
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
        """
        Scrape posts from the authenticated user's Facebook news feed.

        Scrolls through the feed, extracting post data until max_posts
        is reached or no new posts are found after multiple scroll attempts.

        Returns:
            List of post dictionaries with extracted data.
        """
        logger.info("Starting feed scrape — navigating to Facebook feed...")

        await self.page.goto(
            "https://www.facebook.com/?sk=h_nor",
            wait_until="domcontentloaded",
        )
        await human_delay(3.0, 5.0)

        return await self._scroll_and_extract()

    async def scrape_page_posts(self, page_url: str) -> list[dict[str, Any]]:
        """
        Scrape posts from a specific Facebook page.

        Args:
            page_url: URL of the Facebook page to scrape.

        Returns:
            List of post dictionaries with extracted data.
        """
        logger.info("Starting page scrape — navigating to %s", page_url)

        await self.page.goto(page_url, wait_until="domcontentloaded")
        await human_delay(3.0, 5.0)

        # Dismiss any popups (login prompts, cookie banners)
        await self._dismiss_popups()

        return await self._scroll_and_extract()

    async def _scroll_and_extract(self) -> list[dict[str, Any]]:
        """
        Core scraping loop: scroll, extract posts, repeat.

        Uses a stale-scroll counter to detect when no new content
        is being loaded (end of feed or throttled).
        """
        stale_scrolls = 0
        max_stale_scrolls = 5  # Stop after 5 scrolls with no new posts
        scroll_count = 0

        while len(self._scraped_posts) < self.max_posts:
            scroll_count += 1
            prev_count = len(self._scraped_posts)

            # Extract posts currently visible on the page
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

            # Scroll down with human-like behavior
            scroll_px = random_scroll_amount()
            await self.page.mouse.wheel(0, scroll_px)
            await human_delay(self.scroll_pause_min, self.scroll_pause_max)

            # Occasional mouse movement (humans don't just scroll)
            if scroll_count % 3 == 0:
                await random_mouse_movement(self.page)

            # Occasional longer pause (reading a post)
            if scroll_count % 5 == 0:
                logger.debug("Taking a reading break...")
                await human_delay(4.0, 8.0)

        logger.info(
            "Scraping complete — collected %d posts.",
            len(self._scraped_posts),
        )
        return self._scraped_posts

    async def _extract_visible_posts(self) -> None:
        """
        Extract post data from all currently visible post elements.

        Facebook renders posts as div[role="article"] elements.
        Each post is identified by a data attribute or aria label
        to prevent duplicate extraction.
        """
        try:
            # Facebook post containers — these selectors target the
            # main post wrapper elements in the news feed
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
        """
        Extract structured data from a single post element.

        Args:
            element: Playwright Locator for the post container.

        Returns:
            Dictionary with post data, or None if extraction fails.
        """
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

            # ------ Author Name ------
            # The author is usually in an <a> tag with a specific structure
            author_el = element.locator(
                'h2 a, h3 a, h4 a, '
                'a[role="link"] strong, '
                'span.x1lliihq a'  # Common class for author links
            )
            if await author_el.count() > 0:
                post["author"] = (await author_el.first.inner_text()).strip()

            # ------ Post Text ------
            # Post content is in a div with specific data attributes
            text_el = element.locator(
                'div[data-ad-preview="message"], '
                'div[dir="auto"][style*="text-align"], '
                'div.xdj266r, '  # Common content wrapper class
                'div[data-ad-comet-preview="message"]'
            )
            if await text_el.count() > 0:
                post["text"] = (await text_el.first.inner_text()).strip()

            # Fallback: get all visible text if specific selectors fail
            if not post["text"]:
                try:
                    all_text = await element.inner_text()
                    # Take first 500 chars as the post preview
                    lines = [
                        l.strip()
                        for l in all_text.split("\n")
                        if l.strip() and len(l.strip()) > 10
                    ]
                    post["text"] = "\n".join(lines[:5])
                except Exception:
                    pass

            # ------ Timestamp ------
            time_el = element.locator(
                'a[href*="/posts/"] span, '
                'a[role="link"] span[id]'
            )
            if await time_el.count() > 0:
                post["timestamp"] = (await time_el.first.inner_text()).strip()

            # ------ Post URL ------
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

            # ------ Engagement Metrics ------
            # Likes/reactions count
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

            # Comments count
            comments_el = element.locator(
                'span:has-text("comment"), '
                'span:has-text("Comment")'
            )
            if await comments_el.count() > 0:
                comments_text = await comments_el.first.inner_text()
                numbers = re.findall(r"(\d+)", comments_text)
                if numbers:
                    post["comments_count"] = int(numbers[0])

            # ------ Generate unique ID ------
            # Use URL if available, otherwise hash of author + text
            if post["url"]:
                post["id"] = post["url"]
            elif post["author"] and post["text"]:
                post["id"] = f"{post['author']}_{hash(post['text'][:100])}"
            else:
                post["id"] = f"post_{hash(str(post))}"

            # Only return posts that have meaningful content
            if post["text"] or post["author"]:
                return post
            return None

        except Exception as e:
            logger.debug("Post data extraction failed: %s", e)
            return None

    async def _dismiss_popups(self) -> None:
        """Dismiss common Facebook popups and overlays."""
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
        """
        Export scraped posts to a JSON file.

        Args:
            output_path: Path for the output JSON file.

        Returns:
            Absolute path to the created file.
        """
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
        """Get the list of scraped posts."""
        return self._scraped_posts

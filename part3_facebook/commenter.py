import logging
import random
from datetime import datetime
from typing import Any, Optional

from playwright.async_api import Page

from .utils import human_delay, human_typing_speed, random_mouse_movement, setup_logger

logger = setup_logger("facebook.commenter")

DEFAULT_COMMENTS: list[str] = [
    "Great post! Thanks for sharing this.",
    "This is really interesting, appreciate the insight!",
    "Love this! Very helpful information.",
    "Thanks for putting this out there 👍",
    "Really valuable content, bookmarking this.",
    "Well said! I appreciate the transparency.",
    "This is exactly what I was looking for, thank you!",
    "Fantastic share — learned something new today.",
    "Great perspective on this topic!",
    "Appreciate you sharing this with the community.",
    "This is solid information. Thanks!",
    "Really helpful post — keep them coming!",
]

class FacebookCommenter:

    def __init__(
        self,
        page: Page,
        min_delay: float = 30.0,
        max_delay: float = 120.0,
        daily_limit: int = 10,
        comments: Optional[list[str]] = None,
    ) -> None:
        self.page = page
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.daily_limit = daily_limit
        self.comments = comments or DEFAULT_COMMENTS

        self._action_count: int = 0
        self._action_log: list[dict[str, Any]] = []
        self._session_start = datetime.now()

        logger.info(
            "FacebookCommenter initialized | delay=%.0f-%.0fs | daily_limit=%d | templates=%d",
            min_delay,
            max_delay,
            daily_limit,
            len(self.comments),
        )

    async def comment_on_post(
        self,
        post_element,
        comment_text: Optional[str] = None,
    ) -> bool:
        if self._action_count >= self.daily_limit:
            logger.warning(
                "Daily limit reached (%d/%d) — skipping comment.",
                self._action_count,
                self.daily_limit,
            )
            return False

        if comment_text is None:
            comment_text = random.choice(self.comments)

        logger.info(
            "Attempting to comment (action %d/%d): '%s'",
            self._action_count + 1,
            self.daily_limit,
            comment_text[:50] + "..." if len(comment_text) > 50 else comment_text,
        )

        try:
            await post_element.scroll_into_view_if_needed()
            await human_delay(1.0, 2.5)

            await random_mouse_movement(self.page)

            comment_btn = post_element.locator(
                'div[aria-label="Write a comment"], '
                'div[aria-label="Write a comment…"], '
                'span:has-text("Write a comment"), '
                'div[contenteditable="true"][role="textbox"]'
            )

            expand_btn = post_element.locator(
                'div[aria-label="Leave a comment"], '
                'span:has-text("Comment"):not(:has-text("comments"))'
            )

            if await expand_btn.count() > 0:
                await expand_btn.first.click()
                await human_delay(1.0, 2.0)

            await comment_btn.first.wait_for(state="visible", timeout=10000)
            await comment_btn.first.click()
            await human_delay(0.5, 1.5)

            await self._type_comment(comment_btn.first, comment_text)
            await human_delay(0.5, 2.0)

            logger.info("Submitting comment...")
            await comment_btn.first.press("Enter")
            await human_delay(2.0, 4.0)

            self._action_count += 1
            action_record = {
                "action": "comment",
                "text": comment_text,
                "timestamp": datetime.now().isoformat(),
                "action_number": self._action_count,
                "success": True,
            }
            self._action_log.append(action_record)

            logger.info(
                "✅ Comment posted successfully (action %d/%d)",
                self._action_count,
                self.daily_limit,
            )
            return True

        except Exception as e:
            logger.error("Failed to post comment: %s", e)
            self._action_log.append({
                "action": "comment",
                "text": comment_text,
                "timestamp": datetime.now().isoformat(),
                "action_number": self._action_count + 1,
                "success": False,
                "error": str(e),
            })
            return False

    async def _type_comment(self, element, text: str) -> None:
        for i, char in enumerate(text):
            if random.random() < 0.03 and char.isalpha():
                wrong_char = chr(ord(char) + random.choice([-1, 1]))
                if wrong_char.isalpha():
                    await element.press_sequentially(wrong_char, delay=0)
                    await human_delay(0.1, 0.3)
                    await element.press("Backspace")
                    await human_delay(0.05, 0.15)

            delay_ms = human_typing_speed() * 1000
            await element.press_sequentially(char, delay=delay_ms)

            if char == " " and random.random() < 0.3:
                await human_delay(0.2, 0.6)

    async def run_commenting_workflow(
        self,
        posts: list[dict[str, Any]],
        max_comments: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        effective_limit = min(
            max_comments or self.daily_limit,
            self.daily_limit,
            len(posts),
        )

        logger.info(
            "Starting commenting workflow | %d posts available | limit=%d",
            len(posts),
            effective_limit,
        )

        post_indices = list(range(len(posts)))
        random.shuffle(post_indices)

        comments_posted = 0

        for idx in post_indices[:effective_limit]:
            if self._action_count >= self.daily_limit:
                logger.info("Daily limit reached — stopping workflow.")
                break

            try:
                post_elements = self.page.locator('div[role="article"]')
                element_count = await post_elements.count()

                if idx >= element_count:
                    logger.debug("Post index %d out of range — skipping.", idx)
                    continue

                post_element = post_elements.nth(idx)

                success = await self.comment_on_post(post_element)

                if success:
                    comments_posted += 1

                    if comments_posted > 0 and comments_posted % random.randint(3, 4) == 0:
                        break_time = random.uniform(60, 180)
                        logger.info(
                            "Taking a session break (%.0f seconds)...",
                            break_time,
                        )
                        await human_delay(break_time, break_time + 10)

                wait_time = random.uniform(self.min_delay, self.max_delay)
                logger.info("Waiting %.0f seconds before next action...", wait_time)
                await human_delay(wait_time, wait_time + 5)

            except Exception as e:
                logger.error("Error in commenting workflow for post %d: %s", idx, e)
                continue

        logger.info(
            "Commenting workflow complete | %d comments posted | %d total actions",
            comments_posted,
            self._action_count,
        )

        return self._action_log

    @property
    def action_count(self) -> int:
        return self._action_count

    @property
    def action_log(self) -> list[dict[str, Any]]:
        return self._action_log

    @property
    def remaining_actions(self) -> int:
        return max(0, self.daily_limit - self._action_count)

import asyncio
import logging
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from .stealth import apply_stealth, get_random_user_agent, get_random_viewport
from .utils import human_delay, human_type, setup_logger

logger = setup_logger("facebook.browser")

class BrowserManager:

    def __init__(
        self,
        headless: bool = False,
        state_dir: str = "browser_state",
        slow_mo: int = 50,
    ) -> None:
        self.headless = headless
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.slow_mo = slow_mo

        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

        self._user_agent = get_random_user_agent()
        self._viewport = get_random_viewport()

        logger.info(
            "BrowserManager initialized | headless=%s | state_dir=%s",
            headless,
            self.state_dir,
        )

    async def start(self) -> Page:
        logger.info("Launching browser with stealth configuration...")

        self._playwright = await async_playwright().start()

        storage_state_path = self.state_dir / "storage_state.json"

        context_options = {
            "user_agent": self._user_agent,
            "viewport": self._viewport,
            "locale": "en-US",
            "timezone_id": "America/Chicago",
            "color_scheme": "light",
            "reduced_motion": "no-preference",
            "has_touch": False,
            "java_script_enabled": True,
            "ignore_https_errors": True,
            "permissions": ["geolocation"],
            "geolocation": {"latitude": 43.0389, "longitude": -87.9065},
        }

        if storage_state_path.exists():
            context_options["storage_state"] = str(storage_state_path)
            logger.info("Loaded existing session state from %s", storage_state_path)

        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.state_dir / "user_data"),
            headless=self.headless,
            slow_mo=self.slow_mo,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--disable-dev-shm-usage",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-extensions",
                f"--window-size={self._viewport['width']},{self._viewport['height']}",
            ],
            **context_options,
        )

        if self._context.pages:
            self._page = self._context.pages[0]
        else:
            self._page = await self._context.new_page()

        await apply_stealth(self._page)
        logger.info(
            "Browser launched | UA=%s | viewport=%sx%s",
            self._user_agent[:50] + "...",
            self._viewport["width"],
            self._viewport["height"],
        )

        return self._page

    async def login(self, email: str, password: str) -> Page:
        if not self._page:
            raise RuntimeError("Browser not started. Call start() first.")

        page = self._page
        logger.info("Navigating to Facebook...")

        await page.goto("https://www.facebook.com/", wait_until="domcontentloaded")
        await human_delay(2.0, 4.0)

        if await self._is_logged_in(page):
            logger.info("Already logged in from previous session!")
            return page

        logger.info("Not logged in — proceeding with login flow...")

        try:
            cookie_btn = page.locator(
                'button[data-cookiebanner="accept_button"], '
                'button:has-text("Allow all cookies"), '
                'button:has-text("Accept All")'
            )
            if await cookie_btn.count() > 0:
                await cookie_btn.first.click()
                logger.info("Dismissed cookie consent banner")
                await human_delay(1.0, 2.0)
        except Exception:
            pass

        logger.info("Entering email...")
        email_input = page.locator('input#email, input[name="email"]')
        await email_input.click()
        await human_delay(0.5, 1.0)

        await email_input.fill("")
        await human_delay(0.3, 0.6)

        for char in email:
            await email_input.press_sequentially(
                char, delay=_typing_delay()
            )

        await human_delay(0.5, 1.5)

        logger.info("Entering password...")
        pass_input = page.locator('input#pass, input[name="pass"]')
        await pass_input.click()
        await human_delay(0.3, 0.8)

        for char in password:
            await pass_input.press_sequentially(
                char, delay=_typing_delay()
            )

        await human_delay(0.5, 1.5)

        logger.info("Clicking login button...")
        login_btn = page.locator(
            'button[name="login"], '
            'button[data-testid="royal_login_button"], '
            'button:has-text("Log In"), '
            'input[type="submit"][value="Log In"]'
        )
        await login_btn.first.click()

        await human_delay(3.0, 6.0)

        if await self._is_2fa_page(page):
            logger.warning(
                "Two-factor authentication detected! "
                "Please complete 2FA manually in the browser window."
            )
            print("\n" + "=" * 60)
            print("⚠️  TWO-FACTOR AUTHENTICATION REQUIRED")
            print("   Please complete 2FA in the browser window.")
            print("   The script will continue after you're logged in.")
            print("=" * 60 + "\n")

            for _ in range(60):
                await asyncio.sleep(3)
                if await self._is_logged_in(page):
                    logger.info("2FA completed successfully!")
                    break
            else:
                raise RuntimeError(
                    "Timed out waiting for 2FA completion (3 minutes)."
                )

        if await self._is_logged_in(page):
            logger.info("✅ Login successful!")
            await self._save_state()
            return page
        else:
            error_el = page.locator(
                'div[role="alert"], '
                'div._9ay7, '
                'div:has-text("Wrong credentials")'
            )
            if await error_el.count() > 0:
                error_text = await error_el.first.inner_text()
                raise RuntimeError(f"Login failed: {error_text}")
            raise RuntimeError(
                "Login failed — could not verify authenticated state."
            )

    async def _is_logged_in(self, page: Page) -> bool:
        try:
            logged_in_indicators = [
                'a[aria-label="Home"]',
                'div[aria-label="Facebook"]',
                'a[href="/me/"]',
                'div[role="navigation"]',
                'svg[aria-label="Your profile"]',
            ]
            for selector in logged_in_indicators:
                if await page.locator(selector).count() > 0:
                    return True

            url = page.url
            if any(path in url for path in ["/home", "/?sk=h_", "/feed"]):
                return True

            return False
        except Exception:
            return False

    async def _is_2fa_page(self, page: Page) -> bool:
        try:
            twofa_indicators = [
                'input[name="approvals_code"]',
                'div:has-text("Enter the code")',
                'div:has-text("Two-Factor")',
                'div:has-text("authentication code")',
                '#approvals_code',
            ]
            for selector in twofa_indicators:
                if await page.locator(selector).count() > 0:
                    return True
            return False
        except Exception:
            return False

    async def _save_state(self) -> None:
        if self._context:
            state_path = self.state_dir / "storage_state.json"
            await self._context.storage_state(path=str(state_path))
            logger.info("Session state saved to %s", state_path)

    async def close(self) -> None:
        logger.info("Shutting down browser...")
        try:
            if self._context:
                await self._save_state()
                await self._context.close()
            if self._playwright:
                await self._playwright.stop()
            logger.info("Browser closed cleanly.")
        except Exception as e:
            logger.error("Error during browser shutdown: %s", e)

    async def __aenter__(self) -> "BrowserManager":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    @property
    def page(self) -> Optional[Page]:
        return self._page

def _typing_delay() -> float:
    import random

    if random.random() < 0.8:
        return random.uniform(50, 150)
    else:
        return random.uniform(200, 400)

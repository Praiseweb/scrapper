"""
Facebook Automation — Utility Functions
========================================

Shared helpers for human-like timing, logging, and interaction patterns.
"""

import asyncio
import logging
import random
import sys
from datetime import datetime
from pathlib import Path


def setup_logger(
    name: str = "facebook_automation",
    log_dir: str = "logs",
    level: int = logging.INFO,
) -> logging.Logger:
    """
    Configure structured logging with both console and file handlers.

    Args:
        name: Logger name identifier.
        log_dir: Directory for log files.
        level: Logging level.

    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid duplicate handlers on repeat calls
    if logger.handlers:
        return logger

    # Create log directory
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    # Timestamp-based log file name
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_path / f"facebook_{timestamp}.log"

    # Detailed format for file output
    file_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(file_formatter)

    # Concise format for console output
    console_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S",
    )
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(console_formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


async def human_delay(min_seconds: float = 1.0, max_seconds: float = 3.0) -> None:
    """
    Sleep for a random duration that mimics human reaction time.

    Uses a slightly skewed distribution — humans tend to be slightly
    faster than the midpoint, with occasional longer pauses.

    Args:
        min_seconds: Minimum delay in seconds.
        max_seconds: Maximum delay in seconds.
    """
    # Triangular distribution skews toward the lower end (more natural)
    delay = random.triangular(min_seconds, max_seconds, min_seconds * 1.3)
    await asyncio.sleep(delay)


def human_typing_speed() -> float:
    """
    Return a random inter-keystroke delay in seconds.

    Average human typing speed is ~40-80 WPM, which translates to
    approximately 75-200ms between keystrokes, with occasional
    longer pauses at word boundaries.

    Returns:
        Delay in seconds between keystrokes.
    """
    # 80% chance of normal typing speed, 20% chance of a brief pause
    if random.random() < 0.8:
        return random.uniform(0.05, 0.15)  # 50-150ms normal typing
    else:
        return random.uniform(0.2, 0.5)  # 200-500ms thinking pause


async def human_type(page, selector: str, text: str) -> None:
    """
    Type text into an element with human-like keystroke timing.

    Includes occasional brief pauses and realistic speed variations
    that mimic natural typing patterns.

    Args:
        page: Playwright Page object.
        selector: CSS selector for the input element.
        text: Text to type.
    """
    element = page.locator(selector)
    await element.click()
    await human_delay(0.3, 0.8)  # Brief pause after clicking

    for i, char in enumerate(text):
        delay_ms = human_typing_speed() * 1000  # Convert to milliseconds
        await element.press_sequentially(char, delay=delay_ms)

        # Occasional longer pause at word boundaries (space, punctuation)
        if char in " .,!?":
            await human_delay(0.1, 0.4)


def random_scroll_amount() -> int:
    """
    Return a random scroll distance in pixels that mimics human scrolling.

    Humans don't scroll in exact increments — they vary between
    small adjustments and larger page-down-like scrolls.

    Returns:
        Pixel amount to scroll.
    """
    # Mix of small, medium, and large scrolls
    scroll_type = random.random()
    if scroll_type < 0.3:
        return random.randint(100, 300)    # Small scroll
    elif scroll_type < 0.7:
        return random.randint(300, 600)    # Medium scroll
    else:
        return random.randint(600, 1000)   # Large scroll


def format_timestamp(dt: datetime | None = None) -> str:
    """
    Format a datetime for consistent log output.

    Args:
        dt: Datetime to format. Defaults to now.

    Returns:
        Formatted timestamp string.
    """
    if dt is None:
        dt = datetime.now()
    return dt.strftime("%Y-%m-%d %H:%M:%S")


async def random_mouse_movement(page) -> None:
    """
    Perform random mouse movements to simulate human cursor behavior.

    Detection systems track mouse movement patterns — bots typically
    move in straight lines or don't move the mouse at all.

    Args:
        page: Playwright Page object.
    """
    viewport = page.viewport_size
    if not viewport:
        return

    # Move to 2-4 random positions
    for _ in range(random.randint(2, 4)):
        x = random.randint(100, viewport["width"] - 100)
        y = random.randint(100, viewport["height"] - 100)
        await page.mouse.move(x, y, steps=random.randint(5, 15))
        await human_delay(0.2, 0.8)


async def safe_click(page, selector: str, timeout: int = 10000) -> bool:
    """
    Safely click an element with human-like behavior.

    Waits for the element, moves mouse to it naturally, then clicks.
    Returns False instead of raising if the element isn't found.

    Args:
        page: Playwright Page object.
        selector: CSS selector to click.
        timeout: Max wait time in milliseconds.

    Returns:
        True if clicked successfully, False otherwise.
    """
    try:
        element = page.locator(selector)
        await element.wait_for(state="visible", timeout=timeout)
        await human_delay(0.3, 1.0)  # Pause before clicking (natural)
        await element.click()
        return True
    except Exception:
        return False

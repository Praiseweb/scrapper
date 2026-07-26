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
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if logger.handlers:
        return logger

    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_path / f"facebook_{timestamp}.log"

    file_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(file_formatter)

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
    delay = random.triangular(min_seconds, max_seconds, min_seconds * 1.3)
    await asyncio.sleep(delay)

def human_typing_speed() -> float:
    if random.random() < 0.8:
        return random.uniform(0.05, 0.15)
    else:
        return random.uniform(0.2, 0.5)

async def human_type(page, selector: str, text: str) -> None:
    element = page.locator(selector)
    await element.click()
    await human_delay(0.3, 0.8)

    for i, char in enumerate(text):
        delay_ms = human_typing_speed() * 1000
        await element.press_sequentially(char, delay=delay_ms)

        if char in " .,!?":
            await human_delay(0.1, 0.4)

def random_scroll_amount() -> int:
    scroll_type = random.random()
    if scroll_type < 0.3:
        return random.randint(100, 300)
    elif scroll_type < 0.7:
        return random.randint(300, 600)
    else:
        return random.randint(600, 1000)

def format_timestamp(dt: datetime | None = None) -> str:
    if dt is None:
        dt = datetime.now()
    return dt.strftime("%Y-%m-%d %H:%M:%S")

async def random_mouse_movement(page) -> None:
    viewport = page.viewport_size
    if not viewport:
        return

    for _ in range(random.randint(2, 4)):
        x = random.randint(100, viewport["width"] - 100)
        y = random.randint(100, viewport["height"] - 100)
        await page.mouse.move(x, y, steps=random.randint(5, 15))
        await human_delay(0.2, 0.8)

async def safe_click(page, selector: str, timeout: int = 10000) -> bool:
    try:
        element = page.locator(selector)
        await element.wait_for(state="visible", timeout=timeout)
        await human_delay(0.3, 1.0)
        await element.click()
        return True
    except Exception:
        return False

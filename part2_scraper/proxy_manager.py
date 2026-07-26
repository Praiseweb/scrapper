import random
from typing import Optional, List
from .utils import logger

class ProxyManager:
    def __init__(self, proxies: Optional[List[str]] = None, proxy_file: Optional[str] = None):
        self.proxies: List[str] = []
        if proxies:
            self.proxies.extend(proxies)
        if proxy_file:
            self._load_from_file(proxy_file)
        self.dead_proxies: List[str] = []
        self.max_failures = 3
        self.proxy_failures: dict = {}

    def _load_from_file(self, filepath: str) -> None:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                loaded = [line.strip() for line in f if line.strip()]
                self.proxies.extend(loaded)
            logger.info(f"Loaded {len(loaded)} proxies from {filepath}")
        except Exception as e:
            logger.error(f"Failed to load proxies from {filepath}: {e}")

    def get_proxy(self) -> Optional[str]:
        available = [p for p in self.proxies if p not in self.dead_proxies]
        if not available:
            return None
        return random.choice(available)

    def mark_failure(self, proxy: str) -> None:
        if proxy not in self.proxies:
            return
        
        self.proxy_failures[proxy] = self.proxy_failures.get(proxy, 0) + 1
        if self.proxy_failures[proxy] >= self.max_failures:
            logger.warning(f"Marking proxy {proxy} as dead after {self.max_failures} failures")
            self.dead_proxies.append(proxy)

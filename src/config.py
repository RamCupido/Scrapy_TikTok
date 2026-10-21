import os

DEFAULT_TIMEOUT_MS = int(os.getenv("SCRAPER_TIMEOUT_MS", "25000"))
RENDER_WAIT_MS = int(os.getenv("SCRAPER_RENDER_WAIT_MS", "3500"))
HEADLESS_MODE = os.getenv("SCRAPER_HEADLESS", "true").lower() == "true"

DEFAULT_USER_AGENT = os.getenv(
    "SCRAPER_USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0.0.0 Safari/537.36",
)

TIKTOK_BASE_URL = "https://www.tiktok.com"
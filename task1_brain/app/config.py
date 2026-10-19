"""All settings in one place. Override with environment variables (see ../.env.example)."""
import os
from pathlib import Path

DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = os.getenv("DB_PATH", str(DATA_DIR / "brain.sqlite"))

SITEMAP_URL = os.getenv("SITEMAP_URL", "https://support.brilliantdirectories.com/support/sitemap.xml")
USER_AGENT = os.getenv("CRAWL_UA", "BusinessLabsCapstoneBot/1.0 (student project; contact: CHANGE-ME@example.com)")

# Politeness: 2 requests at a time, ~1s gap each => roughly 1-2 pages/second at most.
CONCURRENCY = int(os.getenv("CRAWL_CONCURRENCY", "2"))
DELAY_SECONDS = float(os.getenv("CRAWL_DELAY", "1.0"))
BATCH_SIZE = int(os.getenv("CRAWL_BATCH", "25"))
MAX_PAGES = int(os.getenv("MAX_PAGES", "0"))  # 0 = no limit. Use e.g. 30 for a quick trial.
MAX_IMAGES_PER_PAGE = int(os.getenv("MAX_IMAGES_PER_PAGE", "8"))

# Models. Cheap model for vision; stronger model for answers. Prove the choice in EVALS.md.
MODEL_ANSWER = os.getenv("MODEL_ANSWER", "claude-sonnet-5-5")
MODEL_VISION = os.getenv("MODEL_VISION", "claude-haiku-5-5")

TOP_K = int(os.getenv("TOP_K", "8"))
REFRESH_EVERY_HOURS = float(os.getenv("REFRESH_EVERY_HOURS", "24"))
BRAIN_API_KEY = os.getenv("BRAIN_API_KEY", "")  # if set, callers must send X-API-Key

import os
from pathlib import Path

BRAIN_URL = os.getenv("BRAIN_URL", "http://localhost:8001")
BRAIN_API_KEY = os.getenv("BRAIN_API_KEY", "")
DATA_DIR = Path(os.getenv("T3_DATA_DIR", "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

MODEL_EXTRACT = os.getenv("MODEL_EXTRACT", "claude-haiku-5-5")   # many small, parallel calls
MODEL_REASON = os.getenv("MODEL_REASON", "claude-sonnet-5-5")    # scoping, estimating, writing, review
RATE_PER_HOUR = float(os.getenv("RATE_PER_HOUR", "40"))          # money is computed in code, never by the LLM
CURRENCY = os.getenv("CURRENCY", "USD")
CONTINGENCY = float(os.getenv("CONTINGENCY", "0.15"))
SETTING_HOURS = float(os.getenv("SETTING_HOURS", "0.5"))          # cost of configuring an existing setting
WINDOW_CHARS = int(os.getenv("WINDOW_CHARS", "6000"))

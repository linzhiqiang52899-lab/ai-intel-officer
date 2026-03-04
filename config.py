import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the project directory
_BASE = Path(__file__).parent
load_dotenv(_BASE / ".env")

DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")

# Path resolution: share with local CLI skill if available, else use project data/
_LOCAL_SKILLS = Path(r"C:\Users\pqluc\.claude\skills\rss-intel")
if _LOCAL_SKILLS.exists():
    FEEDS_FILE = _LOCAL_SKILLS / "feeds.json"
    SCRIPTS_DIR = _LOCAL_SKILLS / "scripts"
else:
    FEEDS_FILE = _BASE / "data" / "feeds.json"
    SCRIPTS_DIR = _BASE / "scripts"

# Cache
CACHE_DIR = _BASE / "cache"
CACHE_FILE = CACHE_DIR / "latest.json"
CACHE_DIR.mkdir(exist_ok=True)

# Static files
STATIC_DIR = _BASE / "static"


def check_api_key() -> None:
    if not DEEPSEEK_API_KEY:
        print(
            "[WARNING] DEEPSEEK_API_KEY is not set. "
            "Edit D:\\code\\test\\rss-web\\.env and add your key."
        )
